"""Microestructura: valores exactos sobre libros y flujos sintéticos, sin sorpresas."""
from scalper.micro import NOMBRES, flujo_agresor, flujo_ordenes, forma_libro, instantanea, velocidad
from scalper.signals.base import TokenHistory
from scalper.sim.engine import Engine
from conftest import make_book, make_market


def _hist(flujo=(), trades=(), mids=()):
    h = TokenHistory()
    h.flujo.extend(flujo)
    h.trades.extend(trades)
    h.mids.extend(mids)
    return h


# ------------------------------------------------------------------ forma del libro
def test_profundidad_e_imbalance_a_varias_distancias():
    b = make_book("t", [(0.50, 10), (0.49, 20), (0.47, 40)], [(0.51, 5), (0.52, 5), (0.56, 100)])
    f = forma_libro(b)
    assert f["bid_depth_1t"] == 30 and f["bid_depth_2t"] == 30 and f["bid_depth_3t"] == 70
    assert f["ask_depth_1t"] == 10 and f["ask_depth_5t"] == 110
    assert f["imbalance_1t"] == round((30 - 10) / 40, 5)
    assert f["imbalance_5t"] == round((70 - 110) / 180, 5)      # a 5 ticks el libro pesa del lado vendedor


def test_libro_invalido_da_ceros_sin_reventar():
    from scalper.book import OrderBook
    f = forma_libro(OrderBook("t", "c", 0.01))
    assert set(f.values()) == {0.0} and "imbalance_3t" in f


# ------------------------------------------------------------------ flujo de órdenes
def test_altas_y_bajas_por_lado_y_tasa_de_cancelacion():
    # en el bid se ponen 100 y se quitan 60; de esos 60, 20 fueron por un trade impreso
    h = _hist(flujo=[(1000, "BUY", 100.0), (1500, "BUY", -60.0), (1800, "SELL", 40.0)],
              trades=[(1500, 0.50, 20.0, "SELL")])
    f = flujo_ordenes(h, 2000, 5000)
    assert f["flow_bid_add"] == 100 and f["flow_bid_cancel"] == 60 and f["flow_ask_add"] == 40
    assert f["flow_net"] == (100 - 60) - 40                       # el bid neto sube 40, el ask 40: neto 0
    assert f["cancel_ratio"] == round((60 - 20) / 140, 5)         # lo que desapareció sin trade
    assert f["flow_updates"] == 3


def test_la_ventana_excluye_lo_viejo():
    h = _hist(flujo=[(100, "BUY", 500.0), (9000, "BUY", 10.0)])
    assert flujo_ordenes(h, 10_000, 5_000)["flow_bid_add"] == 10


def test_flujo_agresor_separa_quien_cruza():
    h = _hist(trades=[(1000, 0.5, 30.0, "BUY"), (1200, 0.5, 10.0, "SELL")])
    f = flujo_agresor(h, 2000, 5000)
    assert f["aggr_buy"] == 30 and f["aggr_sell"] == 10 and f["aggr_imbalance"] == 0.5
    assert f["trade_count"] == 2 and f["trade_volume"] == 40


# ------------------------------------------------------------------ velocidad
def test_velocidad_usa_el_ultimo_mid_anterior_a_cada_ventana():
    mids = [(0, 0.50), (9_500, 0.52), (9_900, 0.53), (10_000, 0.55)]
    v = velocidad(_hist(mids=mids), 10_000)
    assert v["vel_250ms"] == round(0.55 - 0.52, 6)     # ventana desde 9 750: el último anterior es el de 9 500
    assert v["vel_1s"] == round(0.55 - 0.50, 6)        # desde 9 000: el último anterior es el de 0
    assert v["vel_60s"] == 0.0                          # no hay observación anterior a -50 s: no se inventa
    assert v["vel_vol_60s"] > 0


def test_velocidad_sin_historia_es_cero():
    v = velocidad(TokenHistory(), 1000)
    assert all(x == 0.0 for x in v.values())


# ------------------------------------------------------------------ integración
def test_instantanea_cubre_todos_los_nombres_declarados():
    b = make_book("t", [(0.50, 10)], [(0.52, 10)])
    h = _hist(flujo=[(900, "BUY", 5.0)], trades=[(950, 0.51, 3.0, "BUY")], mids=[(900, 0.50), (1000, 0.51)])
    datos = instantanea(b, h, 1000)
    faltan = [n for n in NOMBRES if n not in datos]
    assert not faltan


def test_el_motor_adjunta_la_microestructura_a_cada_senal(cfg):
    m = make_market(fee=0.0)
    cfg.sim.latency_ms = 100
    eng = Engine(cfg, "t", "replay")
    eng.set_markets([m])
    y, n = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[y].apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    eng.books[n].apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    eng.on_book(1000, y, eng.books[y])
    assert eng.positions
    micro = eng.positions[0].signal.meta["micro"]
    assert micro["bid_depth_5t"] == 100 and micro["spread_ticks"] == 5


def test_el_flujo_firmado_del_libro_llega_a_la_historia(cfg):
    m = make_market(fee=0.0)
    eng = Engine(cfg, "t", "replay")
    eng.set_markets([m])
    y = m.tokens[0].token_id
    b = eng.books[y]
    b.apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    cambio = b.apply_delta("BUY", 0.40, 70, 1100)
    eng.on_book(1100, y, b, {"side": "BUY", "price": 0.40, "size": 70, "delta": cambio})
    assert cambio == -30
    assert list(eng.history[y].flujo) == [(1100, "BUY", -30.0)]
    assert flujo_ordenes(eng.history[y], 1100, 5000)["flow_bid_cancel"] == 30
