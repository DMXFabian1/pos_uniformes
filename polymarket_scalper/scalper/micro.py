"""Microestructura: lo que el libro y el flujo dicen del próximo segundo, no del próximo partido.

Tres familias de medidas, todas calculadas en el instante de la señal y guardadas con ella:

1. **Forma del libro**: profundidad a 1, 2, 3 y 5 ticks de cada lado, y el desequilibrio a cada
   una de esas distancias. El desequilibrio del mejor nivel es ruidoso; a 3 o 5 ticks dice más.
2. **Flujo**: cuánto se puso y cuánto se quitó en cada lado (altas y bajas de nivel), la tasa de
   cancelación, y el flujo agresor (volumen comprador menos vendedor de los trades impresos).
3. **Velocidad**: cuánto se movió el mid en 250 ms, 1 s, 5 s, 15 s y 60 s, y su volatilidad.

Nada de esto decide por sí solo. Se guarda para que el modelo aprenda si sirve, y para que el
informe pueda decir si la señal llegó cuando el libro ya se estaba moviendo en contra.
"""
from __future__ import annotations

from typing import Any

from .book import OrderBook
from .signals.base import TokenHistory

TICKS = (1, 2, 3, 5)
VENTANAS_MS = (250, 1_000, 5_000, 15_000, 60_000)


def _en_ventana(serie, ts_ms: int, window_ms: int) -> list:
    lo = ts_ms - window_ms
    return [x for x in serie if x[0] >= lo]


def forma_libro(book: OrderBook) -> dict[str, float]:
    """Profundidad e imbalance a varias distancias del mejor precio."""
    out: dict[str, float] = {}
    if not book.is_valid:
        return {f"{k}_{t}t": 0.0 for t in TICKS for k in ("bid_depth", "ask_depth", "imbalance")}
    for t in TICKS:
        b = book.depth_within("BUY", t)
        a = book.depth_within("SELL", t)
        out[f"bid_depth_{t}t"] = round(b, 4)
        out[f"ask_depth_{t}t"] = round(a, 4)
        out[f"imbalance_{t}t"] = round(0.0 if a + b == 0 else (b - a) / (a + b), 5)
    return out


def flujo_ordenes(hist: TokenHistory, ts_ms: int, window_ms: int = 5_000) -> dict[str, float]:
    """Altas y bajas de nivel por lado en la ventana, y tasa de cancelación.

    `cancel_ratio` mezcla cancelaciones y llenados: el feed no los distingue. Lo que mide es
    cuánta de la liquidez que aparece desaparece sin dejar rastro de trade.
    """
    filas = _en_ventana(hist.flujo, ts_ms, window_ms)
    altas_bid = sum(d for _, s, d in filas if s.upper() == "BUY" and d > 0)
    bajas_bid = -sum(d for _, s, d in filas if s.upper() == "BUY" and d < 0)
    altas_ask = sum(d for _, s, d in filas if s.upper() != "BUY" and d > 0)
    bajas_ask = -sum(d for _, s, d in filas if s.upper() != "BUY" and d < 0)
    puesto = altas_bid + altas_ask
    quitado = bajas_bid + bajas_ask
    trades = _en_ventana(hist.trades, ts_ms, window_ms)
    volumen = sum(t[2] for t in trades)
    neto = (altas_bid - bajas_bid) - (altas_ask - bajas_ask)
    total = abs(altas_bid - bajas_bid) + abs(altas_ask - bajas_ask)
    return {
        "flow_bid_add": round(altas_bid, 4), "flow_bid_cancel": round(bajas_bid, 4),
        "flow_ask_add": round(altas_ask, 4), "flow_ask_cancel": round(bajas_ask, 4),
        "flow_net": round(neto, 4),
        "flow_net_ratio": round(neto / total, 5) if total > 0 else 0.0,
        "cancel_ratio": round(max(quitado - volumen, 0.0) / puesto, 5) if puesto > 0 else 0.0,
        "flow_updates": float(len(filas)),
    }


def flujo_agresor(hist: TokenHistory, ts_ms: int, window_ms: int = 5_000) -> dict[str, float]:
    """Volumen que cruzó comprando menos el que cruzó vendiendo, en la ventana."""
    trades = _en_ventana(hist.trades, ts_ms, window_ms)
    compra = sum(sz for _, _, sz, side in trades if str(side).upper() == "BUY")
    venta = sum(sz for _, _, sz, side in trades if str(side).upper() == "SELL")
    tot = compra + venta
    return {
        "aggr_buy": round(compra, 4), "aggr_sell": round(venta, 4),
        "aggr_imbalance": round((compra - venta) / tot, 5) if tot > 0 else 0.0,
        "trade_count": float(len(trades)), "trade_volume": round(tot, 4),
    }


def velocidad(hist: TokenHistory, ts_ms: int, ventanas: tuple[int, ...] = VENTANAS_MS) -> dict[str, float]:
    """Cambio del mid en cada ventana (USD) y volatilidad de los cambios en la más larga.

    El mid de referencia es el último observado **en o antes** del inicio de la ventana. Si no
    hay observación anterior, la ventana queda en 0: no se inventa un precio que no vimos.
    """
    mids = list(hist.mids)
    out: dict[str, float] = {}
    if not mids:
        return {f"vel_{_nombre(w)}": 0.0 for w in ventanas} | {"vel_vol_60s": 0.0}
    actual = mids[-1][1]
    for w in ventanas:
        corte = ts_ms - w
        previo = None
        for t, m in mids:
            if t <= corte:
                previo = m
            else:
                break
        out[f"vel_{_nombre(w)}"] = round(actual - previo, 6) if previo is not None else 0.0
    xs = [m for t, m in mids if t >= ts_ms - 60_000]
    if len(xs) >= 3:
        diffs = [b - a for a, b in zip(xs, xs[1:])]
        media = sum(diffs) / len(diffs)
        var = sum((d - media) ** 2 for d in diffs) / max(len(diffs) - 1, 1)
        out["vel_vol_60s"] = round(var ** 0.5, 6)
    else:
        out["vel_vol_60s"] = 0.0
    return out


def _nombre(ms: int) -> str:
    return f"{ms}ms" if ms < 1000 else f"{ms // 1000}s"


def instantanea(book: OrderBook | None, hist: TokenHistory | None, ts_ms: int) -> dict[str, Any]:
    """Todo junto, listo para adjuntar a la señal. Con libro o historia vacíos devuelve ceros."""
    hist = hist or TokenHistory()
    datos: dict[str, Any] = {}
    if book is not None:
        datos.update(forma_libro(book))
        datos["spread_ticks"] = book.spread_ticks or 0.0
        datos["mid"] = book.mid or 0.0
    datos.update(flujo_ordenes(hist, ts_ms))
    datos.update(flujo_agresor(hist, ts_ms))
    datos.update(velocidad(hist, ts_ms))
    return datos


# Nombres numéricos que el aprendizaje puede consumir directamente.
NOMBRES: list[str] = (
    [f"{k}_{t}t" for t in TICKS for k in ("bid_depth", "ask_depth", "imbalance")]
    + ["flow_bid_add", "flow_bid_cancel", "flow_ask_add", "flow_ask_cancel", "flow_net", "flow_net_ratio",
       "cancel_ratio", "flow_updates", "aggr_buy", "aggr_sell", "aggr_imbalance", "trade_count", "trade_volume"]
    + [f"vel_{_nombre(w)}" for w in VENTANAS_MS] + ["vel_vol_60s"]
)
