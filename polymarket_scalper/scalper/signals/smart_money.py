"""Seguir a wallets con historial (dinero inteligente), no a las grandes por tamaño.

Se dispara con un trade del flujo con identidad en un mercado seguido, si la wallet tiene
perfil con score y muestra suficientes, y el precio actual no se ha ido lejos de su entrada.
La ganancia esperada es una hipótesis basada en el ROI histórico de la wallet; el ledger dirá
cuánto vale realmente, por wallet y por deporte.
"""
from __future__ import annotations

from typing import Any

from ..fees import taker_fee
from .base import Leg, MarketContext, Signal


class SmartMoneyDetector:
    kind = "smart_money"

    def __init__(self, min_edge_net: float, target_size: float, min_score: float = 0.65, min_closed: int = 20,
                 min_usd: float = 1000, max_chase_ticks: int = 3, edge_fraction_of_roi: float = 0.5,
                 max_price: float = 0.9):
        self.min_edge_net = min_edge_net
        self.target_size = target_size
        self.min_score = min_score
        self.min_closed = min_closed
        self.min_usd = min_usd
        self.max_chase_ticks = max_chase_ticks
        self.edge_fraction_of_roi = edge_fraction_of_roi
        self.max_price = max_price

    def detect(self, ctx: MarketContext, ts_ms: int) -> list[Signal]:
        return []

    def on_flow(self, ctx: MarketContext, flow: dict[str, Any], ts_ms: int) -> list[Signal]:
        if flow.get("side") != "BUY" or float(flow.get("usd") or 0) < self.min_usd:
            return []
        prof = ctx.wallet_profile(flow.get("wallet", ""))
        if prof is None or prof.n_closed < self.min_closed or prof.score < self.min_score:
            return []
        m = ctx.market
        tok = next((t for t in m.tokens if t.token_id == flow.get("token_id")), None)
        if tok is None:
            return []
        b = ctx.book(tok.token_id)
        if b is None or not b.is_valid:
            return []
        their_px = float(flow.get("price") or 0)
        if b.best_ask > their_px + self.max_chase_ticks * b.tick_size or b.best_ask > self.max_price:
            return []                                   # ya se movió: no perseguir
        w = b.walk_buy(self.target_size)
        size = w.shares
        if size < m.min_order_size:
            return []
        entry = w.avg_price
        fee_in = taker_fee(size, entry, m.fee_rate) / size
        # hipótesis: capturamos una fracción del ROI histórico de la wallet sobre el precio de entrada
        edge_gross = max(prof.roi_adj, 0.0) * self.edge_fraction_of_roi * entry
        exit_px = entry + edge_gross
        fee_out = taker_fee(size, exit_px, m.fee_rate) / size
        edge_net = edge_gross - fee_in - fee_out - (b.spread or 0) / 2
        if edge_net < self.min_edge_net:
            return []
        conf = min(0.95, prof.score * (0.6 + 0.4 * min(prof.n_closed / 200, 1.0)))
        return [Signal(
            ts_ms=ts_ms, kind=self.kind, condition_id=m.condition_id, event_id=m.event_id,
            legs=[Leg(tok.token_id, "BUY", w.worst_price, size, "taker", tok.outcome)],
            size=size, edge_gross=edge_gross, fee_est=fee_in + fee_out, edge_net=edge_net,
            confidence=round(conf, 3), horizon="directional",
            meta={"wallet": flow.get("wallet"), "wallet_name": flow.get("name"), "wallet_score": prof.score,
                  "wallet_n": prof.n_closed, "wallet_roi": prof.roi, "their_price": their_px, "their_usd": flow.get("usd"),
                  "entry": round(entry, 4), "target": round(exit_px, 4),
                  "stop": round(max(entry - 2 * edge_net, 0.01), 4), "p_market": round(b.mid, 4)},
        )]
