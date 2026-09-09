import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from scalper.book import OrderBook
from scalper.config import Config
from scalper.discovery import MarketInfo, TokenInfo


@pytest.fixture
def cfg() -> Config:
    return Config.model_validate({"categories": {"sports": {"tag_id": 1, "default_fee_rate": 0.05}}})


def make_market(cid="0xabc", event_id="e1", fee=0.05, neg=False, outcomes=("Yes", "No"), tick=0.01) -> MarketInfo:
    toks = [TokenInfo(f"{cid}-{i}", o, i) for i, o in enumerate(outcomes)]
    return MarketInfo(condition_id=cid, gamma_id="1", question="q", slug="s", event_id=event_id, event_slug="es",
                      event_title="et", category="sports", tokens=toks, neg_risk=neg, event_neg_risk=neg,
                      tick_size=tick, min_order_size=5, fee_rate=fee, fee_type="sports_fees_v3", volume_24h=1e5,
                      liquidity=1e4, end_date="2030-01-01T00:00:00Z", accepting_orders=True,
                      sports_market_type="moneyline", game_start_time="")


def make_book(token_id, bids, asks, cid="0xabc", tick=0.01, ts=1000) -> OrderBook:
    b = OrderBook(token_id, cid, tick)
    b.apply_snapshot([{"price": p, "size": s} for p, s in bids], [{"price": p, "size": s} for p, s in asks], ts, "h")
    return b
