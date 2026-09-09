from scalper.signals.base import MarketContext, TokenHistory
from scalper.signals.complement import ComplementDetector
from scalper.signals.multi_outcome import MultiOutcomeDetector
from scalper.signals.spread import SpreadCaptureDetector
from conftest import make_book, make_market


def ctx_for(m, books, sibs=None, ebooks=None, hist=None):
    return MarketContext(m, books, hist or {}, sibs or [m], ebooks or books)


def test_complement_buy_detected_only_when_net_of_fees():
    m = make_market(fee=0.05)
    y, n = m.tokens[0].token_id, m.tokens[1].token_id
    # asks suman 0.96: bruto 0.04/share, fees ~2*0.05*0.48*0.52=0.025 -> neto ~0.015
    books = {y: make_book(y, [(0.40, 100)], [(0.48, 100)]), n: make_book(n, [(0.40, 100)], [(0.48, 100)])}
    sig = ComplementDetector(0.004, 50).detect(ctx_for(m, books), 5000)
    assert len(sig) == 1 and sig[0].kind == "complement_buy"
    s = sig[0]
    assert s.size == 50 and abs(s.edge_gross - 0.04) < 1e-9 and 0.01 < s.edge_net < 0.02
    # asks suman 0.99: bruto 0.01 pero fees lo comen
    books[y] = make_book(y, [(0.40, 100)], [(0.51, 100)])
    assert ComplementDetector(0.004, 50).detect(ctx_for(m, books), 5000) == []


def test_complement_sell_detected():
    m = make_market(fee=0.0)   # geopolítica: sin fee
    y, n = m.tokens[0].token_id, m.tokens[1].token_id
    books = {y: make_book(y, [(0.52, 100)], [(0.60, 100)]), n: make_book(n, [(0.50, 100)], [(0.60, 100)])}
    sig = ComplementDetector(0.004, 50).detect(ctx_for(m, books), 5000)
    assert [s.kind for s in sig] == ["complement_sell"]
    assert abs(sig[0].edge_net - 0.02) < 1e-9


def test_complement_size_limited_by_thinner_side():
    m = make_market(fee=0.0)
    y, n = m.tokens[0].token_id, m.tokens[1].token_id
    books = {y: make_book(y, [(0.40, 100)], [(0.45, 8)]), n: make_book(n, [(0.40, 100)], [(0.45, 100)])}
    sig = ComplementDetector(0.004, 50).detect(ctx_for(m, books), 5000)
    assert sig and sig[0].size == 8
    books[y] = make_book(y, [(0.40, 100)], [(0.45, 3)])   # menos que min_order_size
    assert ComplementDetector(0.004, 50).detect(ctx_for(m, books), 5000) == []


def test_multi_outcome_all_yes_and_all_no():
    sibs = [make_market(cid=f"0x{i}", event_id="ev", fee=0.0, neg=True) for i in range(3)]
    for s in sibs:
        s.event_market_count = 3
    ebooks = {}
    for s in sibs:
        ebooks[s.yes_token.token_id] = make_book(s.yes_token.token_id, [(0.20, 100)], [(0.30, 100)])
        ebooks[s.no_token.token_id] = make_book(s.no_token.token_id, [(0.60, 100)], [(0.62, 100)])
    det = MultiOutcomeDetector(0.004, 50)
    # solo el mercado con menor condition_id evalúa el evento
    assert det.detect(ctx_for(sibs[1], {}, sibs, ebooks), 1) == []
    sig = det.detect(ctx_for(sibs[0], {}, sibs, ebooks), 1)
    kinds = {s.kind: s for s in sig}
    assert "multi_buy_all_yes" in kinds and abs(kinds["multi_buy_all_yes"].edge_net - 0.10) < 1e-9
    assert "multi_buy_all_no" in kinds and abs(kinds["multi_buy_all_no"].edge_net - (2 - 1.86)) < 1e-9
    # si falta el libro de un hermano, no hay cobertura completa -> nada
    del ebooks[sibs[2].yes_token.token_id]
    assert det.detect(ctx_for(sibs[0], {}, sibs, ebooks), 1) == []


def test_multi_outcome_requires_full_event_coverage():
    sibs = [make_market(cid=f"0x{i}", event_id="ev", fee=0.0, neg=True) for i in range(3)]
    ebooks = {}
    for s in sibs:
        s.event_market_count = 18          # el evento tiene 18 mercados, solo vemos 3
        ebooks[s.yes_token.token_id] = make_book(s.yes_token.token_id, [(0.01, 100)], [(0.02, 100)])
        ebooks[s.no_token.token_id] = make_book(s.no_token.token_id, [(0.97, 100)], [(0.98, 100)])
    assert MultiOutcomeDetector(0.004, 50).detect(ctx_for(sibs[0], {}, sibs, ebooks), 1) == []
    for s in sibs:
        s.event_market_count = 3
        s.event_neg_risk_augmented = True  # pueden añadirse resultados: tampoco es arbitraje
    assert MultiOutcomeDetector(0.004, 50).detect(ctx_for(sibs[0], {}, sibs, ebooks), 1) == []


def test_spread_capture_requires_activity_and_width():
    m = make_market(fee=0.05)
    y = m.tokens[0].token_id
    books = {y: make_book(y, [(0.40, 100)], [(0.45, 100)]), m.tokens[1].token_id: make_book("x", [], [])}
    det = SpreadCaptureDetector(0.004, 50, min_spread_ticks=3, min_trades_per_minute=0.3)
    assert det.detect(ctx_for(m, books, hist={}), 600_000) == []          # sin trades
    h = TokenHistory()
    for i in range(10):
        h.trades.append((600_000 - i * 1000, 0.42, 10, "BUY"))
    sig = det.detect(ctx_for(m, books, hist={y: h}), 600_000)
    assert len(sig) == 1 and sig[0].kind == "spread_capture"
    s = sig[0]
    assert [l.side for l in s.legs] == ["BUY", "SELL"] and all(l.role == "maker" for l in s.legs)
    assert abs(s.legs[0].price - 0.41) < 1e-9 and abs(s.legs[1].price - 0.44) < 1e-9
    assert s.fee_est == 0.0 and s.edge_net > 0
    books[y] = make_book(y, [(0.44, 100)], [(0.45, 100)])                  # spread de 1 tick
    assert det.detect(ctx_for(m, books, hist={y: h}), 600_000) == []
