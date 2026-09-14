"""La pata suelta: que exista, que se sitúe en el tiempo y que su coste salga del libro de verdad.

Cada prueba de aquí fija una de las formas de engañarse que la fase anterior ya cometió una vez.
"""
import polars as pl
import pytest

from scalper import pata as P
from scalper.sim.engine import Engine
from scalper.storage import ParquetWriter, scan
from conftest import make_book, make_market


# --------------------------------------------------------------------------- matemática de salida
def test_salir_de_una_compra_vende_contra_los_bids_no_contra_el_mid():
    # Comprado a 0,50. El mid dice 0,50 y no ha pasado nada; el bid dice 0,45 y salir cuesta.
    libro = make_book("t", [(0.45, 100)], [(0.55, 100)])
    s = P.coste_de_salir(libro, "BUY", 50)
    assert s.precio == 0.45 and s.ejecutable
    assert s.precio != libro.mid            # el mid (0,50) no es un precio al que se pueda salir
    assert P.contrafactual_pnl("BUY", 0.50, 50, s) == -2.5


def test_salir_de_una_venta_compra_contra_los_asks():
    libro = make_book("t", [(0.45, 100)], [(0.55, 100)])
    s = P.coste_de_salir(libro, "SELL", 50)
    assert s.precio == 0.55
    assert P.contrafactual_pnl("SELL", 0.50, 50, s) == -2.5


def test_el_vwap_atraviesa_niveles_cuando_hace_falta():
    # 30 al mejor bid y 70 un tick por debajo: salir de 50 shares toca los dos niveles.
    libro = make_book("t", [(0.45, 30), (0.44, 70)], [(0.55, 100)])
    s = P.coste_de_salir(libro, "BUY", 50)
    esperado = (30 * 0.45 + 20 * 0.44) / 50
    assert s.precio == pytest.approx(esperado, abs=1e-6)
    assert s.peor_nivel == 0.44
    assert s.slippage == pytest.approx(esperado - 0.45, abs=1e-6)


def test_sin_profundidad_no_se_inventa_un_precio():
    # Solo hay 10 shares en el bid y queremos salir de 50: la salida no es ejecutable entera.
    libro = make_book("t", [(0.45, 10)], [(0.55, 100)])
    s = P.coste_de_salir(libro, "BUY", 50)
    assert s.shares == 10 and not s.completa and not s.ejecutable
    assert P.contrafactual_pnl("BUY", 0.50, 50, s) is None    # antes que un número apoyado en el mid


def test_un_libro_vacio_del_lado_de_salida_no_da_precio():
    libro = make_book("t", [], [(0.55, 100)])
    s = P.coste_de_salir(libro, "BUY", 50)
    assert s.precio is None and P.contrafactual_pnl("BUY", 0.50, 50, s) is None


# --------------------------------------------------------------------------- identidad y T0
def test_el_identificador_es_estable_y_no_choca():
    a = P.nuevo_id("exp-1", "s1", "tok", 1000)
    assert a == P.nuevo_id("exp-1", "s1", "tok", 1000)          # la misma pata, el mismo id
    assert a != P.nuevo_id("exp-1", "s1", "tok", 1001)          # otro instante, otra pata
    assert a != P.nuevo_id("exp-2", "s1", "tok", 1000)          # otro experimento, otra pata
    assert a.startswith("pl-")


class _Sig:
    def __init__(self):
        self.signal_id = "s1"
        self.strategy = "TENNIS_SPREAD_CAPTURE"
        self.kind = "spread_capture"
        self.condition_id = "c1"
        self.event_id = "e1"
        self.meta = {"edge_net": 0.02}


class _Orden:
    def __init__(self, token_id, side, price):
        self.token_id, self.side, self.price = token_id, side, price


def _pata(t0=10_000):
    libro = make_book("tok", [(0.45, 200)], [(0.55, 200)])
    falta = make_book("otro", [(0.40, 200)], [(0.50, 200)])
    return P.abrir("exp-1", _Sig(), _Orden("tok", "BUY", 0.46), _Orden("otro", "SELL", 0.54),
                   t0, 50.0, 0.46, libro, falta), libro


def test_t0_guarda_las_dos_alternativas_reales():
    # En T0 hay dos salidas posibles y las dos se guardan: completar cruzando, o deshacer.
    p, _ = _pata()
    assert p.t0_ms == 10_000
    assert p.t0_best_bid == 0.45 and p.t0_best_ask == 0.55
    assert p.t0_salida_precio == 0.45                       # deshacer: vender al bid
    assert p.t0_contrafactual_pnl == pytest.approx(-0.5)    # (0,45 − 0,46) × 50
    assert p.t0_precio_completar == 0.40                    # completar: vender la otra pata al bid
    assert p.ventaja_prometida == 0.02


# --------------------------------------------------------------------------- trayectoria
def test_cada_horizonte_se_mide_una_sola_vez():
    p, libro = _pata()
    assert len(P.medir(p, 10_000, libro)) == 0              # todavía no vence ninguno
    nuevos = P.medir(p, 10_000 + 6_000, libro)
    assert [x.horizonte_ms for x in nuevos] == [1_000, 5_000]
    assert P.medir(p, 10_000 + 6_000, libro) == []          # no se repiten
    assert len(p.puntos) == 2


def test_un_hueco_se_declara_en_vez_de_rellenarse():
    p, _ = _pata()
    P.medir(p, 10_000 + 1_000, None)                        # sin libro en ese instante
    x = p.punto(1_000)
    assert x.contrafactual_pnl is None and x.incompleto == "sin_libro"
    p2, _ = _pata()
    P.medir(p2, 10_000 + 1_000, make_book("tok", [(0.45, 5)], [(0.55, 200)]))
    assert p2.punto(1_000).incompleto == "sin_profundidad"


def test_la_trayectoria_sigue_el_precio_hacia_abajo():
    p, _ = _pata()
    P.medir(p, 10_000 + 1_000, make_book("tok", [(0.45, 200)], [(0.55, 200)]))
    P.medir(p, 10_000 + 60_000, make_book("tok", [(0.30, 200)], [(0.40, 200)]))
    assert p.punto(1_000).contrafactual_pnl == pytest.approx(-0.5)
    assert p.punto(60_000).contrafactual_pnl == pytest.approx(-8.0)   # (0,30 − 0,46) × 50


# --------------------------------------------------------------------------- desenlace
def test_recuperar_la_segunda_pata_deja_el_tiempo_que_tardo():
    p, _ = _pata(t0=1_000)
    P.cerrar(p, 31_000, P.RECUPERADA, "both_filled", pnl_realizado=1.7, ts_segunda_pata=31_000)
    assert p.desenlace == P.RECUPERADA and p.time_to_second_leg_ms == 30_000
    assert p.pnl_realizado_final == 1.7


def test_una_pata_que_nunca_se_recupera_queda_marcada_como_tal():
    p, _ = _pata(t0=1_000)
    P.cerrar(p, 601_000, P.CADUCADA, "expired", pnl_realizado=-6.4)
    assert p.desenlace == P.CADUCADA and p.time_to_second_leg_ms is None
    assert p.duracion_ms == 600_000


def test_el_punto_de_no_retorno_solo_existe_si_hubo_perdida():
    p, _ = _pata()
    for h, bid in ((1_000, 0.45), (5_000, 0.44), (10_000, 0.42), (20_000, 0.40)):
        P.medir(p, 10_000 + h, make_book("tok", [(bid, 200)], [(bid + 0.10, 200)]))
    P.cerrar(p, 10_000 + 600_000, P.CADUCADA, "expired", pnl_realizado=-3.0)
    nr = P.punto_de_no_retorno(p)
    # la pérdida final es −3,00; el 25 % (−0,75) ya se alcanza en el primer punto (−0,50 no, −1,00 sí)
    assert nr["t_25pct_ms"] == 5_000
    assert nr["t_50pct_ms"] == 10_000          # −2,00 ≤ −1,50
    assert nr["t_90pct_ms"] == 20_000          # −3,00 ≤ −2,70
    # y si terminó ganando, no hay pérdida que fraccionar y no se inventa un número
    q, _ = _pata()
    P.cerrar(q, 20_000, P.RECUPERADA, "both_filled", pnl_realizado=1.7)
    assert all(v is None for v in P.punto_de_no_retorno(q).values())


def test_el_ahorro_hipotetico_se_llama_por_su_nombre():
    p, _ = _pata()
    P.medir(p, 10_000 + 1_000, make_book("tok", [(0.45, 200)], [(0.55, 200)]))
    P.cerrar(p, 10_000 + 600_000, P.CADUCADA, "expired", pnl_realizado=-6.4)
    # cerrar en T+1s habría costado −0,50 en vez de −6,40
    assert P.evitable(p, 1_000) == pytest.approx(5.9)
    assert P.evitable(p, 300_000) is None      # ese horizonte no se midió: no se rellena


# --------------------------------------------------------------------------- el motor
SI, NO = "c1-0", "c1-1"


def _engine_spread(cfg, tmp_path):
    cfg.data_dir = str(tmp_path)
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=1)
    eng = Engine(cfg, "r", "paper", w, experiment="exp-t")
    eng.set_markets([make_market("c1")])
    # Nuestras órdenes van a 0,46 (compra) y 0,54 (venta): nadie más en esos niveles, así que la
    # cola por delante es cero y el llenado depende solo del volumen que cruce.
    eng.books[SI] = make_book(SI, [(0.45, 200)], [(0.55, 200)], cid="c1")
    eng.books[NO] = make_book(NO, [(0.40, 200)], [(0.50, 200)], cid="c1")
    return eng, w


def _posicion(eng, ts=1_000):
    from scalper.signals.base import Leg, Signal
    from scalper.sim.ledger import Position

    s = Signal(ts, "spread_capture", "c1", "e1",
               [Leg(SI, "BUY", 0.46, 50, "maker"), Leg(NO, "SELL", 0.54, 50, "maker")],
               50, 0.02, 0.02, 0.0, 0.5, "mean_revert")
    s.strategy = "TENNIS_SPREAD_CAPTURE"
    pos = Position(signal=s, experiment="exp-t")
    eng.positions.append(pos)
    eng._place_makers(pos, ts)
    return pos


def test_el_motor_crea_la_pata_cuando_solo_se_llena_un_lado(cfg, tmp_path):
    eng, w = _engine_spread(cfg, tmp_path)
    pos = _posicion(eng)
    # solo se llena la primera pata
    eng.fill_model.maker_on_trade(pos.maker_orders[0],
                                  {"token_id": SI, "side": "SELL", "price": 0.46, "size": 50}, 2_000)
    eng._after_maker_fill(pos, 2_000)
    assert len(eng.patas) == 1
    pata = next(iter(eng.patas.values()))
    assert pata.t0_ms == 2_000 and pata.lado == "BUY" and pata.token_faltante == NO
    assert pata.partial_leg_id.startswith("pl-")
    assert pata.precio_entrada == pytest.approx(0.46)
    # T0 no es un punto de trayectoria: es la foto que va en la fila de la pata. El primer punto
    # medido no aparece hasta que vence el primer horizonte.
    assert pata.puntos == [] and pata.t0_salida_precio == 0.45
    eng._seguir_patas(2_000 + 1_000)
    assert [x.horizonte_ms for x in pata.puntos] == [1_000]
    w.flush()
    assert scan(tmp_path, "partial_leg_track") is not None


def test_si_se_llenan_las_dos_patas_no_hay_pata_suelta(cfg, tmp_path):
    eng, w = _engine_spread(cfg, tmp_path)
    pos = _posicion(eng)
    for o, trade in zip(pos.maker_orders,
                        ({"token_id": SI, "side": "SELL", "price": 0.46, "size": 50},
                         {"token_id": NO, "side": "BUY", "price": 0.54, "size": 50})):
        eng.fill_model.maker_on_trade(o, trade, 2_000)
    eng._after_maker_fill(pos, 2_000)
    assert eng.patas == {}
    assert pos.exit_reason == "both_filled"


def test_la_pata_que_se_recupera_guarda_cuanto_tardo(cfg, tmp_path):
    eng, w = _engine_spread(cfg, tmp_path)
    pos = _posicion(eng)
    eng.fill_model.maker_on_trade(pos.maker_orders[0],
                                  {"token_id": SI, "side": "SELL", "price": 0.46, "size": 50}, 2_000)
    eng._after_maker_fill(pos, 2_000)
    assert len(eng.patas) == 1
    # 30 s después llega la segunda
    eng.fill_model.maker_on_trade(pos.maker_orders[1],
                                  {"token_id": NO, "side": "BUY", "price": 0.54, "size": 50}, 32_000)
    eng._after_maker_fill(pos, 32_000)
    assert eng.patas == {} and len(eng.patas_cerradas) == 1
    pata = eng.patas_cerradas[0]
    assert pata.desenlace == P.RECUPERADA and pata.time_to_second_leg_ms == 30_000


def test_una_pata_que_caduca_queda_con_su_resultado_realizado_al_lado(cfg, tmp_path):
    eng, w = _engine_spread(cfg, tmp_path)
    pos = _posicion(eng)
    eng.fill_model.maker_on_trade(pos.maker_orders[0],
                                  {"token_id": SI, "side": "SELL", "price": 0.46, "size": 50}, 2_000)
    eng._after_maker_fill(pos, 2_000)
    eng._expire(2_000 + cfg.sim.max_hold_seconds * 1000 + 1)
    assert eng.patas == {} and len(eng.patas_cerradas) == 1
    pata = eng.patas_cerradas[0]
    assert pata.desenlace == P.CADUCADA
    assert pata.pnl_realizado_final is not None          # el real, al lado del hipotético
    assert pata.time_to_second_leg_ms is None            # nunca llegó
    # y la fila llega al disco con las dos cifras separadas
    w.flush()
    fila = scan(tmp_path, "partial_legs").collect().to_dicts()[0]
    assert fila["partial_leg_id"] == pata.partial_leg_id
    assert fila["desenlace"] == P.CADUCADA and fila["t0_ms"] == 2_000
    assert fila["pnl_realizado_final"] is not None       # realizado
    assert fila["t0_contrafactual_pnl"] is not None      # e hipotético, en columnas distintas


def test_las_patas_abiertas_al_cerrar_la_corrida_tambien_se_escriben(cfg, tmp_path):
    # Si la corrida termina antes que la posición, la pata no puede quedarse sin fila: se cerraría
    # su trayectoria sin desenlace y no habría forma de saber que existió.
    eng, w = _engine_spread(cfg, tmp_path)
    pos = _posicion(eng)
    eng.fill_model.maker_on_trade(pos.maker_orders[0],
                                  {"token_id": SI, "side": "SELL", "price": 0.46, "size": 50}, 2_000)
    eng._after_maker_fill(pos, 2_000)
    assert len(eng.patas) == 1
    eng.close_all(50_000, "end")
    assert eng.patas == {} and len(eng.patas_cerradas) == 1
    w.flush()
    assert scan(tmp_path, "partial_legs").collect().height == 1


def test_cada_punto_dice_cuanto_tarde_se_pudo_mirar_de_verdad():
    # El libro solo se observa cuando llega un evento. Un horizonte que vence entre dos eventos se
    # mide con el primero que llegue después, y eso hay que decirlo: un horizonte de 1 s medido
    # 800 ms tarde no es un horizonte de 1 s.
    p, libro = _pata(t0=10_000)
    P.medir(p, 11_800, libro)                       # el de 1 s vencía en 11_000
    x = p.punto(1_000)
    assert x.ts_ms == 11_000                        # el instante que pedía el horizonte
    assert x.ts_medido_ms == 11_800                 # cuándo se pudo mirar
    assert x.desfase_medicion_ms == 800


def test_el_camino_de_produccion_escribe_la_trayectoria_por_el_reloj(cfg, tmp_path):
    """De extremo a extremo por donde pasa de verdad: `tick`, no las funciones internas.

    En producción nadie llama a `_seguir_patas`: lo llama el reloj del motor una vez por segundo, y
    los eventos de libro. Si esa conexión se rompiera, los tests de unidad seguirían en verde y la
    corrida de ocho horas no mediría nada.
    """
    eng, w = _engine_spread(cfg, tmp_path)
    pos = _posicion(eng)
    eng.fill_model.maker_on_trade(pos.maker_orders[0],
                                  {"token_id": SI, "side": "SELL", "price": 0.46, "size": 50}, 2_000)
    eng._after_maker_fill(pos, 2_000)
    pata = next(iter(eng.patas.values()))

    # el precio se va en contra y el reloj avanza: la trayectoria tiene que aparecer sola
    eng.books[SI] = make_book(SI, [(0.40, 200)], [(0.50, 200)], cid="c1")
    for t in (2_000 + 1_000, 2_000 + 5_000, 2_000 + 10_000, 2_000 + 20_000):
        eng.tick(t)
    assert [x.horizonte_ms for x in pata.puntos] == [1_000, 5_000, 10_000, 20_000]
    assert all(x.contrafactual_pnl == pytest.approx(-3.0) for x in pata.puntos)   # (0,40 − 0,46) × 50

    w.flush()
    filas = scan(tmp_path, "partial_leg_track").collect().sort("horizonte_ms").to_dicts()
    assert [f["horizonte_ms"] for f in filas] == [1_000, 5_000, 10_000, 20_000]
    assert all(f["salida_precio"] == 0.40 for f in filas)          # del libro, no del mid (0,45)
    assert all(f["partial_leg_id"] == pata.partial_leg_id for f in filas)
    # y el motor lo cuenta en su resumen
    assert eng.summary()["patas_abiertas"] == 1


def test_la_estrategia_apagada_no_abre_nada_pero_deja_constancia(cfg, tmp_path):
    # TENNIS_DIRECTIONAL está apagada para esta fase. No es un veredicto: es no gastar muestra.
    # Pero la señal tiene que quedar registrada, o se pierde la cuenta de cuántas hubo.
    from scalper.storage import scan as leer

    cfg.data_dir = str(tmp_path)
    cfg.validacion.desactivadas = ["TENNIS_DIRECTIONAL"]
    eng, w = _engine_spread(cfg, tmp_path)
    assert "TENNIS_DIRECTIONAL" in eng._desactivadas
