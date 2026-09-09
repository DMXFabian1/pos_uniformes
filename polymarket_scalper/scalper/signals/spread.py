"""Captura de spread como maker.

Si el spread es ancho y hay actividad, posteamos bid y ask dentro del spread. No pagamos fee.
Ganancia esperada por share = (ask_post - bid_post)/2 - selección adversa estimada
(volatilidad reciente del mid). Es la única señal con incertidumbre real: es donde el ledger
mide el error de predicción y donde luego entra el modelo aprendido.
"""
from __future__ import annotations

from .base import Leg, MarketContext, Signal, TokenHistory


class SpreadCaptureDetector:
    kind = "spread_capture"

    def __init__(self, min_edge_net: float, target_size: float, min_spread_ticks: int = 3,
                 min_trades_per_minute: float = 0.3, trade_window_seconds: int = 300, vol_window_seconds: int = 300):
        self.min_edge_net = min_edge_net
        self.target_size = target_size
        self.min_spread_ticks = min_spread_ticks
        self.min_tpm = min_trades_per_minute
        self.trade_window_ms = trade_window_seconds * 1000
        self.vol_window_ms = vol_window_seconds * 1000

    def detect(self, ctx: MarketContext, ts_ms: int) -> list[Signal]:
        out: list[Signal] = []
        m = ctx.market
        for tok in m.tokens:
            b = ctx.book(tok.token_id)
            if b is None or not b.is_valid:
                continue
            st = b.spread_ticks or 0
            if st < self.min_spread_ticks:
                continue
            hist = ctx.history.get(tok.token_id) or TokenHistory()
            trades = hist.trades_in(ts_ms, self.trade_window_ms)
            tpm = len(trades) / (self.trade_window_ms / 60000)
            if tpm < self.min_tpm:
                continue
            tick = b.tick_size
            bid_post = round(b.best_bid + tick, 6)
            ask_post = round(b.best_ask - tick, 6)
            if ask_post - bid_post < tick - 1e-9:
                continue
            vol = hist.mid_vol(ts_ms, self.vol_window_ms)
            half = (ask_post - bid_post) / 2
            adverse = max(vol, tick * 0.5)
            edge_net = half - adverse
            if edge_net < self.min_edge_net:
                continue
            size = min(self.target_size, max(b.best_bid_size, b.best_ask_size, m.min_order_size))
            size = max(size, m.min_order_size)
            imb = b.imbalance()
            # más actividad y menos volatilidad -> más confianza; desequilibrio fuerte la baja
            conf = 0.3 + 0.3 * min(tpm / 3, 1) + 0.3 * (1 - min(vol / max(half, 1e-9), 1)) - 0.2 * abs(imb)
            out.append(Signal(
                ts_ms=ts_ms, kind="spread_capture", condition_id=m.condition_id, event_id=m.event_id,
                legs=[Leg(tok.token_id, "BUY", bid_post, size, "maker", tok.outcome),
                      Leg(tok.token_id, "SELL", ask_post, size, "maker", tok.outcome)],
                size=size, edge_gross=half, fee_est=0.0, edge_net=edge_net,
                confidence=round(max(0.05, min(conf, 0.95)), 3), horizon="mean_revert",
                meta={"spread_ticks": st, "tpm": round(tpm, 3), "mid_vol": round(vol, 5), "imbalance": round(imb, 3),
                      "mid": b.mid, "best_bid": b.best_bid, "best_ask": b.best_ask},
            ))
        return out
