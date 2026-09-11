"""Desvío entre el modelo de probabilidad en vivo y el precio del mercado.

Para cada token de un mercado enlazado a un partido en vivo con modelo disponible:
    p_model - entrada - fee(entrada) - costo estimado de salida  >  umbral  -> comprar ese token.
La salida se hace cuando el mercado converge al modelo (target), en el stop, al vencer el
time stop, o al terminar el partido. El ledger mide si el modelo tenía razón.

Todo candidato que se descarta queda anotado en `ctx.no_trade` con su motivo: sin eso no se
puede saber si los filtros son demasiado estrictos o demasiado laxos.
"""
from __future__ import annotations

from ..fees import taker_fee
from .base import Leg, MarketContext, Signal, planear_entrada


class ModelDeviationDetector:
    kind = "model_deviation"

    def __init__(self, min_edge_net: float, target_size: float, min_deviation: float = 0.04,
                 max_deviation: float = 0.35, stop_fraction: float = 1.5, min_tau: float = 0.02,
                 require_pregame: bool = False, maker_first: bool = True, max_event_risk: float = 1.0):
        self.maker_first = maker_first
        self.min_edge_net = min_edge_net
        self.target_size = target_size
        self.min_deviation = min_deviation
        self.max_deviation = max_deviation          # más que esto suele ser marcador mal parseado
        self.stop_fraction = stop_fraction          # stop = entrada - stop_fraction * edge
        self.min_tau = min_tau
        self.require_pregame = require_pregame
        self.max_event_risk = max_event_risk        # 1.0 = no filtra (hasta tener distribución medida)

    def detect(self, ctx: MarketContext, ts_ms: int) -> list[Signal]:
        g, wp = ctx.game, ctx.model_prob
        if g is None or wp is None or not g.live or g.ended:
            return []
        if self.require_pregame and ctx.pregame is None:
            return []
        tau = wp.detail.get("tau")
        if tau is not None and tau < self.min_tau:
            ctx.no_trade(self.kind, "partido_casi_terminado", tau=tau)
            return []
        m = ctx.market
        reaccion = ctx.reaction or {}
        riesgo = float(reaccion.get("event_risk_score") or 0.0)
        out: list[Signal] = []
        for tok in m.tokens:
            side = ctx.outcome_side.get(tok.token_id)
            if side is None:
                continue
            p_model = wp.for_side(side)
            b = ctx.book(tok.token_id)
            if b is None or not b.is_valid:
                continue
            desvio_mid = p_model - b.mid
            if desvio_mid < self.min_deviation / 2:
                continue                                 # ni siquiera es candidato: no se anota
            if desvio_mid > self.max_deviation:
                ctx.no_trade(self.kind, "desvio_implausible", side=side, p_model=p_model, mid=b.mid)
                continue
            if riesgo > self.max_event_risk:
                ctx.no_trade(self.kind, "riesgo_de_evento", side=side, event_risk_score=riesgo)
                continue
            e = planear_entrada(b, m, p_model, self.min_deviation, self.target_size, self.maker_first)
            if e is None:
                ctx.no_trade(self.kind, "sin_precio_de_entrada", side=side, p_model=p_model, mid=b.mid,
                             best_bid=b.best_bid, best_ask=b.best_ask)
                continue
            dev = p_model - e.precio
            if dev < self.min_deviation:
                ctx.no_trade(self.kind, "desvio_insuficiente", side=side, desvio=dev, p_model=p_model, entrada=e.precio)
                continue
            # salida: vender como taker cerca del modelo, pagando fee y medio spread
            exit_px = p_model - (b.spread or 0) / 2
            fee_out = taker_fee(e.size, exit_px, m.fee_rate) / e.size
            edge_net = exit_px - e.precio - e.fee_in - fee_out
            if edge_net < self.min_edge_net:
                ctx.no_trade(self.kind, "edge_neto_insuficiente", side=side, edge_net=edge_net, p_model=p_model,
                             entrada=e.precio)
                continue
            edge_taker = None
            if e.taker_precio is not None:
                edge_taker = round(exit_px - e.taker_precio - e.taker_fee_in
                                   - taker_fee(e.taker_size, exit_px, m.fee_rate) / e.taker_size, 5)
            conf = 0.3 + min(dev / 0.2, 1.0) * 0.4
            if ctx.pregame is None:
                conf *= 0.7
            if tau is not None:
                conf *= 0.6 + 0.4 * (1 - tau)          # más cerca del final, el modelo sabe más
            out.append(Signal(
                ts_ms=ts_ms, kind=self.kind, condition_id=m.condition_id, event_id=m.event_id,
                legs=[Leg(tok.token_id, "BUY", e.precio_limite, e.size, e.rol, tok.outcome)],
                size=e.size, edge_gross=dev, fee_est=e.fee_in + fee_out, edge_net=edge_net,
                confidence=round(max(0.05, min(conf, 0.95)), 3), horizon="directional",
                meta={"entry_role": e.rol, "side": side, "p_model": round(p_model, 4), "p_market": round(b.mid, 4),
                      "entry": round(e.precio, 4), "target": round(exit_px, 4),
                      "stop": round(max(e.precio - self.stop_fraction * edge_net, 0.01), 4),
                      "edge_taker": edge_taker, "queue_ahead": round(e.queue_ahead, 2),
                      "game_id": g.game_id, "sport": g.sport, "league": g.league, "model": wp.model,
                      "score": f"{g.home_score}-{g.away_score}", "period": g.period,
                      "pregame": round(ctx.pregame.for_side(side), 4) if ctx.pregame else None,
                      "event_risk_score": round(riesgo, 3),
                      "ms_since_event": reaccion.get("ms_since_event"),
                      "reaction_lag_ms": reaccion.get("typical_lag_ms"),
                      "por_que": _por_que(side, g, p_model, e.precio, reaccion),
                      **wp.detail},
            ))
        return out


def _por_que(side: str, g, p_model: float, entrada: float, reaccion: dict) -> str:
    """Una frase: por qué existe este trade (desalineación entre el estado del partido y el precio)."""
    lado = {"home": g.home, "away": g.away}.get(side, side)
    desde = reaccion.get("ms_since_event")
    hace = f" hace {desde / 1000:.0f} s" if isinstance(desde, (int, float)) else ""
    return (f"Con el marcador {g.home_score}-{g.away_score} ({g.period}) el modelo da {p_model * 100:.0f} % a {lado}; "
            f"el mercado sigue en {entrada:.2f}{hace}. Se compra antes de que el precio alcance al partido.")
