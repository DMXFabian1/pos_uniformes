"""Seguir a wallets con historial (dinero inteligente), no a las grandes por tamaño.

Se dispara con un trade del flujo con identidad en un mercado seguido, si la wallet tiene
perfil con score y muestra suficientes, y el precio actual no se ha ido lejos de su entrada.
La ganancia esperada es una hipótesis basada en el ROI histórico de la wallet; el ledger dirá
cuánto vale realmente, por wallet y por deporte.
"""
from __future__ import annotations

from typing import Any

from ..fees import taker_fee
from .base import Leg, MarketContext, Signal, planear_entrada


class SmartMoneyDetector:
    kind = "smart_money"

    def __init__(self, min_edge_net: float, target_size: float, min_score: float = 0.65, min_closed: int = 20,
                 min_usd: float = 1000, max_chase_ticks: int = 3, edge_fraction_of_roi: float = 0.5,
                 max_price: float = 0.9, maker_first: bool = True):
        self.maker_first = maker_first
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
            ctx.no_trade(self.kind, "precio_ya_se_movio", wallet=flow.get("wallet"), their_price=their_px,
                         best_ask=b.best_ask)
            return []                                   # ya se movió: no perseguir
        # hipótesis: capturamos una fracción del ROI histórico de la wallet sobre el precio de entrada
        justo = their_px * (1 + max(prof.roi_adj, 0.0) * self.edge_fraction_of_roi)
        e = planear_entrada(b, m, justo, self.min_edge_net, self.target_size, self.maker_first)
        if e is None:
            ctx.no_trade(self.kind, "sin_precio_de_entrada", wallet=flow.get("wallet"), justo=justo, mid=b.mid)
            return []
        edge_gross = justo - e.precio
        exit_px = justo
        fee_out = taker_fee(e.size, exit_px, m.fee_rate) / e.size
        edge_net = edge_gross - e.fee_in - fee_out - (0 if self.maker_first else (b.spread or 0) / 2)
        if edge_net < self.min_edge_net:
            ctx.no_trade(self.kind, "edge_neto_insuficiente", wallet=flow.get("wallet"), edge_net=edge_net)
            return []
        edge_taker = None
        if e.taker_precio is not None:
            edge_taker = round(exit_px - e.taker_precio - e.taker_fee_in
                               - taker_fee(e.taker_size, exit_px, m.fee_rate) / e.taker_size - (b.spread or 0) / 2, 5)
        conf = min(0.95, prof.score * (0.6 + 0.4 * min(prof.n_closed / 200, 1.0)))
        nombre = flow.get("name") or str(flow.get("wallet", ""))[:10]
        return [Signal(
            ts_ms=ts_ms, kind=self.kind, condition_id=m.condition_id, event_id=m.event_id,
            legs=[Leg(tok.token_id, "BUY", e.precio_limite, e.size, e.rol, tok.outcome)],
            size=e.size, edge_gross=edge_gross, fee_est=e.fee_in + fee_out, edge_net=edge_net,
            confidence=round(conf, 3), horizon="directional",
            meta={"entry_role": e.rol, "wallet": flow.get("wallet"), "wallet_name": flow.get("name"), "wallet_score": prof.score,
                  "wallet_n": prof.n_closed, "wallet_roi": prof.roi, "their_price": their_px, "their_usd": flow.get("usd"),
                  "entry": round(e.precio, 4), "target": round(exit_px, 4),
                  "stop": round(max(e.precio - 2 * edge_net, 0.01), 4), "p_market": round(b.mid, 4),
                  "edge_taker": edge_taker, "queue_ahead": round(e.queue_ahead, 2),
                  "edge_raw": round(edge_gross, 5),
                  "edge_conservador": round(b.best_bid - e.precio - e.fee_in
                                            - taker_fee(e.size, b.best_bid, m.fee_rate) / e.size, 5),
                  "por_que": (f"La wallet {nombre} ({prof.n_closed} cierres, {prof.roi * 100:.0f} % de retorno) acaba de "
                              f"comprar a {their_px:.2f} y el precio sigue en {b.mid:.2f}: se entra antes de que el "
                              f"mercado la siga.")},
        )]
