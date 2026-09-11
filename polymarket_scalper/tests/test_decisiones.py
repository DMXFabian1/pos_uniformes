"""Cada decisión queda registrada, incluidas las de NO operar; y la ejecución se mide, no se supone."""
import json

import polars as pl

from scalper.signals.base import strategy_id
from scalper.sim.engine import Engine
from scalper.storage import ParquetWriter, scan
from conftest import make_market


def _game(gid="g1", score="0-0", period="", elapsed="", live=False, ended=False, league="nba"):
    return {"game_id": gid, "league": league, "sport": "", "home": "Lakers", "away": "Celtics", "status": "",
            "live": live, "ended": ended, "score": score, "period": period, "elapsed": elapsed}


def _engine(cfg, markets, writer=None, maker_first=True):
    cfg.sim.latency_ms = 100
    cfg.sim.slippage_ticks = 0
    cfg.sim.max_position_usd = 1000
    cfg.signals.spread.enabled = False
    cfg.signals.complement.enabled = False
    cfg.signals.maker_first = maker_first
    eng = Engine(cfg, "t", "replay", writer)
    eng.set_markets(markets)
    return eng


def _nba(cfg, writer=None, maker_first=True):
    m = make_market(fee=0.03, outcomes=("Lakers", "Celtics"))
    m.event_game_id = "g1"
    m.category = "nba"
    eng = _engine(cfg, [m], writer, maker_first)
    h, a = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[h].apply_snapshot([{"price": 0.54, "size": 500}], [{"price": 0.56, "size": 500}], 1000)
    eng.books[a].apply_snapshot([{"price": 0.44, "size": 500}], [{"price": 0.46, "size": 500}], 1000)
    eng.on_game(1000, "g1", _game())
    # el hueco es de un tick: la orden se une al bid de 0.69, con 120 shares delante
    eng.books[h].apply_snapshot([{"price": 0.69, "size": 120}], [{"price": 0.70, "size": 500}], 1500)
    eng.books[a].apply_snapshot([{"price": 0.29, "size": 500}], [{"price": 0.31, "size": 500}], 1500)
    return eng, m, h, a


# ------------------------------------------------------------------ identificadores de estrategia
def test_strategy_id_separa_lo_que_no_debe_mezclarse():
    assert strategy_id("model_deviation", {"league": "nba", "sport": "basketball"}) == "NBA_DIRECTIONAL"
    assert strategy_id("model_deviation", {"league": "atp", "sport": "tennis"}) == "TENNIS_DIRECTIONAL"
    assert strategy_id("updown_model", {"window_s": 300}) == "CRYPTO_5M"
    assert strategy_id("updown_model", {"window_s": 900}) == "CRYPTO_15M"
    assert strategy_id("spread_capture", {}, "nba") == "NBA_SPREAD_CAPTURE"
    assert strategy_id("complement_buy", {}) == "ARBITRAGE" and strategy_id("multi_buy_all_yes", {}) == "ARBITRAGE"
    assert strategy_id("smart_money", {}) == "SMART_MONEY"


# ------------------------------------------------------------------ log de decisiones
def test_la_senal_y_su_por_que_llevan_estrategia_y_alternativa_taker(cfg):
    eng, m, h, a = _nba(cfg)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    assert eng.positions
    s = eng.positions[0].signal
    assert s.strategy == "NBA_DIRECTIONAL"
    assert s.meta["entry_role"] == "maker" and s.meta["edge_taker"] is not None
    assert s.meta["edge_taker"] < s.edge_net                  # cruzar el libro paga fee y spread
    assert s.legs[0].price == 0.69 and s.meta["queue_ahead"] == 120   # nos unimos al bid: 120 delante
    assert "Lakers" in s.meta["por_que"] and "100-88" in s.meta["por_que"]


def test_no_trade_queda_registrado_con_motivo_y_deduplicado(cfg, tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    eng, m, h, a = _nba(cfg, writer=w)
    cfg.signals.model_deviation.min_edge_net = 0.5            # imposible de cumplir: todo es NO TRADE
    eng.detectors = [d for d in eng.detectors if d.kind != "model_deviation"]
    from scalper.signals.model_deviation import ModelDeviationDetector
    eng.detectors.append(ModelDeviationDetector(0.5, 50, maker_first=True))
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    eng.on_game(2300, "g1", _game(score="100-89", period="Q4", elapsed="05:50", live=True))   # mismo motivo, < 30 s
    assert not eng.positions
    assert eng.stats["no_trade"] == 1 and eng.stats["no_trade_edge_neto_insuficiente"] == 1
    w.close()
    df = scan(tmp_path, "decisions").collect()
    assert df.height == 1
    r = df.to_dicts()[0]
    assert r["decision"] == "no_trade" and r["motivo"] == "edge_neto_insuficiente" and r["strategy"] == "NBA_DIRECTIONAL"
    assert json.loads(r["detalle"])["side"] == "home"


def test_la_decision_de_operar_tambien_se_registra(cfg, tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    eng, m, h, a = _nba(cfg, writer=w)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    w.close()
    df = scan(tmp_path, "decisions").collect()
    assert df.filter(pl.col("decision") == "trade").height == 1


def test_tope_de_exposicion_por_mercado_rechaza_y_lo_anota(cfg):
    from scalper.signals.base import Leg, Signal
    from scalper.sim.ledger import Position
    eng, m, h, a = _nba(cfg)
    cfg.sim.max_market_exposure_usd = 30
    # ya hay 35 USD comprometidos en este mercado por otra señal (50 shares a 0.70)
    otra = Signal(1900, "smart_money", m.condition_id, m.event_id, [Leg(h, "BUY", 0.70, 50, "maker")], 50,
                  0.05, 0.0, 0.05, 0.5, "directional", {"entry_role": "maker"})
    eng.positions.append(Position(signal=otra, exec_ts=10**12))
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    assert len(eng.positions) == 1 and eng.stats["no_trade_tope_exposicion"] == 1
    # y con tope holgado, sí entra, pero recortada al hueco que queda
    cfg.sim.max_market_exposure_usd = 50
    eng._ultima_decision.clear()
    eng.on_game(2300, "g1", _game(score="100-89", period="Q4", elapsed="05:50", live=True))
    assert len(eng.positions) == 2
    nueva = eng.positions[1].signal
    assert nueva.size * nueva.legs[0].price <= 15 + 1e-6


# ------------------------------------------------------------------ ejecución medida
def test_ledger_guarda_los_tres_escenarios_y_la_seleccion_adversa(cfg, tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    eng, m, h, a = _nba(cfg, writer=w)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    pos = eng.positions[0]
    precio = pos.signal.legs[0].price
    eng.tick(2100)
    assert pos.ts_placed == 2100 and pos.ts_fill == 0
    assert precio == 0.69
    # 120 delante en la cola; 170 cruzan: nos tocan 50 (BASE y CONSERVADOR); OPTIMISTA ya con los primeros
    eng.on_trade(3000, h, {"token_id": h, "price": precio, "size": 170, "side": "SELL"})
    assert pos.size_filled == 50 and pos.ts_fill == 3000 and pos.fees == 0
    # mid al llenarse: 0.695. A +1 s el mid sube a 0.73; a +5 s cae a 0.68; después no cambia
    eng.books[h].apply_snapshot([{"price": 0.72, "size": 500}], [{"price": 0.74, "size": 500}], 4000)
    eng.on_book(4000, h, eng.books[h])
    eng.books[h].apply_snapshot([{"price": 0.67, "size": 500}], [{"price": 0.69, "size": 500}], 8000)
    eng.on_book(8000, h, eng.books[h])
    eng.tick(14_000)
    esperado = {100: 0.005, 500: 0.005, 1000: 0.04, 2000: 0.04, 5000: -0.01, 10000: -0.01}
    for hz, v in esperado.items():
        assert abs(pos.adverse[hz] - v) < 1e-9, (hz, pos.adverse[hz])
    eng.close_all(20_000)
    w.close()
    df = scan(tmp_path, "ledger").collect()
    r = df.to_dicts()[0]
    assert r["strategy"] == "NBA_DIRECTIONAL" and r["entry_role"] == "maker"
    assert r["fill_conservador"] == 50 and r["fill_optimista"] == 50 and r["queue_inicial"] == 120
    assert r["vol_cruzado"] == 170 and r["barrido"] is False
    assert abs(r["adverse_1s"] - 0.04) < 1e-9 and abs(r["adverse_100ms"] - 0.005) < 1e-9
    assert r["ts_placed"] == 2100 and r["ts_fill"] == 3000


def test_una_salida_rapida_espera_a_completar_las_marcas_antes_de_ir_al_ledger(cfg, tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    eng, m, h, a = _nba(cfg, writer=w)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    pos = eng.positions[0]
    precio = pos.signal.legs[0].price
    eng.tick(2100)
    eng.on_trade(3000, h, {"token_id": h, "price": precio, "size": 500, "side": "SELL"})
    eng.books[h].apply_snapshot([{"price": 0.98, "size": 500}], [{"price": 0.99, "size": 500}], 3500)
    eng.on_book(3500, h, eng.books[h])                        # target a los 500 ms
    assert pos.status == "closed" and pos.exit_reason == "target"
    assert pos in eng._por_escribir                            # todavía no está en el ledger
    eng.tick(3600)
    eng.tick(13_500)                                           # +10 s: ya puede escribirse
    assert pos not in eng._por_escribir
    w.close()
    assert scan(tmp_path, "ledger").collect().height == 1


def test_time_stop_saca_la_posicion_que_no_convergio(cfg):
    eng, m, h, a = _nba(cfg)
    cfg.sim.time_stop_directional_seconds = 60
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    pos = eng.positions[0]
    precio = pos.signal.legs[0].price
    eng.tick(2100)
    eng.on_trade(3000, h, {"token_id": h, "price": precio, "size": 500, "side": "SELL"})
    eng.tick(3000 + 59_000)
    assert pos.status == "open"
    eng.tick(3000 + 61_000)
    assert pos.status == "closed" and pos.exit_reason == "time_stop"
    assert abs(pos.to_row("t", "replay")["hold_s"] - 61.0) < 1e-9


def test_el_stop_mira_el_bid_no_el_mid(cfg):
    eng, m, h, a = _nba(cfg)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    pos = eng.positions[0]
    precio, stop = pos.signal.legs[0].price, pos.signal.meta["stop"]
    eng.tick(2100)
    eng.on_trade(3000, h, {"token_id": h, "price": precio, "size": 500, "side": "SELL"})
    # mid por encima del stop pero bid por debajo: lo que se cobraría es el bid → stop
    eng.books[h].apply_snapshot([{"price": stop - 0.01, "size": 500}], [{"price": stop + 0.05, "size": 500}], 4000)
    eng.on_book(4000, h, eng.books[h])
    assert pos.status == "closed" and pos.exit_reason == "stop"


def test_las_reacciones_del_mercado_se_persisten(cfg, tmp_path):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    eng, m, h, a = _nba(cfg, writer=w)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    eng.on_game(5000, "g1", _game(score="103-88", period="Q4", elapsed="05:40", live=True))
    eng.books[h].apply_snapshot([{"price": 0.74, "size": 500}], [{"price": 0.76, "size": 500}], 7000)
    eng.on_book(7000, h, eng.books[h])
    eng.close_all(100_000)
    w.close()
    df = scan(tmp_path, "reactions").collect()
    ok = df.filter(pl.col("reacciono"))
    assert ok.height >= 1
    fila = ok.filter(pl.col("token_id") == h).sort("ts_evento").to_dicts()[-1]
    assert fila["evento"] == "marcador" and fila["lag_ms"] == 2000 and fila["league"] == "nba"
    assert eng.stats["reacciones"] >= 1


def test_el_motor_rechaza_lo_que_no_llega_al_minimo_medido(cfg):
    """Filtro global de NO TRADE: por debajo de lo que la estrategia necesita, no se entra."""
    eng, m, h, a = _nba(cfg)
    eng.on_game(2000, "g1", _game(score="100-88", period="Q4", elapsed="06:00", live=True))
    edge = eng.positions[0].signal.edge_net
    eng.positions.clear()
    eng._ultima_decision.clear()
    eng.minimos = {"NBA_DIRECTIONAL": edge + 0.01}          # como si el ledger pidiera más
    eng.on_game(2400, "g1", _game(score="100-89", period="Q4", elapsed="05:50", live=True))
    assert not eng.positions
    assert eng.stats["skipped_bajo_minimo"] == 1 and eng.stats["no_trade_bajo_el_minimo_requerido"] == 1


def test_sin_muestra_suficiente_el_minimo_no_filtra(cfg, tmp_path):
    """El mínimo solo existe con al menos 20 posiciones cerradas: con menos filtraría por ruido."""
    from scalper.evaluacion import minimos_requeridos
    from scalper.storage import ParquetWriter
    from test_evaluacion import _fila

    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    for i in range(19):
        w.append("ledger", _fila(i, strategy="NBA_DIRECTIONAL"))
    w.close()
    assert minimos_requeridos(tmp_path) == {}
    w2 = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    w2.append("ledger", _fila(19, strategy="NBA_DIRECTIONAL"))
    w2.close()
    assert "NBA_DIRECTIONAL" in minimos_requeridos(tmp_path)
