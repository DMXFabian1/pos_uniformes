"""Desvío entre el modelo de probabilidad en vivo y el precio del mercado.

Para cada token de un mercado enlazado a un partido en vivo con modelo disponible:
    p_model - ask - fee(entrada) - costo estimado de salida  >  umbral  -> comprar ese token.
La salida se hace cuando el mercado converge al modelo (target), en el stop, al vencer el
tiempo máximo, o al terminar el partido. El ledger mide si el modelo tenía razón.
"""
from __future__ import annotations

from ..fees import taker_fee
from .base import Leg, MarketContext, Signal, precio_maker


class ModelDeviationDetector:
    kind = "model_deviation"

    def __init__(self, min_edge_net: float, target_size: float, min_deviation: float = 0.04,
                 max_deviation: float = 0.35, stop_fraction: float = 1.5, min_tau: float = 0.02,
                 require_pregame: bool = False, maker_first: bool = True):
        self.maker_first = maker_first
        self.min_edge_net = min_edge_net
        self.target_size = target_size
        self.min_deviation = min_deviation
        self.max_deviation = max_deviation          # más que esto suele ser marcador mal parseado
        self.stop_fraction = stop_fraction          # stop = entrada - stop_fraction * edge
        self.min_tau = min_tau
        self.require_pregame = require_pregame

    def detect(self, ctx: MarketContext, ts_ms: int) -> list[Signal]:
        g, wp = ctx.game, ctx.model_prob
        if g is None or wp is None or not g.live or g.ended:
            return []
        if self.require_pregame and ctx.pregame is None:
            return []
        tau = wp.detail.get("tau")
        if tau is not None and tau < self.min_tau:
            return []
        m = ctx.market
        out: list[Signal] = []
        for tok in m.tokens:
            side = ctx.outcome_side.get(tok.token_id)
            if side is None:
                continue
            p_model = wp.for_side(side)
            b = ctx.book(tok.token_id)
            if b is None or not b.is_valid:
                continue
            if self.maker_first:
                entry = precio_maker(b, p_model, self.min_deviation)
                if entry is None:
                    continue
                size = max(self.target_size, m.min_order_size)
                fee_in = 0.0                                        # quien pone la orden no paga
                rol, precio_limite = "maker", entry
            else:
                w = b.walk_buy(self.target_size)
                size = w.shares
                if size < m.min_order_size:
                    continue
                entry = w.avg_price
                fee_in = taker_fee(size, entry, m.fee_rate) / size
                rol, precio_limite = "taker", w.worst_price
            dev = p_model - entry
            if dev < self.min_deviation or dev > self.max_deviation:
                continue
            # salida: vender como taker cerca del modelo, pagando fee y medio spread
            exit_px = p_model - (b.spread or 0) / 2
            fee_out = taker_fee(size, exit_px, m.fee_rate) / size
            edge_net = exit_px - entry - fee_in - fee_out
            if edge_net < self.min_edge_net:
                continue
            conf = 0.3 + min(dev / 0.2, 1.0) * 0.4
            if ctx.pregame is None:
                conf *= 0.7
            if tau is not None:
                conf *= 0.6 + 0.4 * (1 - tau)          # más cerca del final, el modelo sabe más
            out.append(Signal(
                ts_ms=ts_ms, kind=self.kind, condition_id=m.condition_id, event_id=m.event_id,
                legs=[Leg(tok.token_id, "BUY", precio_limite, size, rol, tok.outcome)],
                size=size, edge_gross=dev, fee_est=fee_in + fee_out, edge_net=edge_net,
                confidence=round(max(0.05, min(conf, 0.95)), 3), horizon="directional",
                meta={"entry_role": rol, "side": side, "p_model": round(p_model, 4), "p_market": round(b.mid, 4), "entry": round(entry, 4),
                      "target": round(exit_px, 4), "stop": round(max(entry - self.stop_fraction * edge_net, 0.01), 4),
                      "game_id": g.game_id, "sport": g.sport, "league": g.league, "model": wp.model,
                      "score": f"{g.home_score}-{g.away_score}", "period": g.period,
                      "pregame": round(ctx.pregame.for_side(side), 4) if ctx.pregame else None, **wp.detail},
            ))
        return out
