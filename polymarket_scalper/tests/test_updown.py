import math

from scalper.discovery import parse_updown_slug
from scalper.models.crypto import UpDownModel, UpDownState, calibrate_sigma, sigma_window
from scalper.signals.base import MarketContext
from scalper.signals.updown import UpDownDetector
from scalper.sim.engine import Engine
from conftest import make_book, make_market


def test_parse_slug():
    assert parse_updown_slug("btc-updown-5m-1789088700") == ("btc", 300, 1789088700000)
    assert parse_updown_slug("eth-updown-15m-1789088400") == ("eth", 900, 1789088400000)
    assert parse_updown_slug("sol-updown-1h-1000") == ("sol", 3600, 1000000)
    assert parse_updown_slug("btc-up-or-down-daily") is None
    assert parse_updown_slug("") is None


def test_diffusion_model_behaviour():
    m = UpDownModel()
    s5 = sigma_window(0.50, 5)
    assert 0.0014 < s5 < 0.0017                                   # ~0,15 % en 5 minutos
    en_el_dinero = UpDownState("btc", 113000, 113000, 300, 300)
    assert abs(m.prob_up(en_el_dinero) - 0.5) < 1e-9
    # una desviación estándar por encima a mitad de camino
    arriba = UpDownState("btc", 113000, 113000 * math.exp(s5 * math.sqrt(0.5)), 150, 300)
    assert abs(m.prob_up(arriba) - 0.8413) < 0.01
    # al expirar ya no hay incertidumbre
    assert m.prob_up(UpDownState("btc", 113000, 113001, 0, 300)) == 1.0
    assert m.prob_up(UpDownState("btc", 113000, 112999, 0, 300)) == 0.0
    # cuanto menos tiempo queda, más se acerca a 0 o 1 con el mismo movimiento
    spot = 113000 * 1.001
    ps = [m.prob_up(UpDownState("btc", 113000, spot, seg, 300)) for seg in (300, 150, 30)]
    assert ps[0] < ps[1] < ps[2]
    assert m.prob_up(UpDownState("btc", 0, 1, 60, 300)) is None     # sin strike no hay modelo


def test_calibrate_sigma_recovers_known_volatility():
    import random
    rng = random.Random(7)
    sigma_real = 0.002                        # por ventana de 300 s
    paso = sigma_real / math.sqrt(300)        # por segundo
    precio, serie = 100000.0, []
    for i in range(300 * 60):                 # 60 ventanas
        precio *= math.exp(rng.gauss(0, paso))
        serie.append((i * 1000, precio))
    r = calibrate_sigma(serie, 300)
    assert r["n"] >= 50 and abs(r["sigma_window"] - sigma_real) < 0.0006
    assert calibrate_sigma(serie[:5], 300) == {}


def _ctx(m, book_up, book_down, st, p_up):
    books = {m.tokens[0].token_id: book_up, m.tokens[1].token_id: book_down}
    return MarketContext(m, books, {}, [m], books, updown=st, updown_prob=p_up)


def test_detector_requires_edge_above_the_seven_percent_fee():
    m = make_market(fee=0.07, outcomes=("Up", "Down"))
    up, down = m.tokens[0].token_id, m.tokens[1].token_id
    st = UpDownState("btc", 113000, 113113, 150, 300)
    det = UpDownDetector(min_edge_net=0.03, target_size=50, min_seconds_left=45, maker_first=False)
    # modelo 0.82 contra ask 0.70: bruto 0.12, fee 0.07*0.7*0.3=0.0147 -> neto ~0.105
    sig = det.detect(_ctx(m, make_book(up, [(0.68, 500)], [(0.70, 500)]),
                          make_book(down, [(0.28, 500)], [(0.30, 500)]), st, 0.82), 1000)
    assert len(sig) == 1 and sig[0].kind == "updown_model"
    s = sig[0]
    assert s.meta["side"] == "up" and s.legs[0].side == "BUY" and len(s.legs) == 1
    assert s.horizon == "resolution"                       # se aguanta hasta la resolución
    assert abs(s.edge_gross - 0.12) < 1e-9 and 0.10 < s.edge_net < 0.11
    # mercado ya alineado con el modelo: sin ventaja, sin señal
    assert det.detect(_ctx(m, make_book(up, [(0.80, 500)], [(0.82, 500)]),
                           make_book(down, [(0.17, 500)], [(0.19, 500)]), st, 0.82), 1000) == []
    # ventaja pequeña que la comisión se come
    assert det.detect(_ctx(m, make_book(up, [(0.76, 500)], [(0.78, 500)]),
                           make_book(down, [(0.20, 500)], [(0.22, 500)]), st, 0.82), 1000) == []


def test_detector_skips_the_final_stretch_and_absurd_edges():
    m = make_market(fee=0.07, outcomes=("Up", "Down"))
    up, down = m.tokens[0].token_id, m.tokens[1].token_id
    bu = make_book(up, [(0.68, 500)], [(0.70, 500)])
    bd = make_book(down, [(0.28, 500)], [(0.30, 500)])
    st = UpDownState("btc", 113000, 113113, 150, 300)
    det = UpDownDetector(0.03, 50, min_seconds_left=45, max_edge_net=0.45, maker_first=False)
    assert det.detect(_ctx(m, bu, bd, UpDownState("btc", 113000, 113113, 20, 300), 0.82), 1) == []
    assert det.detect(_ctx(m, bu, bd, None, None), 1) == []
    # con p=0.999 la ventaja neta ronda 0.28: pasa el tope por defecto pero no uno estricto
    assert len(det.detect(_ctx(m, bu, bd, st, 0.999), 1)) == 1
    estricto = UpDownDetector(0.03, 50, min_seconds_left=45, max_edge_net=0.20, maker_first=False)
    assert estricto.detect(_ctx(m, bu, bd, st, 0.999), 1) == []


def test_engine_buys_holds_and_settles_at_expiry(cfg):
    cfg.sim.latency_ms = 100
    cfg.sim.slippage_ticks = 0
    cfg.sim.max_position_usd = 1000
    cfg.signals.spread.enabled = False
    cfg.signals.complement.enabled = False
    cfg.signals.maker_first = False              # este caso verifica la ruta que cruza el libro
    cfg.updown.min_edge_net = 0.03
    m = make_market(fee=0.07, outcomes=("Up", "Down"))
    m.slug = "btc-updown-5m-1000"
    eng = Engine(cfg, "t", "replay")
    eng.set_markets([m])
    up, down = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[up].apply_snapshot([{"price": 0.68, "size": 500}], [{"price": 0.70, "size": 500}], 1000)
    eng.books[down].apply_snapshot([{"price": 0.28, "size": 500}], [{"price": 0.30, "size": 500}], 1000)
    fin = 1000 + 150_000
    eng.on_updown(1000, m.condition_id, {"market": m, "strike": 113000.0, "strike_ts_ms": 0, "symbol": "btc",
                                         "start_ms": 1000 - 150_000, "end_ms": fin, "window_s": 300})
    eng.on_price(1400, "btc", {"price": 113113.0})       # tras el intervalo de detección
    assert eng.positions and eng.positions[0].signal.kind == "updown_model"
    sig = eng.positions[0].signal
    assert sig.meta["side"] == "up"
    eng.tick(1600)
    pos = eng.positions[0]
    assert pos.status == "open" and pos.inventory[up] == sig.size          # comprado y retenido
    coste, comision = pos.cost, pos.fees
    assert comision > 0
    # más precio no lo hace vender: aquí no se sale antes de tiempo
    eng.books[up].apply_snapshot([{"price": 0.96, "size": 500}], [{"price": 0.98, "size": 500}], 2500)
    eng.on_book(2500, up, eng.books[up])
    assert pos.status == "open" and pos.fees == comision
    eng.on_updown_settle(fin, m.condition_id, {"up_won": True, "winner_token": up, "settle_price": 113200.0})
    assert pos.status == "closed" and pos.exit_reason == "updown_settle"
    assert abs(pos.payout - sig.size) < 1e-9                                # 1 USD por share
    assert abs(pos.realized_pnl - (sig.size - coste - comision)) < 1e-9 and pos.realized_pnl > 0


def test_engine_settlement_when_the_model_was_wrong(cfg):
    cfg.sim.latency_ms = 100
    cfg.sim.slippage_ticks = 0
    cfg.sim.max_position_usd = 1000
    cfg.signals.spread.enabled = False
    cfg.signals.complement.enabled = False
    cfg.signals.maker_first = False
    m = make_market(fee=0.07, outcomes=("Up", "Down"))
    eng = Engine(cfg, "t", "replay")
    eng.set_markets([m])
    up, down = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[up].apply_snapshot([{"price": 0.68, "size": 500}], [{"price": 0.70, "size": 500}], 1000)
    eng.books[down].apply_snapshot([{"price": 0.28, "size": 500}], [{"price": 0.30, "size": 500}], 1000)
    fin = 1000 + 150_000
    eng.on_updown(1000, m.condition_id, {"market": m, "strike": 113000.0, "strike_ts_ms": 0, "symbol": "btc",
                                         "start_ms": 1000 - 150_000, "end_ms": fin, "window_s": 300})
    eng.on_price(1400, "btc", {"price": 113113.0})
    eng.tick(1600)
    pos = eng.positions[0]
    eng.on_updown_settle(fin, m.condition_id, {"up_won": False, "winner_token": down, "settle_price": 112900.0})
    assert pos.status == "closed" and pos.payout == 0.0 and pos.realized_pnl < 0
    assert abs(pos.realized_pnl + pos.cost + pos.fees) < 1e-9                # se pierde lo invertido


def test_collector_price_at_respects_tolerance(cfg, tmp_path):
    from scalper.collector import Collector
    cfg.data_dir = str(tmp_path)
    cfg.collector.prevent_sleep = False
    col = Collector(cfg, persist=False)
    for i in range(10):
        col.prices["btc"].append((1_000_000 + i * 1000, 113000 + i))
    assert col.price_at("btc", 1_005_000, 20) == (113005, 1_005_000)
    assert col.price_at("btc", 1_004_600, 20)[0] == 113005                # el más cercano
    assert col.price_at("btc", 1_100_000, 20) is None                     # fuera de tolerancia
    assert col.price_at("btc", 1_009_000 + 19_000, 20)[0] == 113009       # justo dentro
    assert col.price_at("eth", 1_000_005_000, 20) is None                 # símbolo sin datos


def test_strike_is_taken_at_or_after_the_window_opens(cfg, tmp_path):
    """Las ventanas se descubren por adelantado: el strike nunca puede ser anterior a la apertura."""
    from scalper.collector import Collector
    cfg.data_dir = str(tmp_path)
    cfg.collector.prevent_sleep = False
    col = Collector(cfg, persist=False)
    apertura = 1_000_000
    for t, p in ((apertura - 2000, 76910.0), (apertura - 200, 76905.0), (apertura + 800, 76877.0),
                 (apertura + 1800, 76880.0)):
        col.prices["btc"].append((t, p))
    # el más cercano devolvería un precio previo a la apertura: ese era el sesgo
    assert col.price_at("btc", apertura, 10) == (76905.0, apertura - 200)
    # el bueno es el primero en la apertura o después
    assert col.price_from("btc", apertura, 10) == (76877.0, apertura + 800)
    # si el primer dato posterior llega tarde, no hay strike
    assert col.price_from("btc", apertura, 0.5) is None
    # sin datos posteriores tampoco
    assert col.price_from("btc", apertura + 5000, 10) is None
