"""Arbitraje de complemento en mercados binarios.

- complement_buy:  ask_yes + ask_no + fees < 1  -> comprar ambos y fusionarlos (merge) por 1 USD.
- complement_sell: bid_yes + bid_no - fees > 1  -> partir 1 USD en SÍ+NO (mint) y vender ambos.
La ganancia es determinista una vez llenadas ambas patas; el riesgo es de ejecución.
"""
from __future__ import annotations

from ..fees import taker_fee
from .base import Leg, MarketContext, Signal


class ComplementDetector:
    kind = "complement"

    def __init__(self, min_edge_net: float, target_size: float):
        self.min_edge_net = min_edge_net
        self.target_size = target_size

    def detect(self, ctx: MarketContext, ts_ms: int) -> list[Signal]:
        m = ctx.market
        if not m.is_binary:
            return []
        by, bn = ctx.book(m.tokens[0].token_id), ctx.book(m.tokens[1].token_id)
        if by is None or bn is None or not by.is_valid or not bn.is_valid:
            return []
        out: list[Signal] = []
        rate = m.fee_rate

        # ---- comprar ambos
        wy, wn = by.walk_buy(self.target_size), bn.walk_buy(self.target_size)
        size = min(wy.shares, wn.shares)
        if size >= m.min_order_size:
            wy, wn = by.walk_buy(size), bn.walk_buy(size)
            cost = wy.notional + wn.notional
            fees = taker_fee(size, wy.avg_price, rate) + taker_fee(size, wn.avg_price, rate)
            edge_gross = (size - cost) / size
            edge_net = (size - cost - fees) / size
            if edge_net >= self.min_edge_net:
                out.append(Signal(
                    ts_ms=ts_ms, kind="complement_buy", condition_id=m.condition_id, event_id=m.event_id,
                    legs=[Leg(m.tokens[0].token_id, "BUY", wy.worst_price, size, "taker", m.tokens[0].outcome),
                          Leg(m.tokens[1].token_id, "BUY", wn.worst_price, size, "taker", m.tokens[1].outcome)],
                    size=size, edge_gross=edge_gross, fee_est=fees / size, edge_net=edge_net,
                    confidence=_conf(edge_net, size, self.target_size), horizon="merge",
                    meta={"ask_yes": by.best_ask, "ask_no": bn.best_ask, "avg_yes": wy.avg_price, "avg_no": wn.avg_price},
                ))

        # ---- vender ambos (mint + sell)
        sy, sn = by.walk_sell(self.target_size), bn.walk_sell(self.target_size)
        size = min(sy.shares, sn.shares)
        if size >= m.min_order_size:
            sy, sn = by.walk_sell(size), bn.walk_sell(size)
            proceeds = sy.notional + sn.notional
            fees = taker_fee(size, sy.avg_price, rate) + taker_fee(size, sn.avg_price, rate)
            edge_gross = (proceeds - size) / size
            edge_net = (proceeds - size - fees) / size
            if edge_net >= self.min_edge_net:
                out.append(Signal(
                    ts_ms=ts_ms, kind="complement_sell", condition_id=m.condition_id, event_id=m.event_id,
                    legs=[Leg(m.tokens[0].token_id, "SELL", sy.worst_price, size, "taker", m.tokens[0].outcome),
                          Leg(m.tokens[1].token_id, "SELL", sn.worst_price, size, "taker", m.tokens[1].outcome)],
                    size=size, edge_gross=edge_gross, fee_est=fees / size, edge_net=edge_net,
                    confidence=_conf(edge_net, size, self.target_size), horizon="mint",
                    meta={"bid_yes": by.best_bid, "bid_no": bn.best_bid, "avg_yes": sy.avg_price, "avg_no": sn.avg_price},
                ))
        return out


def _conf(edge_net: float, size: float, target: float) -> float:
    """Más edge y más profundidad -> más confianza de que la ejecución sobreviva la latencia."""
    e = min(edge_net / 0.02, 1.0)
    s = min(size / target, 1.0)
    return round(0.4 + 0.4 * e + 0.2 * s, 3)
