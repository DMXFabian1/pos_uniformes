"""Fútbol: goles restantes como Poisson independientes por equipo.

Las tasas de gol (λ_local, λ_visitante) a partido completo se infieren del precio previo
(local/empate/visitante) y se escalan por el tiempo que falta. Con el marcador actual, la
distribución de goles restantes da P(local), P(empate), P(visitante).
"""
from __future__ import annotations

import math
import re

from .base import GameState, WinProb

FULL_TIME_S = 90 * 60


def _poisson(lam: float, k: int) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def outcome_probs(lh: float, la: float, lead: int = 0, kmax: int = 10) -> tuple[float, float, float]:
    """P(local, empate, visitante) con `lead` goles de ventaja del local ahora y tasas restantes lh, la."""
    ph = pd = pa = 0.0
    for i in range(kmax + 1):
        pi = _poisson(lh, i)
        for j in range(kmax + 1):
            pj = _poisson(la, j)
            d = lead + i - j
            if d > 0:
                ph += pi * pj
            elif d == 0:
                pd += pi * pj
            else:
                pa += pi * pj
    s = ph + pd + pa
    return ph / s, pd / s, pa / s


def infer_rates(p_home: float, p_draw: float, total_goals: float = 2.7) -> tuple[float, float]:
    """Busca (λh, λa) con λh+λa≈total que reproduzcan P(local) y P(empate) previos.

    Dos incógnitas, dos ecuaciones: se resuelve por bisección en la diferencia y luego se
    ajusta el total para casar el empate (más total -> menos empates).
    """
    total = total_goals
    for _ in range(12):
        lo, hi = -total * 0.95, total * 0.95
        for _ in range(30):
            d = (lo + hi) / 2
            ph, _, _ = outcome_probs((total + d) / 2, (total - d) / 2)
            if ph < p_home:
                lo = d
            else:
                hi = d
        d = (lo + hi) / 2
        _, pd, _ = outcome_probs((total + d) / 2, (total - d) / 2)
        if pd > p_draw + 0.005:
            total *= 1.08
        elif pd < p_draw - 0.005:
            total *= 0.93
        else:
            break
        total = min(max(total, 1.0), 6.0)
    return round((total + d) / 2, 4), round((total - d) / 2, 4)


class SoccerModel:
    name = "poisson"

    def __init__(self, total_goals: float = 2.7):
        self.total_goals = total_goals

    def remaining_fraction(self, g: GameState) -> float | None:
        p = (g.period or "").upper()
        if p in ("FT", "FINAL", "ENDED", "AET", "PEN"):
            return 0.0
        if p in ("HT", "HALF", "HALFTIME"):
            return 0.5
        if not g.live and not p:
            return 1.0
        elapsed = g.elapsed_s
        if p in ("2H", "H2", "SECOND HALF", "2ND HALF") or re.match(r"^(P|H)?2$", p):
            elapsed = 45 * 60 + min(elapsed, 45 * 60 + 8 * 60) if elapsed < 45 * 60 else elapsed
        elif p in ("1H", "H1", "FIRST HALF", "1ST HALF") or re.match(r"^(P|H)?1$", p):
            elapsed = min(elapsed, 45 * 60 + 6 * 60)
        elif p.startswith("ET") or p.startswith("OT"):
            return 0.02
        elif elapsed <= 0:
            return None
        return max(0.0, min(1.0, (FULL_TIME_S - elapsed) / FULL_TIME_S))

    def prob(self, g: GameState, pregame: WinProb | None) -> WinProb | None:
        tau = self.remaining_fraction(g)
        if tau is None:
            return None
        if pregame is not None and pregame.home > 0 and pregame.draw > 0:
            lh, la = infer_rates(pregame.home, pregame.draw, self.total_goals)
        else:
            lh, la = self.total_goals * 0.55, self.total_goals * 0.45
        lead = g.home_score - g.away_score
        if tau <= 1e-6:
            ph, pd, pa = (1.0, 0.0, 0.0) if lead > 0 else (0.0, 1.0, 0.0) if lead == 0 else (0.0, 0.0, 1.0)
        else:
            ph, pd, pa = outcome_probs(lh * tau, la * tau, lead)
        return WinProb(home=ph, away=pa, draw=pd, model=self.name,
                       detail={"tau": round(tau, 4), "lead": lead, "lambda_home": lh, "lambda_away": la})
