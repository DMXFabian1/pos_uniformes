"""La fase de medición: congelar el motor, marcar el dato sucio y seguir lo que pasa tras el fill."""
import json

import polars as pl

from scalper.experimento import congelar, diferencias, registrar, umbrales
from scalper.salud import (CONGELADO, DEGRADADO, SANO, VIEJO, bucket, corregir,
                          desfase_reloj, evaluar)
from scalper.sim.engine import Engine
from scalper.storage import ParquetWriter, scan
from conftest import make_market


def _game(gid="g1", score="0-0", period="", elapsed="", live=False, ended=False, league="nba"):
    return {"game_id": gid, "league": league, "sport": "", "home": "Lakers", "away": "Celtics", "status": "",
            "live": live, "ended": ended, "score": score, "period": period, "elapsed": elapsed}


def _nba(cfg, writer=None, experiment="exp-test"):
    cfg.sim.latency_ms = 100
    cfg.sim.slippage_ticks = 0
    cfg.sim.max_position_usd = 1000
    cfg.signals.spread.enabled = False
    cfg.signals.complement.enabled = False
    cfg.signals.maker_first = True
    m = make_market(fee=0.03, outcomes=("Lakers", "Celtics"))
    m.event_game_id = "g1"
    m.category = "nba"
    eng = Engine(cfg, "t", "replay", writer, experiment=experiment)
    eng.set_markets([m])
    h, a = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[h].apply_snapshot([{"price": 0.54, "size": 500}], [{"price": 0.56, "size": 500}], 1000)
    eng.books[a].apply_snapshot([{"price": 0.44, "size": 500}], [{"price": 0.46, "size": 500}], 1000)
    eng.on_game(1000, "g1", _game())
    eng.books[h].apply_snapshot([{"price": 0.69, "size": 120}], [{"price": 0.70, "size": 500}], 1500)
    eng.books[a].apply_snapshot([{"price": 0.29, "size": 500}], [{"price": 0.31, "size": 500}], 1500)
    return eng, m, h, a


def _llenar(eng, h, precio, ts=3000, size=170):
    eng.on_trade(ts, h, {"token_id": h, "price": precio, "size": size, "side": "SELL"})


# ------------------------------------------------------------------ congelar el motor
def test_la_huella_cambia_solo_si_cambia_algo_que_decide(cfg, tmp_path):
    cfg.data_dir = str(tmp_path)
    a = congelar(cfg)
    b = congelar(cfg)
    assert a.huella == b.huella and a.experiment_id == b.experiment_id
    cfg.signals.min_edge_net = 0.999
    c = congelar(cfg)
    assert c.huella != a.huella
    cambios = diferencias(umbrales_de(a), umbrales_de(c))
    assert any("min_edge_net" in x for x in cambios)


def umbrales_de(exp):
    return exp.umbrales


def test_el_experimento_se_registra_una_sola_vez(cfg, tmp_path):
    cfg.data_dir = str(tmp_path)
    exp = congelar(cfg, "primera")
    registrar(cfg, exp)
    registrar(cfg, exp)
    assert scan(tmp_path, "experiments").collect().height == 1
    cfg.sim.latency_ms = 999
    registrar(cfg, congelar(cfg, "otra"))
    assert scan(tmp_path, "experiments").collect().height == 2


def test_los_umbrales_capturan_lo_que_decide_y_no_las_urls(cfg):
    thr = umbrales(cfg)
    plano = json.dumps(thr)
    assert "min_edge_net" in plano and "maker_first" in plano and "latency_ms" in plano
    assert "ws_url" not in plano and "gamma_url" not in plano


# ------------------------------------------------------------------ salud del feed
def test_los_cuatro_estados_del_feed():
    assert evaluar(200, 0).estado == SANO
    assert evaluar(3000, 0).estado == DEGRADADO
    assert evaluar(9000, 0).estado == VIEJO
    assert evaluar(100, 20_000).estado == VIEJO          # llega fresco pero hace mucho que no llega nada
    assert evaluar(100, 90_000).estado == CONGELADO
    assert evaluar(200, 0).puede_operar and not evaluar(9000, 0).puede_operar
    assert evaluar(9000, 0).contaminado and not evaluar(3000, 0).contaminado


def test_los_tramos_de_frescura_cubren_todo():
    assert bucket(0) == "0-250ms" and bucket(249) == "0-250ms"
    assert bucket(250) == "250-500ms" and bucket(1500) == "1-2s"
    assert bucket(9999) == "5-10s" and bucket(60_000) == "10s+"
    assert bucket(None) == "desconocida"


def test_una_frescura_negativa_es_el_libro_mas_fresco_no_el_mas_viejo():
    # Con el reloj desfasado, `recv - ts` sale negativo. Antes no encajaba en ningún tramo y caía
    # en `10s+`: el dato recién llegado se contaba como el más rancio posible.
    assert bucket(-207) == "0-250ms"
    assert bucket(-1) == "0-250ms"


def test_el_desfase_de_reloj_se_estima_con_el_minimo_observado():
    # El mensaje que menos tardó es el que menos transporte lleva dentro: filtro de mínimo.
    assert desfase_reloj([-207, -98, -42, 846]) == -207.0
    # Un mínimo positivo es retraso de verdad: no hay desfase que descontar.
    assert desfase_reloj([120, 300, 900]) == 0.0
    assert desfase_reloj([]) == 0.0
    assert desfase_reloj([None, -50]) == -50.0


def test_descontado_el_desfase_la_frescura_es_relativa_al_suelo():
    # -207 es el suelo: pasa a valer 0 y cae en el primer tramo; -98 queda a 109 ms de él.
    assert corregir(-207, -207) == 0.0
    assert corregir(-98, -207) == 109.0
    assert bucket(-98, -207) == "0-250ms"
    assert bucket(846, -207) == "1-2s"
    # Nunca negativa: por debajo del suelo el mínimo es cero.
    assert corregir(-300, -207) == 0.0


def test_la_salud_se_guarda_cada_cierto_tiempo(cfg, tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    cfg.salud.registro_segundos = 10
    eng, m, h, a = _nba(cfg, writer=w)
    eng.registrar_salud(100_000, evaluar(300, 0))
    eng.registrar_salud(105_000, evaluar(300, 0))          # dentro del mismo tramo: no se repite
    eng.registrar_salud(115_000, evaluar(8000, 0))
    w.close()
    df = scan(tmp_path, "feed_health").collect()
    assert df.height == 2 and df["estado"].to_list() == [SANO, VIEJO]
    assert df["experiment"][0] == "exp-test"


# ------------------------------------------------------------------ lo que pasa tras el fill
def test_la_trayectoria_posterior_al_fill_se_guarda_por_horizonte(cfg, tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    cfg.sim.adverse_horizons_ms = [1000, 5000]
    cfg.validacion.horizontes_ms = [1000, 5000, 30_000]
    eng, m, h, a = _nba(cfg, writer=w)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    pos = eng.reales[0]
    precio = pos.signal.legs[0].price
    eng.tick(2100)
    _llenar(eng, h, precio)                                # mid al llenarse: 0.695
    eng.books[h].apply_snapshot([{"price": 0.72, "size": 500}], [{"price": 0.74, "size": 500}], 4000)
    eng.on_book(4000, h, eng.books[h])                     # +1 s → mid 0.73
    eng.books[h].apply_snapshot([{"price": 0.67, "size": 500}], [{"price": 0.69, "size": 500}], 8000)
    eng.on_book(8000, h, eng.books[h])                     # +5 s → mid 0.68
    eng.tick(40_000)
    w.close()
    df = scan(tmp_path, "post_fill").collect().sort("horizonte_ms")
    assert df["horizonte_ms"].to_list() == [1000, 5000, 30_000]
    assert abs(df["delta"][0] - 0.04) < 1e-9              # a 1 s el mid estaba 4 centavos por encima
    assert abs(df["delta"][1] - (-0.01)) < 1e-9           # a 5 s ya estaba por debajo
    assert df["entrada"][0] == precio and not df["sombra"][0]


def test_mfe_mae_y_tiempos_hasta_cada_movimiento(cfg):
    eng, m, h, a = _nba(cfg)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    pos = eng.reales[0]
    precio = pos.signal.legs[0].price                      # 0.69, mid de entrada 0.695
    eng.tick(2100)
    _llenar(eng, h, precio)
    eng.books[h].apply_snapshot([{"price": 0.71, "size": 500}], [{"price": 0.73, "size": 500}], 3500)
    eng.on_book(3500, h, eng.books[h])                     # mid 0.72: +3 centavos sobre la entrada
    eng.books[h].apply_snapshot([{"price": 0.64, "size": 500}], [{"price": 0.66, "size": 500}], 5000)
    eng.on_book(5000, h, eng.books[h])                     # mid 0.65: −4 centavos
    assert abs(pos.mfe - 0.03) < 1e-9 and pos.t_mfe_ms == 500
    assert abs(pos.mae - (-0.04)) < 1e-9 and pos.t_mae_ms == 2000
    assert pos.t_fav[1.0] == 500 and pos.t_fav[2.0] == 500      # 3 centavos cubren 1, 2 y 3 ticks
    assert pos.t_adv[1.0] == 2000 and 3.0 in pos.t_adv
    fila = pos.to_row("t", "replay")
    assert fila["t_fav_1t_ms"] == 500 and fila["t_adv_3t_ms"] == 2000
    assert abs(fila["mfe"] - 0.03) < 1e-9


def test_el_objetivo_y_el_stop_quedan_fechados_aunque_la_salida_sea_otra(cfg):
    eng, m, h, a = _nba(cfg)
    cfg.sim.time_stop_directional_seconds = 10**6
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    pos = eng.reales[0]
    precio = pos.signal.legs[0].price
    stop = pos.signal.meta["stop"]
    eng.tick(2100)
    _llenar(eng, h, precio)
    eng.books[h].apply_snapshot([{"price": stop - 0.01, "size": 500}], [{"price": stop + 0.05, "size": 500}], 4000)
    eng.on_book(4000, h, eng.books[h])
    assert pos.exit_reason == "stop" and pos.t_stop_ms == 1000
    fila = pos.to_row("t", "replay")
    assert fila["t_stop_ms"] == 1000 and fila["t_target_ms"] is None
    assert fila["target_antes_que_stop"] is False


# ------------------------------------------------------------------ condiciones de llenado
def test_cada_orden_puesta_deja_sus_condiciones_y_su_resultado(cfg, tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    eng, m, h, a = _nba(cfg, writer=w)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    pos = eng.reales[0]
    precio = pos.signal.legs[0].price
    eng.tick(2100)
    _llenar(eng, h, precio, ts=5000)
    eng.close_all(600_000)
    w.close()
    df = scan(tmp_path, "fill_observations").collect()
    assert df.height == 1
    r = df.to_dicts()[0]
    assert r["llenada"] and r["fraccion_llenada"] == 1.0 and r["espera_ms"] == 2900
    assert r["cola_delante"] == 120 and r["vol_cruzado"] == 170
    assert r["distancia_bid_ticks"] == 0.0 and r["distancia_ask_ticks"] == 1.0
    assert r["strategy"] == "NBA_DIRECTIONAL" and r["feed_state"] == SANO and not r["sombra"]
    assert r["profundidad_propia"] == 120 and r["spread_ticks"] == 1


def test_una_orden_que_no_se_llena_tambien_deja_su_fila(cfg, tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    cfg.signals.maker_entry_timeout_s = 5
    eng, m, h, a = _nba(cfg, writer=w)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    eng.tick(2100)
    eng.tick(20_000)
    w.close()
    r = scan(tmp_path, "fill_observations").collect().to_dicts()[0]
    assert not r["llenada"] and r["fraccion_llenada"] == 0.0 and r["espera_ms"] is None
    assert not r["llenada_conservador"] and not r["llenada_optimista"]


# ------------------------------------------------------------------ sombras
def test_una_senal_rechazada_se_sigue_como_sombra_sin_tocar_el_dinero(cfg, tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    eng, m, h, a = _nba(cfg, writer=w)
    eng.minimos = {"NBA_DIRECTIONAL": 9.0}                 # imposible: todo se rechaza
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    assert not eng.reales and len(eng.sombras) == 1
    pos = eng.sombras[0]
    assert pos.sombra and pos.motivo_rechazo == "bajo_el_minimo_requerido"
    efectivo = eng.cash
    eng.tick(2100)
    _llenar(eng, h, pos.signal.legs[0].price)
    eng.books[h].apply_snapshot([{"price": 0.98, "size": 500}], [{"price": 0.99, "size": 500}], 9000)
    eng.on_book(9000, h, eng.books[h])
    assert pos.status == "closed" and pos.realized_pnl > 0
    assert eng.cash == efectivo                            # la sombra ganó, pero no existe para la caja
    eng.close_all(600_000)
    w.close()
    df = scan(tmp_path, "ledger").collect()
    fila = df.filter(pl.col("sombra")).to_dicts()[0]
    assert fila["motivo_rechazo"] == "bajo_el_minimo_requerido" and fila["realized_pnl"] > 0
    assert eng.summary()["pnl"] == 0.0                     # el resumen no mezcla sombras con dinero


def test_una_sombra_no_bloquea_ni_ocupa_sitio(cfg):
    eng, m, h, a = _nba(cfg)
    eng.minimos = {"NBA_DIRECTIONAL": 9.0}
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    assert len(eng.sombras) == 1
    eng.minimos = {}                                       # ahora sí se puede operar
    eng.on_game(2400, "g1", _game(score="100-89", period="Q4", elapsed="05:50", live=True))
    assert len(eng.reales) == 1 and len(eng.sombras) == 1
    assert eng._abiertas() == 1


def test_el_tope_de_sombras_evita_que_se_desmadren(cfg):
    eng, m, h, a = _nba(cfg)
    cfg.validacion.max_sombras = 0
    eng.minimos = {"NBA_DIRECTIONAL": 9.0}
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    assert not eng.sombras and eng.stats["no_trade_bajo_el_minimo_requerido"] == 1


def test_la_decision_enlaza_con_la_sombra_por_el_id_de_la_senal(cfg, tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    eng, m, h, a = _nba(cfg, writer=w)
    eng.minimos = {"NBA_DIRECTIONAL": 9.0}
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    sombra = eng.sombras[0]
    w.close()
    d = scan(tmp_path, "decisions").collect().to_dicts()[0]
    assert d["signal_id"] == sombra.signal.signal_id and d["motivo"] == "bajo_el_minimo_requerido"
    assert d["experiment"] == "exp-test" and d["feed_state"] == SANO and not d["contaminado"]


def test_el_retraso_se_mide_sobre_los_mensajes_recientes_no_sobre_los_ultimos_n(cfg, monkeypatch):
    """El feed llega a ráfagas: con un recuento fijo, una ráfaga vieja contamina la medida."""
    from scalper import collector as mod

    col = mod.Collector(cfg, persist=False)
    ahora = 1_000_000_000
    monkeypatch.setattr(mod, "now_ms", lambda: ahora)
    # una ráfaga de hace un minuto con 60 s de retraso, y treinta mensajes recientes al día
    for i in range(500):
        col.latencias.append((ahora - 60_000 + i, 60_000))
    for i in range(30):
        col.latencias.append((ahora - 1_000 + i * 30, 120))
    lat = col.latencia()
    assert lat["mediana"] == 120 and lat["n"] == 30        # la ráfaga vieja queda fuera
    # y si en la ventana no hay casi nada, se usan los últimos de todos en vez de quedarse ciego
    col.latencias.clear()
    for i in range(40):
        col.latencias.append((ahora - 600_000 + i, 4_000))
    assert col.latencia()["mediana"] == 4_000


def test_la_captura_de_spread_marca_el_llenado_cuando_se_llena_no_al_poner(cfg, tmp_path):
    """ts_fill era el momento de poner la orden: daba esperas de cero y tiempos de tenencia falsos."""
    from conftest import make_book

    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    cfg.sim.latency_ms = 100
    cfg.sim.slippage_ticks = 0
    cfg.signals.complement.enabled = False
    cfg.sim.max_hold_seconds = 30
    m = make_market(fee=0.05)
    eng = Engine(cfg, "t", "replay", w, experiment="exp-test")
    eng.set_markets([m])
    y = m.tokens[0].token_id
    eng.books[y].apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    for i in range(10):
        eng.on_trade(1000 + i * 300, y, {"token_id": y, "price": 0.42, "size": 5, "side": "BUY"})
    pos = next(p for p in eng.reales if p.signal.kind == "spread_capture")
    eng.tick(4200)
    assert pos.ts_placed and pos.ts_fill == 0                 # puesta, todavía sin llenar
    eng.on_trade(9000, y, {"token_id": y, "price": 0.41, "size": 200, "side": "SELL"})
    assert pos.ts_fill == 9000
    eng.close_all(600_000)
    w.close()
    r = scan(tmp_path, "fill_observations").collect().to_dicts()[0]
    assert r["espera_ms"] == 9000 - pos.ts_placed and r["espera_ms"] > 0


def test_las_reacciones_llevan_la_corrida_y_el_experimento(cfg, tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    eng, m, h, a = _nba(cfg, writer=w)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    eng.on_game(5000, "g1", _game(score="103-88", period="Q4", elapsed="05:40", live=True))
    eng.books[h].apply_snapshot([{"price": 0.74, "size": 500}], [{"price": 0.76, "size": 500}], 7000)
    eng.on_book(7000, h, eng.books[h])
    eng.close_all(600_000)
    w.close()
    df = scan(tmp_path, "reactions").collect()
    assert df.height and set(df["experiment"].to_list()) == {"exp-test"}
    assert set(df["run_id"].to_list()) == {"t"}


def test_dos_experimentos_con_los_mismos_umbrales_deciden_igual():
    from scalper.experimento import cambios_que_deciden

    a = {"umbrales": '{"signals": {"min_edge_net": 0.01}}', "modelos": '{"spread": 3}'}
    assert cambios_que_deciden(a, dict(a)) == []
    b = {"umbrales": '{"signals": {"min_edge_net": 0.02}}', "modelos": '{"spread": 3}'}
    assert cambios_que_deciden(a, b) == ["signals.min_edge_net: 0.01 → 0.02"]
    # Un modelo promovido también cambia lo que decide.
    c = {"umbrales": a["umbrales"], "modelos": '{"spread": 4}'}
    assert cambios_que_deciden(a, c) == ["spread: 3 → 4"]
    # Si no se puede leer, no se inventa una respuesta.
    assert cambios_que_deciden(a, {"umbrales": "esto no es json", "modelos": "{}"}) is None
