from scalper.sim.engine import Engine
from scalper.sim.fill_model import FillModel, MakerOrder
from scalper.signals.base import Leg
from conftest import make_book, make_market


def _engine(cfg, markets):
    cfg.sim.latency_ms = 100
    cfg.sim.slippage_ticks = 0
    cfg.sim.fill_baseline_prob = 1.0
    cfg.signals.min_edge_net = 0.004
    eng = Engine(cfg, "test", "replay")
    eng.set_markets(markets)
    return eng


def test_taker_fill_walks_book_with_slippage_and_fee():
    fm = FillModel(slippage_ticks=1)
    b = make_book("t", [(0.40, 10)], [(0.45, 20), (0.47, 30)])
    f = fm.fill_taker(Leg("t", "BUY", 0.47, 30), b, 0.05, 1)
    assert f.shares == 30 and abs(f.notional - (20 * 0.45 + 10 * 0.47 + 30 * 0.01)) < 1e-9 and f.fee > 0
    f = fm.fill_taker(Leg("t", "SELL", 0.40, 50), b, 0.05, 1)
    assert f.shares == 10                                          # solo 10 en bids


def test_maker_fills_on_crossing_trade_and_queue():
    fm = FillModel(slippage_ticks=0)
    o = MakerOrder("t", "BUY", 0.41, 50, queue_ahead=20, ts_placed=0)
    assert fm.maker_on_trade(o, {"token_id": "t", "side": "BUY", "price": 0.41, "size": 100}, 1) == 0   # no cruza
    assert fm.maker_on_trade(o, {"token_id": "t", "side": "SELL", "price": 0.41, "size": 30}, 1) == 10  # 20 de cola
    assert fm.maker_on_trade(o, {"token_id": "t", "side": "SELL", "price": 0.40, "size": 100}, 2) == 40
    assert o.done
    o2 = MakerOrder("t", "SELL", 0.44, 10, 0, 0)
    b = make_book("t", [(0.45, 10)], [(0.46, 10)])                # el bid pasó por encima de nuestro ask
    assert fm.maker_on_book(o2, b, 3) == 10


def test_complement_arb_lifecycle_records_ledger(cfg):
    m = make_market(fee=0.0)
    eng = _engine(cfg, [m])
    y, n = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[y].apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    eng.books[n].apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    eng.on_book(1000, y, eng.books[y])
    assert len(eng.positions) == 1 and eng.positions[0].status == "pending"
    eng.tick(1200)                                                   # pasa la latencia
    assert not eng.reales and len(eng.closed) == 1
    p = eng.closed[0]
    assert p.exit_reason == "merge" and p.size_filled == 50
    assert abs(p.realized_pnl - 50 * 0.10) < 1e-9
    assert abs(p.realized_pnl - p.predicted_pnl) < 1e-9             # sin latencia real, sin error


def test_complement_arb_breaks_when_book_moves_during_latency(cfg):
    m = make_market(fee=0.0)
    eng = _engine(cfg, [m])
    y, n = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[y].apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    eng.books[n].apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    eng.on_book(1000, y, eng.books[y])
    # antes de ejecutar, el NO se encarece: el arb desaparece parcialmente
    eng.books[n].apply_delta("SELL", 0.45, 0, 1050)
    eng.books[n].apply_delta("SELL", 0.60, 100, 1050)
    eng.tick(1200)
    p = eng.closed[0]
    assert p.exit_reason == "merge"
    assert p.realized_pnl < p.predicted_pnl                          # error negativo registrado
    assert p.realized_pnl - p.predicted_pnl < -1


def test_spread_capture_both_sides_filled_and_expiry(cfg):
    m = make_market(fee=0.05)
    cfg.sim.max_hold_seconds = 10
    eng = _engine(cfg, [m])
    y = m.tokens[0].token_id
    eng.books[y].apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    # trades separados 300 ms para superar detect_interval_ms (250)
    for i in range(10):
        eng.on_trade(1000 + i * 300, y, {"token_id": y, "price": 0.42, "size": 5, "side": "BUY"})
    assert eng.positions and eng.positions[0].signal.kind == "spread_capture"
    t = 3700
    eng.tick(t + 200)
    pos = eng.positions[0]
    assert pos.status == "open" and len(pos.maker_orders) == 2
    size = pos.signal.size
    eng.on_trade(t + 300, y, {"token_id": y, "price": 0.41, "size": size, "side": "SELL"})   # nos llenan el bid
    assert pos.inventory[y] == size and pos.status == "open"
    eng.on_trade(t + 400, y, {"token_id": y, "price": 0.44, "size": size, "side": "BUY"})    # nos llenan el ask
    assert pos.status == "closed" and pos.exit_reason == "both_filled"
    assert abs(pos.realized_pnl - size * 0.03) < 1e-6

    # segundo ciclo: solo se llena un lado y expira -> se deshace como taker con fee
    t2 = 20_000
    for i in range(10):
        eng.on_trade(t2 + i * 300, y, {"token_id": y, "price": 0.42, "size": 5, "side": "BUY"})
    assert eng.positions
    eng.tick(t2 + 2700 + 200)
    pos2 = eng.positions[0]
    assert pos2.status == "open"
    eng.on_trade(t2 + 3000, y, {"token_id": y, "price": 0.41, "size": pos2.signal.size, "side": "SELL"})
    eng.tick(t2 + 3000 + 11_000)
    assert pos2.status == "closed" and pos2.exit_reason == "expired"
    assert pos2.realized_pnl < 0 and pos2.fees > 0


def test_risk_limits_scale_size_and_block_duplicates(cfg):
    m = make_market(fee=0.0)
    cfg.sim.max_position_usd = 9.0            # 0.9 USD por share de par -> 10 shares
    eng = _engine(cfg, [m])
    cfg.sim.latency_ms = 1000
    y, n = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[y].apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    eng.books[n].apply_snapshot([{"price": 0.40, "size": 100}], [{"price": 0.45, "size": 100}], 1000)
    eng.on_book(1000, y, eng.books[y])
    assert abs(eng.positions[0].signal.size - 10) < 1e-9
    eng.on_book(1300, n, eng.books[n])            # aún dentro de la latencia: la primera sigue pendiente
    assert len(eng.positions) == 1 and eng.stats["skipped_duplicate"] >= 1


def test_stuck_short_inventory_is_not_counted_as_profit(cfg):
    from scalper.sim.ledger import Position
    from scalper.signals.base import Signal
    m = make_market(fee=0.0)
    eng = _engine(cfg, [m])
    y = m.tokens[0].token_id
    sig = Signal(1, "spread_capture", m.condition_id, m.event_id,
                 [Leg(y, "BUY", 0.88, 50, "maker"), Leg(y, "SELL", 0.91, 50, "maker")], 50, 0.015, 0, 0.01, 0.5, "mean_revert")
    pos = Position(signal=sig, status="open", payout=45.5, inventory={y: -50})
    eng.positions.append(pos)
    eng.books[y].bids.clear(); eng.books[y].asks.clear()      # libro vacío: no se puede recomprar
    eng.close_all(10, "end")
    assert pos.exit_reason == "end_stuck"
    assert pos.realized_pnl <= 45.5 - 50 * 1.0 + 1e-9         # recompra valorada a 1.0 (peor caso)


def test_implausible_edge_is_discarded(cfg):
    m = make_market(fee=0.0)
    eng = _engine(cfg, [m])
    y, n = m.tokens[0].token_id, m.tokens[1].token_id
    eng.books[y].apply_snapshot([{"price": 0.01, "size": 100}], [{"price": 0.02, "size": 100}], 1000)
    eng.books[n].apply_snapshot([{"price": 0.01, "size": 100}], [{"price": 0.02, "size": 100}], 1000)
    eng.on_book(1000, y, eng.books[y])
    assert not eng.reales and eng.stats["skipped_edge_implausible"] == 1


def test_posicion_abierta_al_cerrar_se_valora_a_mercado_no_a_cero(cfg):
    """Cortar la corrida con una posición viva no es una pérdida: se valora a lo que vale."""
    from scalper.signals.base import Signal
    from scalper.sim.ledger import Position
    m = make_market(fee=0.0, outcomes=("Up", "Down"))
    eng = _engine(cfg, [m])
    up = m.tokens[0].token_id
    sig = Signal(1, "updown_model", m.condition_id, m.event_id,
                 [Leg(up, "BUY", 0.27, 50, "taker", "Up")], 50, 0.10, 0.0, 0.08, 0.6, "resolution")
    pos = Position(signal=sig, status="open", cost=13.5, fees=0.7, inventory={up: 50})
    eng.positions.append(pos)
    eng.books[up].apply_snapshot([{"price": 0.30, "size": 500}], [{"price": 0.32, "size": 500}], 1000)
    eng.on_book(1000, up, eng.books[up])
    eng.close_all(2000, "end")
    # con libro, simplemente se vende al mejor comprador
    assert pos.exit_reason == "end" and abs(pos.payout - 50 * 0.30) < 1e-9
    assert pos.realized_pnl > 0                                 # compró a 0.27 y vale 0.30

    # sin libro, se usa el último precio medio conocido en vez de dar todo por perdido
    pos2 = Position(signal=sig, status="open", cost=13.5, fees=0.7, inventory={up: 50})
    eng.positions.append(pos2)
    eng.books[up].bids.clear()
    eng.books[up].asks.clear()
    eng.close_all(3000, "end")
    assert pos2.exit_reason == "end_stuck"
    assert abs(pos2.payout - 50 * 0.31) < 1e-9                  # el mid que se vio antes
    assert pos2.realized_pnl > -14.2                            # muy lejos de dar todo por perdido
