"""Básquet: modelo de Stern (1994). El margen evoluciona como un movimiento browniano.

P(local gana) = Φ( (ventaja + deriva·τ) / (σ·√τ) )
- ventaja: puntos de diferencia ahora
- τ: fracción del partido que falta
- deriva: ventaja esperada a partido completo, inferida del precio previo al partido
- σ: desviación del margen final a partido completo. Calibrado con 1230 partidos de la NBA
  2023-24: 16,2 puntos (la literatura clásica decía 11-12; el ritmo actual es mayor)

Es paramétrico a propósito: funciona desde el primer día y `scalper calibrate` ajusta σ con
partidos reales (propios o históricos) en cuanto los hay.
"""
from __future__ import annotations

import math
import re

from .base import GameState, WinProb

LEAGUE_MINUTES = {"nba": 48, "wnba": 40, "ncaab": 40, "cbb": 40, "euroleague": 40, "nbl": 40, "acb": 40}
LEAGUE_PERIODS = {"nba": 4, "wnba": 4, "ncaab": 2, "cbb": 2}
LEAGUE_OT = {"nba": 5, "wnba": 5, "ncaab": 5, "cbb": 5}


def phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def phi_inv(p: float) -> float:
    """Inversa aproximada de Φ (Acklam), suficiente para inferir la deriva."""
    p = min(max(p, 1e-6), 1 - 1e-6)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    plow = 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > 1 - plow:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


class BasketballModel:
    name = "stern"

    def __init__(self, sigma: float = 16.2, sigma_by_league: dict[str, float] | None = None):
        self.sigma = sigma
        self.sigma_by_league = sigma_by_league or {}

    def remaining_fraction(self, g: GameState) -> float | None:
        lg = g.league
        total = LEAGUE_MINUTES.get(lg, 48) * 60
        nper = LEAGUE_PERIODS.get(lg, 4)
        per_len = total / nper
        p = (g.period or "").upper()
        m = re.match(r"^(Q|P|H)?(\d+)$", p)
        if m:
            idx = int(m.group(2))
            done_before = (idx - 1) * per_len
        elif p.startswith("OT"):
            n = re.sub(r"\D", "", p) or "1"
            ot_len = LEAGUE_OT.get(lg, 5) * 60
            done_before = total + (int(n) - 1) * ot_len
            total = done_before + ot_len
            per_len = ot_len
        elif p in ("HT", "HALF", "HALFTIME"):
            return 0.5
        elif p in ("FT", "FINAL", "ENDED"):
            return 0.0
        elif not p and not g.live:
            return 1.0
        else:
            return None
        elapsed = done_before + min(max(g.elapsed_s, 0.0), per_len)
        return max(0.0, min(1.0, (total - elapsed) / total))

    def prob(self, g: GameState, pregame: WinProb | None) -> WinProb | None:
        tau = self.remaining_fraction(g)
        if tau is None:
            return None
        sigma = self.sigma_by_league.get(g.league, self.sigma)
        lead = g.home_score - g.away_score
        drift = 0.0
        if pregame is not None and 0 < pregame.home < 1:
            drift = phi_inv(pregame.home) * sigma      # ventaja esperada a partido completo
        if tau <= 1e-6:
            p = 1.0 if lead > 0 else 0.0 if lead < 0 else 0.5
        else:
            p = phi((lead + drift * tau) / (sigma * math.sqrt(tau)))
        return WinProb(home=p, away=1 - p, model=self.name,
                       detail={"tau": round(tau, 4), "lead": lead, "drift": round(drift, 2), "sigma": sigma})
