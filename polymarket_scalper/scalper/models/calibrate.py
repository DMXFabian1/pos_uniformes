"""Calibración del modelo de básquet con datos reales.

σ es la desviación estándar del margen final a partido completo. Si el margen es browniano,
Var(final − margen_t) = σ²·τ, así que σ̂² = media[(final − margen_t)² / τ] sobre muchos
instantes. Además se comprueba: (1) que la varianza escale con τ (si no, el modelo browniano
está mal), y (2) la calibración de P(local) = Φ(margen/(σ√τ)) contra el resultado real.

Fuentes:
- play-by-play de stats.nba.com (dataset shufinskiy/nba_data): columnas GAME_ID, PERIOD,
  PCTIMESTRING (reloj restante del período), SCOREMARGIN (local − visitante, 'TIE' = 0).
- la tabla `games` propia, cuando haya partidos de básquet terminados.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .base import parse_game
from .basketball import phi

REG_SECONDS = 48 * 60
OT_SECONDS = 5 * 60


def _elapsed_seconds(period: int, clock: str) -> float:
    """Segundos jugados dado el período y el reloj restante 'MM:SS'."""
    try:
        mm, ss = clock.split(":")
        remaining = int(mm) * 60 + float(ss)
    except (ValueError, AttributeError):
        return -1.0
    if period <= 4:
        return (period - 1) * 12 * 60 + (12 * 60 - remaining)
    return REG_SECONDS + (period - 5) * OT_SECONDS + (OT_SECONDS - remaining)


def load_nba_pbp(path: str | Path) -> dict[str, list[tuple[float, int]]]:
    """GAME_ID -> lista de (segundos jugados, margen local) en cada evento con marcador."""
    games: dict[str, list[tuple[float, int]]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sm = row.get("SCOREMARGIN") or ""
            if not sm:
                continue
            margin = 0 if sm == "TIE" else int(sm)
            try:
                period = int(row.get("PERIOD") or 0)
            except ValueError:
                continue
            t = _elapsed_seconds(period, row.get("PCTIMESTRING") or "")
            if t < 0:
                continue
            games[row["GAME_ID"]].append((t, margin))
    for g in games.values():
        g.sort()
    return games


def calibrate_from_trajectories(trajs: Iterable[list[tuple[float, int]]], total_seconds: float = REG_SECONDS,
                                min_tau: float = 0.05, sample_every: float = 60.0) -> dict[str, Any]:
    """Estima σ y comprueba escalado y calibración. `trajs`: por partido, [(t_seg, margen)] ordenado."""
    sq_over_tau: list[float] = []
    by_bucket: dict[float, list[float]] = defaultdict(list)
    calib: dict[float, list[tuple[float, int]]] = defaultdict(list)
    n_games = 0
    samples: list[tuple[float, int, int]] = []   # (tau, margen, final)
    for traj in trajs:
        if not traj:
            continue
        final = traj[-1][1]
        if final == 0:
            continue
        n_games += 1
        next_t = 0.0
        for t, margin in traj:
            if t > total_seconds:
                break                                    # prórroga: fuera de la calibración base
            if t < next_t:
                continue
            next_t = t + sample_every
            tau = (total_seconds - t) / total_seconds
            if tau < min_tau:
                continue
            samples.append((tau, margin, final))
            sq_over_tau.append((final - margin) ** 2 / tau)
            by_bucket[round(math.floor(tau * 10) / 10, 1)].append((final - margin) ** 2)
    if not sq_over_tau:
        return {"n_games": 0}
    sigma = math.sqrt(sum(sq_over_tau) / len(sq_over_tau))
    scaling = {b: {"n": len(v), "std": round(math.sqrt(sum(v) / len(v)), 2),
                   "std_pred": round(sigma * math.sqrt(b + 0.05), 2)} for b, v in sorted(by_bucket.items())}
    # calibración de Φ(margen/(σ√τ)) sin deriva contra el resultado
    for tau, margin, final in samples:
        p = phi(margin / (sigma * math.sqrt(tau)))
        calib[round(math.floor(p * 10) / 10, 1)].append((p, 1 if final > 0 else 0))
    calibration = {b: {"n": len(v), "p_pred": round(sum(x for x, _ in v) / len(v), 3),
                       "p_real": round(sum(y for _, y in v) / len(v), 3)} for b, v in sorted(calib.items())}
    brier = sum((phi(m / (sigma * math.sqrt(t))) - (1 if f > 0 else 0)) ** 2 for t, m, f in samples) / len(samples)
    return {"n_games": n_games, "n_samples": len(samples), "sigma": round(sigma, 3), "brier": round(brier, 4),
            "scaling": scaling, "calibration": calibration}


def trajectories_from_games_table(rows: list[dict[str, Any]], league: str = "nba") -> list[list[tuple[float, int]]]:
    """Convierte filas de la tabla `games` (básquet) en trayectorias (t_seg, margen)."""
    from .basketball import BasketballModel
    bm = BasketballModel()
    by_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if (r.get("league") or "").lower() == league:
            by_game[r["game_id"]].append(r)
    out = []
    for gid, rs in by_game.items():
        rs.sort(key=lambda r: r["ts_ms"])
        if not rs[-1].get("ended"):
            continue
        traj = []
        for r in rs:
            g = parse_game(r)
            tau = bm.remaining_fraction(g)
            if tau is None:
                continue
            traj.append(((1 - tau) * REG_SECONDS, g.home_score - g.away_score))
        if traj:
            out.append(traj)
    return out


def format_report(res: dict[str, Any]) -> str:
    if not res.get("n_games"):
        return "sin partidos para calibrar"
    lines = [f"partidos={res['n_games']} muestras={res['n_samples']} sigma={res['sigma']} brier={res['brier']}",
             "", "escalado de la varianza con el tiempo restante (std real vs σ·√τ):"]
    for b, v in res["scaling"].items():
        lines.append(f"  τ≈{b:.1f}  n={v['n']:>6}  std={v['std']:>6}  pred={v['std_pred']:>6}")
    lines += ["", "calibración de Φ(margen/(σ√τ)) sin deriva (p predicha vs frecuencia real de victoria local):"]
    for b, v in res["calibration"].items():
        lines.append(f"  p≈{b:.1f}  n={v['n']:>6}  pred={v['p_pred']:.3f}  real={v['p_real']:.3f}")
    return "\n".join(lines)
