"""Arbitraje multi-resultado en eventos negRisk (exactamente un SÍ gana).

- multi_buy_all_yes: sum(ask_yes_i) + fees < 1        -> comprar todos los SÍ, uno paga 1.
- multi_buy_all_no:  sum(ask_no_i) + fees < (n - 1)   -> comprar todos los NO, n-1 pagan 1.
Requiere que TODOS los mercados del evento estén activos y con libro válido; si falta uno,
la cobertura no es completa y no es arbitraje.
"""
from __future__ import annotations

from ..fees import taker_fee
from .base import Leg, MarketContext, Signal


class MultiOutcomeDetector:
    kind = "multi_outcome"

    def __init__(self, min_edge_net: float, target_size: float, max_legs: int = 12):
        self.min_edge_net = min_edge_net
        self.target_size = target_size
        self.max_legs = max_legs

    def detect(self, ctx: MarketContext, ts_ms: int) -> list[Signal]:
        m = ctx.market
        sibs = ctx.event_markets
        if not m.event_neg_risk or m.event_neg_risk_augmented or len(sibs) < 3 or len(sibs) > self.max_legs:
            return []
        # cobertura: si no tenemos todos los mercados abiertos del evento, no es arbitraje
        if m.event_market_count and len(sibs) != m.event_market_count:
            return []
        if not m.event_market_count:
            return []
        # Solo evalúa una vez por evento: lo hace el mercado con menor condition_id
        if m.condition_id != min(s.condition_id for s in sibs):
            return []
        yes_books, no_books = [], []
        for s in sibs:
            if not s.is_binary:
                return []
            by, bn = ctx.event_books.get(s.yes_token.token_id), ctx.event_books.get(s.no_token.token_id)
            if by is None or bn is None or not by.is_valid or not bn.is_valid:
                return []
            yes_books.append((s, by))
            no_books.append((s, bn))
        out: list[Signal] = []
        n = len(sibs)
        min_size = max(s.min_order_size for s in sibs)

        # ---- todos los SÍ
        size = min(b.walk_buy(self.target_size).shares for _, b in yes_books)
        if size >= min_size:
            walks = [(s, b.walk_buy(size)) for s, b in yes_books]
            cost = sum(w.notional for _, w in walks)
            fees = sum(taker_fee(size, w.avg_price, s.fee_rate) for s, w in walks)
            edge_gross = (size - cost) / size
            edge_net = (size - cost - fees) / size
            if edge_net >= self.min_edge_net:
                out.append(Signal(
                    ts_ms=ts_ms, kind="multi_buy_all_yes", condition_id=m.condition_id, event_id=m.event_id,
                    legs=[Leg(s.yes_token.token_id, "BUY", w.worst_price, size, "taker", s.question[:60]) for s, w in walks],
                    size=size, edge_gross=edge_gross, fee_est=fees / size, edge_net=edge_net,
                    confidence=round(min(0.9, 0.3 + edge_net / 0.02 * 0.4 + 0.2 * (size / self.target_size)), 3),
                    horizon="resolution", meta={"n": n, "sum_asks": cost / size},
                ))

        # ---- todos los NO (pagan n-1)
        size = min(b.walk_buy(self.target_size).shares for _, b in no_books)
        if size >= min_size:
            walks = [(s, b.walk_buy(size)) for s, b in no_books]
            cost = sum(w.notional for _, w in walks)
            fees = sum(taker_fee(size, w.avg_price, s.fee_rate) for s, w in walks)
            payout = size * (n - 1)
            edge_gross = (payout - cost) / size
            edge_net = (payout - cost - fees) / size
            if edge_net >= self.min_edge_net:
                out.append(Signal(
                    ts_ms=ts_ms, kind="multi_buy_all_no", condition_id=m.condition_id, event_id=m.event_id,
                    legs=[Leg(s.no_token.token_id, "BUY", w.worst_price, size, "taker", s.question[:60]) for s, w in walks],
                    size=size, edge_gross=edge_gross, fee_est=fees / size, edge_net=edge_net,
                    confidence=round(min(0.9, 0.3 + edge_net / 0.02 * 0.4 + 0.2 * (size / self.target_size)), 3),
                    horizon="resolution", meta={"n": n, "sum_asks": cost / size, "payout_per_share": n - 1},
                ))
        return out
