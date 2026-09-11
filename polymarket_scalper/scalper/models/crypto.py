"""Modelo para mercados "Up or Down" de cripto.

El mercado paga SÍ ("Up") si el precio al cierre supera al de apertura. Con el precio de
referencia en vivo, la probabilidad es la de que un movimiento browniano que ahora vale
ln(S/K) termine por encima de cero:

    P(Up) = Φ( ln(S/K) / (σ·√τ) )

- S: precio ahora, K: precio de apertura (strike), τ: fracción de la ventana que falta
- σ: desviación del rendimiento logarítmico en una ventana completa. Se calibra con los
  propios datos (`scalper calibrate --crypto`); el valor por defecto sale de una volatilidad
  anualizada del 50 %, que es lo típico de BTC.

Sin deriva a propósito: en 5 minutos la tendencia es ruido frente a la volatilidad, y meterla
solo añade una forma de equivocarse.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .basketball import phi

MINUTES_PER_YEAR = 365 * 24 * 60


def sigma_window(annual_vol: float, window_minutes: float) -> float:
    """Desviación del rendimiento logarítmico en una ventana de N minutos."""
    return annual_vol * math.sqrt(window_minutes / MINUTES_PER_YEAR)


DEFAULT_ANNUAL_VOL = {"btc": 0.50, "eth": 0.65, "sol": 0.85, "xrp": 0.80, "doge": 0.95, "bnb": 0.55}


@dataclass
class UpDownState:
    symbol: str
    strike: float          # precio de apertura de la ventana
    spot: float            # precio ahora
    seconds_left: float
    window_seconds: float
    spot_ts_ms: int = 0

    @property
    def tau(self) -> float:
        return max(0.0, min(1.0, self.seconds_left / self.window_seconds)) if self.window_seconds > 0 else 0.0


class UpDownModel:
    name = "diffusion"

    def __init__(self, annual_vol: dict[str, float] | None = None, default_annual_vol: float = 0.6):
        self.annual_vol = dict(DEFAULT_ANNUAL_VOL)
        if annual_vol:
            self.annual_vol.update(annual_vol)
        self.default = default_annual_vol

    def sigma_for(self, symbol: str, window_seconds: float) -> float:
        vol = self.annual_vol.get(symbol, self.default)
        return sigma_window(vol, window_seconds / 60.0)

    def prob_up(self, st: UpDownState) -> float | None:
        """None si faltan datos. Al expirar devuelve 1 o 0 según el precio."""
        if st.strike <= 0 or st.spot <= 0 or st.window_seconds <= 0:
            return None
        moneyness = math.log(st.spot / st.strike)
        if st.tau <= 1e-9:
            return 1.0 if moneyness > 0 else 0.0 if moneyness < 0 else 0.5
        sigma = self.sigma_for(st.symbol, st.window_seconds) * math.sqrt(st.tau)
        if sigma <= 0:
            return 1.0 if moneyness > 0 else 0.0
        return phi(moneyness / sigma)


def calibrate_sigma(prices: list[tuple[int, float]], window_seconds: float) -> dict[str, float]:
    """σ de la ventana a partir de una serie (ts_ms, precio), midiendo rendimientos sin solapar."""
    if len(prices) < 30:
        return {}
    prices = sorted(prices)
    step = window_seconds * 1000
    muestras: list[float] = []
    i = 0
    while i < len(prices):
        t0, p0 = prices[i]
        j = i
        while j < len(prices) and prices[j][0] < t0 + step:
            j += 1
        if j >= len(prices):
            break
        muestras.append(math.log(prices[j][1] / p0))
        i = j
    if len(muestras) < 20:
        return {}
    media = sum(muestras) / len(muestras)
    var = sum((x - media) ** 2 for x in muestras) / (len(muestras) - 1)
    sigma = math.sqrt(var)
    return {"n": len(muestras), "sigma_window": round(sigma, 6),
            "annual_vol": round(sigma * math.sqrt(MINUTES_PER_YEAR / (window_seconds / 60)), 4)}
