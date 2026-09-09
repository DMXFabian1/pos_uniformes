from scalper.fees import taker_fee, fee_rate_from_market
from conftest import make_book


def test_taker_fee_matches_polymarket_examples():
    assert taker_fee(100, 0.5, 0.04) == 1.0       # política, ejemplo de la doc
    assert taker_fee(100, 0.2, 0.04) == 0.64
    assert taker_fee(100, 0.5, 0.07) == 1.75      # cripto
    assert taker_fee(100, 0.3, 0.07) == 1.47
    assert taker_fee(100, 0.5, 0.0) == 0.0


def test_fee_rate_from_market_prefers_schedule():
    assert fee_rate_from_market({"feesEnabled": True, "feeSchedule": {"rate": 0.03}}, 0.05) == 0.03
    assert fee_rate_from_market({"feesEnabled": False}, 0.05) == 0.0
    assert fee_rate_from_market({"feesEnabled": True}, 0.05) == 0.05


def test_book_best_levels_regardless_of_input_order():
    b = make_book("t", bids=[(0.01, 100), (0.44, 50), (0.42, 10)], asks=[(0.99, 100), (0.45, 20), (0.47, 30)])
    assert b.best_bid == 0.44 and b.best_ask == 0.45
    assert b.spread_ticks == 1
    assert b.is_valid


def test_walk_buy_and_sell():
    b = make_book("t", bids=[(0.44, 50), (0.42, 10)], asks=[(0.45, 20), (0.47, 30)])
    w = b.walk_buy(30)
    assert w.shares == 30 and abs(w.notional - (20 * 0.45 + 10 * 0.47)) < 1e-9 and w.worst_price == 0.47
    w = b.walk_buy(100)
    assert w.shares == 50                         # solo hay 50 en el libro
    s = b.walk_sell(55)
    assert s.shares == 55 and abs(s.notional - (50 * 0.44 + 5 * 0.42)) < 1e-9


def test_delta_absolute_size_and_removal():
    b = make_book("t", bids=[(0.44, 50)], asks=[(0.45, 20)])
    b.apply_delta("BUY", 0.44, 70, 2000)
    assert b.bids[0.44] == 70
    b.apply_delta("BUY", 0.44, 0, 2001)
    assert 0.44 not in b.bids and b.best_bid is None
    b.apply_delta("SELL", 0.46, 5, 2002)
    assert b.asks[0.46] == 5


def test_depth_and_imbalance():
    b = make_book("t", bids=[(0.44, 50), (0.40, 100), (0.30, 999)], asks=[(0.45, 10), (0.50, 10)])
    assert b.depth_within("BUY", 5) == 150
    assert b.depth_within("SELL", 5) == 20
    assert abs(b.imbalance() - (50 - 10) / 60) < 1e-9
