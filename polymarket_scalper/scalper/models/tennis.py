"""Tenis: cadena de Markov por puntos (O'Malley 2008).

De la probabilidad de ganar un punto al saque de cada jugador salen, en forma cerrada, las de
ganar un juego, un set y el partido desde cualquier marcador. Las probabilidades de punto se
infieren del precio previo al partido: se fija la media del circuito (≈0,62 en ATP, ≈0,58 en
WTA) y se busca la diferencia entre jugadores que reproduce ese precio.
"""
from __future__ import annotations

from functools import lru_cache

from .base import GameState, WinProb


@lru_cache(maxsize=None)
def p_game(p: float) -> float:
    """Prob. de ganar un juego al saque con prob. p de ganar cada punto."""
    q = 1 - p
    return p**4 * (1 + 4 * q + 10 * q**2) + 20 * p**3 * q**3 * p**2 / (1 - 2 * p * q)


def _serving_a(total_points: int, server_a: bool) -> bool:
    """En el tiebreak el primero saca 1 punto y luego se alterna de a 2."""
    if total_points == 0:
        return server_a
    return server_a if ((total_points - 1) // 2) % 2 == 1 else not server_a


@lru_cache(maxsize=None)
def p_tiebreak(p: float, r: float, a: int = 0, b: int = 0, server_a: bool = True, target: int = 7) -> float:
    """Prob. de que A gane el tiebreak desde a-b. p: A gana punto al saque; r: A gana punto al resto."""
    if a >= target and a - b >= 2:
        return 1.0
    if b >= target and b - a >= 2:
        return 0.0
    pp = p if _serving_a(a + b, server_a) else r
    if a >= target - 1 and b >= target - 1:
        # zona de 'deuce': cada bloque de dos puntos tiene un saque de cada uno
        p_tie = p * r / (p * r + (1 - p) * (1 - r)) if (p * r + (1 - p) * (1 - r)) > 0 else 0.5
        if a == b:
            return p_tie
        if a == b + 1:
            return pp + (1 - pp) * p_tie
        return pp * p_tie                      # b == a + 1
    return pp * p_tiebreak(p, r, a + 1, b, server_a, target) + (1 - pp) * p_tiebreak(p, r, a, b + 1, server_a, target)


@lru_cache(maxsize=None)
def p_set(p: float, r: float, ga: int = 0, gb: int = 0, a_serves: bool = True, tb_at: int = 6) -> float:
    """Prob. de que A gane el set desde ga-gb juegos, sacando A si a_serves."""
    if ga >= 6 and ga - gb >= 2:
        return 1.0
    if gb >= 6 and gb - ga >= 2:
        return 0.0
    if ga == tb_at + 1 and gb == tb_at:
        return 1.0
    if gb == tb_at + 1 and ga == tb_at:
        return 0.0
    if ga == tb_at and gb == tb_at:
        return p_tiebreak(p, r, 0, 0, a_serves)
    pg = p_game(p) if a_serves else 1 - p_game(1 - r)   # si saca B, A gana el juego con 1-p_game(B al saque)
    return pg * p_set(p, r, ga + 1, gb, not a_serves, tb_at) + (1 - pg) * p_set(p, r, ga, gb + 1, not a_serves, tb_at)


def p_match(p: float, r: float, sets_a: int, sets_b: int, best_of: int, ga: int, gb: int,
            a_serves: bool | None, in_tb: bool = False, tb_a: int = 0, tb_b: int = 0) -> float:
    need = best_of // 2 + 1
    if sets_a >= need:
        return 1.0
    if sets_b >= need:
        return 0.0
    # set actual
    if in_tb:
        cur = 0.5 * (p_tiebreak(p, r, tb_a, tb_b, True) + p_tiebreak(p, r, tb_a, tb_b, False))
    elif a_serves is None:
        cur = 0.5 * (p_set(p, r, ga, gb, True) + p_set(p, r, ga, gb, False))
    else:
        cur = p_set(p, r, ga, gb, a_serves)
    win_after = _p_sets(p, r, sets_a + 1, sets_b, need)
    lose_after = _p_sets(p, r, sets_a, sets_b + 1, need)
    return cur * win_after + (1 - cur) * lose_after


@lru_cache(maxsize=None)
def _p_sets(p: float, r: float, sa: int, sb: int, need: int) -> float:
    if sa >= need:
        return 1.0
    if sb >= need:
        return 0.0
    ps = 0.5 * (p_set(p, r, 0, 0, True) + p_set(p, r, 0, 0, False))
    return ps * _p_sets(p, r, sa + 1, sb, need) + (1 - ps) * _p_sets(p, r, sa, sb + 1, need)


def infer_point_probs(pregame_home: float, avg_serve: float, best_of: int) -> tuple[float, float]:
    """Busca delta tal que con p_home = avg+delta, p_away = avg-delta, P(home gana partido) = pregame."""
    lo, hi = -0.25, 0.25
    for _ in range(30):
        mid = (lo + hi) / 2
        ph, pa = avg_serve + mid, avg_serve - mid
        val = p_match(round(ph, 4), round(1 - pa, 4), 0, 0, best_of, 0, 0, None)
        if val < pregame_home:
            lo = mid
        else:
            hi = mid
    d = (lo + hi) / 2
    return round(avg_serve + d, 4), round(avg_serve - d, 4)


class TennisModel:
    name = "omalley"

    def __init__(self, avg_serve_atp: float = 0.62, avg_serve_wta: float = 0.58):
        self.avg_atp = avg_serve_atp
        self.avg_wta = avg_serve_wta

    def prob(self, g: GameState, pregame: WinProb | None) -> WinProb | None:
        x = g.extra
        if "sets_home" not in x:
            return None
        wta = "wta" in g.league
        avg = self.avg_wta if wta else self.avg_atp
        best_of = 5 if ("grand" in g.league or "slam" in g.league) and not wta else 3
        pre = pregame.home if pregame is not None and 0 < pregame.home < 1 else 0.5
        ph, pa = infer_point_probs(pre, avg, best_of)
        p = p_match(ph, round(1 - pa, 4), x["sets_home"], x["sets_away"], best_of, x["games_home"], x["games_away"],
                    None, x.get("in_tiebreak", False), x.get("tb_home", 0), x.get("tb_away", 0))
        return WinProb(home=p, away=1 - p, model=self.name,
                       detail={"p_serve_home": ph, "p_serve_away": pa, "best_of": best_of, **x})
