"""Mercados "Up or Down" de cripto: modelo de difusión contra el precio del mercado.

Regla de oro aquí: **se compra y se aguanta hasta la resolución**. La comisión de cripto es
del 7 % y solo la paga quien cruza el libro; la resolución no cobra nada. Entrar y salir
pagaría dos veces y se comería cualquier ventaja, así que este detector nunca propone salida.
"""
from __future__ import annotations

from ..fees import taker_fee
from .base import Leg, MarketContext, Signal, planear_entrada


class UpDownDetector:
    kind = "updown_model"

    def __init__(self, min_edge_net: float, target_size: float, min_seconds_left: float = 45,
                 max_edge_net: float = 0.45, maker_first: bool = True):
        self.maker_first = maker_first
        self.min_edge_net = min_edge_net
        self.target_size = target_size
        self.min_seconds_left = min_seconds_left
        self.max_edge_net = max_edge_net

    def detect(self, ctx: MarketContext, ts_ms: int) -> list[Signal]:
        st, p_up = ctx.updown, ctx.updown_prob
        if st is None or p_up is None:
            return []
        if st.seconds_left < self.min_seconds_left:
            ctx.no_trade(self.kind, "tramo_final", seconds_left=st.seconds_left)
            return []
        m = ctx.market
        out: list[Signal] = []
        for tok in m.tokens:
            es_up = tok.outcome.lower() == "up"
            p_model = p_up if es_up else 1.0 - p_up
            b = ctx.book(tok.token_id)
            if b is None or not b.is_valid:
                continue
            if p_model - b.mid < self.min_edge_net / 2:
                continue                                 # ni siquiera es candidato
            lado = "up" if es_up else "down"
            e = planear_entrada(b, m, p_model, self.min_edge_net, self.target_size, self.maker_first)
            if e is None:
                ctx.no_trade(self.kind, "sin_precio_de_entrada", side=lado, p_model=p_model, mid=b.mid)
                continue
            entrada, size, fee = e.precio, e.size, e.fee_in
            edge_bruto = p_model - entrada
            edge_neto = edge_bruto - fee
            if edge_neto < self.min_edge_net:
                ctx.no_trade(self.kind, "edge_neto_insuficiente", side=lado, edge_net=edge_neto, p_model=p_model)
                continue
            if edge_neto > self.max_edge_net:
                ctx.no_trade(self.kind, "edge_implausible", side=lado, edge_net=edge_neto, strike=st.strike, spot=st.spot)
                continue
            edge_taker = None
            if e.taker_precio is not None:
                edge_taker = round(p_model - e.taker_precio - e.taker_fee_in, 5)
            conf = 0.35 + 0.45 * min(edge_neto / 0.15, 1.0)
            conf *= 0.7 + 0.3 * min(st.seconds_left / st.window_seconds, 1.0)
            mueve = (st.spot / st.strike - 1) * 10000 if st.strike else 0.0
            out.append(Signal(
                ts_ms=ts_ms, kind=self.kind, condition_id=m.condition_id, event_id=m.event_id,
                legs=[Leg(tok.token_id, "BUY", e.precio_limite, size, e.rol, tok.outcome)],
                size=size, edge_gross=edge_bruto, fee_est=fee, edge_net=edge_neto,
                confidence=round(max(0.05, min(conf, 0.95)), 3), horizon="resolution",
                meta={"entry_role": e.rol, "side": lado, "p_model": round(p_model, 4),
                      "edge_taker": edge_taker, "queue_ahead": round(e.queue_ahead, 2),
                      "edge_raw": round(edge_bruto, 5),
                      # conservadora: si hubiera que deshacer ya, se vende al bid pagando comisión
                      "edge_conservador": round(b.best_bid - entrada
                                                - taker_fee(size, b.best_bid, m.fee_rate) / size, 5),
                      "por_que": (f"Bitcoin va {mueve:+.0f} pb respecto a la apertura a {st.seconds_left:.0f} s del "
                                  f"cierre: el modelo da {p_model * 100:.0f} % a {lado.capitalize()} y el mercado "
                                  f"lo vende a {b.mid:.2f}."),
                      "p_market": round(b.mid, 4), "entry": round(entrada, 4), "symbol": st.symbol,
                      "strike": st.strike, "spot": st.spot, "seconds_left": round(st.seconds_left, 1),
                      "tau": round(st.tau, 4), "window_s": st.window_seconds,
                      "moneyness_bps": round((st.spot / st.strike - 1) * 10000, 2) if st.strike else None,
                      "sport": "crypto", "league": st.symbol,
                      # arrastre de la ventana anterior: así el ledger puede medir si el sesgo
                      # de apertura que deja la racha es información o sobrerreacción
                      "prev_up_won": (ctx.prev_window or {}).get("up_won"),
                      "prev_return_bps": (ctx.prev_window or {}).get("return_bps"),
                      "elapsed_s": round(st.window_seconds - st.seconds_left, 1),
                      "market_skew": round((b.mid - 0.5) * (1 if es_up else -1), 4)},
            ))
        return out
