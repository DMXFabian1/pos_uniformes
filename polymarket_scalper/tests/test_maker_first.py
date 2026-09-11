"""El cambio de fondo: poner órdenes en vez de cruzar el libro.

La comisión de Polymarket solo la paga quien cruza. Poniendo la orden dentro del spread la
ventaja es entera; a cambio puede no llenarse, y eso es coste de oportunidad, no pérdida.
"""
from scalper.book import OrderBook
from scalper.models.crypto import UpDownState
from scalper.signals.base import MarketContext, precio_maker
from scalper.signals.updown import UpDownDetector
from scalper.sim.engine import Engine
from conftest import make_book, make_market


def _ctx(m, bu, bd, st, p_up):
    books = {m.tokens[0].token_id: bu, m.tokens[1].token_id: bd}
    return MarketContext(m, books, {}, [m], books, updown=st, updown_prob=p_up)


def _engine(cfg, markets):
    cfg.sim.latency_ms = 100
    cfg.sim.slippage_ticks = 0
    cfg.sim.max_position_usd = 1000
    cfg.signals.spread.enabled = False
    cfg.signals.complement.enabled = False
    cfg.signals.maker_first = True
    eng = Engine(cfg, "t", "replay")
    eng.set_markets(markets)
    return eng


# --------------------------------------------------------------- el precio límite
def test_el_precio_limite_nunca_cruza_y_respeta_la_ventaja():
    b = make_book("t", [(0.25, 500)], [(0.27, 500)])
    assert precio_maker(b, 0.37, 0.03) == 0.26            # mejora el bid sin tocar el ask
    assert precio_maker(b, 0.28, 0.03) == 0.25            # se une a la cola del mejor comprador
    assert precio_maker(b, 0.26, 0.03) is None            # habría que ponerse detrás: no compensa
    apretado = make_book("t", [(0.25, 500)], [(0.26, 500)])
    assert precio_maker(apretado, 0.40, 0.03) == 0.25     # con 1 tick de hueco, se une al bid
    vacio = OrderBook("t", "c", 0.01)
    assert precio_maker(vacio, 0.40, 0.03) is None


def test_poner_la_orden_da_mas_ventaja_que_cruzar_el_libro():
    """El mismo mercado, los dos modos: la diferencia es la comisión más el spread."""
    m = make_market(fee=0.07, outcomes=("Up", "Down"))
    up, down = m.tokens[0].token_id, m.tokens[1].token_id
    bu, bd = make_book(up, [(0.25, 500)], [(0.27, 500)]), make_book(down, [(0.71, 500)], [(0.73, 500)])
    st = UpDownState("btc", 113000, 113113, 150, 300)
    ctx = _ctx(m, bu, bd, st, 0.40)
    cruzando = UpDownDetector(0.03, 50, maker_first=False).detect(ctx, 1)[0]
    poniendo = UpDownDetector(0.03, 50, maker_first=True).detect(ctx, 1)[0]
    assert cruzando.legs[0].role == "taker" and poniendo.legs[0].role == "maker"
    assert cruzando.fee_est > 0 and poniendo.fee_est == 0.0          # quien pone no paga
    assert poniendo.edge_net > cruzando.edge_net
    assert poniendo.legs[0].price < cruzando.legs[0].price           # además compra más barato
    assert poniendo.meta["entry_role"] == "maker"


# --------------------------------------------------------------- el motor
def _senal_de_entrada(cfg, eng, m):
    """Bitcoin ya subió: el modelo ronda 0,79 y el mercado sigue pidiendo 0,62 por el Up."""
    up, down = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[up].apply_snapshot([{"price": 0.60, "size": 500}], [{"price": 0.62, "size": 500}], 1000)
    eng.books[down].apply_snapshot([{"price": 0.38, "size": 500}], [{"price": 0.40, "size": 500}], 1000)
    fin = 1000 + 200_000
    eng.on_updown(1000, m.condition_id, {"market": m, "strike": 113000.0, "strike_ts_ms": 0, "symbol": "btc",
                                         "start_ms": 1000 - 100_000, "end_ms": fin, "window_s": 300})
    eng.on_price(1400, "btc", {"price": 113113.0})
    return fin


def test_la_orden_se_pone_y_espera_sin_pagar_comision(cfg):
    m = make_market(fee=0.07, outcomes=("Up", "Down"))
    eng = _engine(cfg, [m])
    up = m.tokens[0].token_id
    _senal_de_entrada(cfg, eng, m)
    assert eng.positions and eng.positions[0].signal.legs[0].role == "maker"
    pos = eng.positions[0]
    precio = pos.signal.legs[0].price
    eng.tick(1600)
    assert pos.status == "open" and pos.entrada_maker is not None
    assert pos.size_filled == 0 and pos.cost == 0 and pos.fees == 0    # todavía no pasó nada
    # llega un vendedor que cruza nuestro precio: nos llenan
    eng.on_trade(1700, up, {"token_id": up, "price": precio, "size": pos.signal.size, "side": "SELL"})
    assert pos.size_filled == pos.signal.size
    assert abs(pos.cost - pos.signal.size * precio) < 1e-9
    assert pos.fees == 0.0                                             # la clave de todo el cambio
    assert pos.inventory[up] == pos.signal.size


def test_si_no_se_llena_se_cancela_sin_perder_nada(cfg):
    m = make_market(fee=0.07, outcomes=("Up", "Down"))
    cfg.signals.maker_entry_timeout_s = 5
    eng = _engine(cfg, [m])
    _senal_de_entrada(cfg, eng, m)
    pos = eng.positions[0]
    eng.tick(1600)
    assert pos.status == "open" and pos.entrada_maker is not None
    eng.tick(1600 + 6000)                                              # pasa el plazo sin que nadie cruce
    assert pos.status == "closed" and pos.exit_reason == "sin_llenar"
    assert pos.realized_pnl == 0.0 and pos.cost == 0.0 and pos.fees == 0.0
    assert eng.stats["entradas_maker_sin_llenar"] == 1


def test_llenada_y_liquidada_a_favor(cfg):
    m = make_market(fee=0.07, outcomes=("Up", "Down"))
    eng = _engine(cfg, [m])
    up = m.tokens[0].token_id
    fin = _senal_de_entrada(cfg, eng, m)
    pos = eng.positions[0]
    precio = pos.signal.legs[0].price
    eng.tick(1600)
    eng.on_trade(1700, up, {"token_id": up, "price": precio, "size": pos.signal.size, "side": "SELL"})
    eng.on_updown_settle(fin, m.condition_id, {"up_won": True, "winner_token": up, "settle_price": 113200.0})
    assert pos.status == "closed" and pos.exit_reason == "updown_settle"
    esperado = pos.signal.size * (1 - precio)                          # cobra 1 por share, sin comisión
    assert abs(pos.realized_pnl - esperado) < 1e-9 and pos.realized_pnl > 0


def test_si_la_ventana_cierra_sin_llenarnos_no_hay_perdida(cfg):
    m = make_market(fee=0.07, outcomes=("Up", "Down"))
    eng = _engine(cfg, [m])
    up = m.tokens[0].token_id
    fin = _senal_de_entrada(cfg, eng, m)
    pos = eng.positions[0]
    eng.tick(1600)
    eng.on_updown_settle(fin, m.condition_id, {"up_won": False, "winner_token": m.tokens[1].token_id,
                                               "settle_price": 112800.0})
    assert pos.status == "closed" and pos.exit_reason == "sin_llenar"
    assert pos.realized_pnl == 0.0                                     # el modelo falló y no costó nada


def test_si_el_mercado_baja_hasta_nuestro_precio_antes_de_poner_la_orden_se_descarta(cfg):
    m = make_market(fee=0.07, outcomes=("Up", "Down"))
    eng = _engine(cfg, [m])
    up = m.tokens[0].token_id
    _senal_de_entrada(cfg, eng, m)
    pos = eng.positions[0]
    # el ask se desploma por debajo de nuestro límite: ya no hay ventaja que poner
    eng.books[up].apply_snapshot([{"price": 0.10, "size": 500}], [{"price": 0.12, "size": 500}], 1500)
    eng.tick(1600)
    assert pos.status == "closed" and pos.exit_reason == "price_moved" and pos.realized_pnl == 0.0
