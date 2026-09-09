"""Modelo de ejecución simulada: fills taker contra el libro y fills maker por trades."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..book import OrderBook
from ..fees import taker_fee
from ..signals.base import Leg


@dataclass
class Fill:
    token_id: str
    side: str
    shares: float
    avg_price: float
    notional: float
    fee: float
    ts_ms: int
    role: str


@dataclass
class MakerOrder:
    token_id: str
    side: str
    price: float
    size: float
    queue_ahead: float
    ts_placed: int
    filled: float = 0.0
    fills: list[Fill] = field(default_factory=list)

    @property
    def remaining(self) -> float:
        return max(self.size - self.filled, 0.0)

    @property
    def done(self) -> bool:
        return self.remaining <= 1e-9


class FillModel:
    def __init__(self, slippage_ticks: int = 1, maker_fill_prob: float = 0.6, seed: int = 7):
        self.slippage_ticks = slippage_ticks
        self.maker_fill_prob = maker_fill_prob
        self.rng = random.Random(seed)

    # ------------------------------------------------------------ taker
    def fill_taker(self, leg: Leg, book: OrderBook, fee_rate: float, ts_ms: int, size: float | None = None) -> Fill:
        want = leg.size if size is None else size
        slip = self.slippage_ticks * book.tick_size
        if leg.side == "BUY":
            w = book.walk_buy(want)
            notional = w.notional + slip * w.shares
        else:
            w = book.walk_sell(want)
            notional = max(w.notional - slip * w.shares, 0.0)
        avg = notional / w.shares if w.shares > 0 else 0.0
        fee = taker_fee(w.shares, avg, fee_rate)
        return Fill(leg.token_id, leg.side, w.shares, avg, notional, fee, ts_ms, "taker")

    # ------------------------------------------------------------ maker
    def place_maker(self, leg: Leg, book: OrderBook, ts_ms: int) -> MakerOrder:
        levels = book.bids if leg.side == "BUY" else book.asks
        ahead = levels.get(leg.price, 0.0)
        return MakerOrder(leg.token_id, leg.side, leg.price, leg.size, ahead, ts_ms)

    def maker_on_trade(self, order: MakerOrder, trade: dict, ts_ms: int) -> float:
        """Devuelve shares llenados por este trade (0 si no aplica)."""
        if order.done or trade["token_id"] != order.token_id:
            return 0.0
        crosses = (order.side == "BUY" and trade["side"] == "SELL" and trade["price"] <= order.price + 1e-9) or \
                  (order.side == "SELL" and trade["side"] == "BUY" and trade["price"] >= order.price - 1e-9)
        if not crosses:
            return 0.0
        avail = float(trade["size"])
        if order.queue_ahead > 0:
            used = min(order.queue_ahead, avail)
            order.queue_ahead -= used
            avail -= used
        if avail <= 0 or self.rng.random() > self.maker_fill_prob:
            return 0.0
        got = min(order.remaining, avail)
        self._record(order, got, ts_ms)
        return got

    def maker_on_book(self, order: MakerOrder, book: OrderBook, ts_ms: int) -> float:
        """Si el mercado cruzó nuestro precio, nos llenaron todo (selección adversa)."""
        if order.done or book.token_id != order.token_id:
            return 0.0
        ba, bb = book.best_ask, book.best_bid
        crossed = (order.side == "BUY" and ba is not None and ba <= order.price + 1e-9) or \
                  (order.side == "SELL" and bb is not None and bb >= order.price - 1e-9)
        if not crossed:
            return 0.0
        got = order.remaining
        self._record(order, got, ts_ms)
        return got

    @staticmethod
    def _record(order: MakerOrder, shares: float, ts_ms: int) -> None:
        order.filled += shares
        order.fills.append(Fill(order.token_id, order.side, shares, order.price, shares * order.price, 0.0, ts_ms, "maker"))
