"""Market Reaction Engine: cuánto tarda el precio en enterarse de lo que pasa en el partido.

La tesis del scalping en vivo es la desalineación temporal: el marcador cambia y el precio tarda
en moverse. Este módulo la mide en vez de suponerla. Por cada cambio de estado del partido
(canasta, cambio de período) toma una foto del mid de cada token enlazado y espera a que el mid
se mueva al menos `umbral_ticks`. El retraso observado y el tamaño del movimiento se guardan en
la tabla `reactions`; si en `ventana_ms` no se movió, se guarda como "no reaccionó".

Con eso salen tres cosas que usan los detectores:
- `ms_since_event`: cuánto hace del último evento (si es muy reciente, el precio está por moverse).
- `typical_lag_ms`: mediana del retraso observado en esa liga (tiempo hasta reacción esperado).
- `event_risk_score`: 0..1, explicable por componentes. Hoy solo se registra: el filtro se activa
  cuando haya distribución medida (`max_event_risk` en la configuración).
"""
from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .models.base import GameState


@dataclass
class _Pendiente:
    game_id: str
    league: str
    evento: str
    ts_evento: int
    mids: dict[str, tuple[str, float]]        # token_id -> (condition_id, mid al momento del evento)
    resueltos: set[str] = field(default_factory=set)


class ReactionEngine:
    def __init__(self, umbral_ticks: float = 1.0, ventana_ms: int = 60_000, max_lags: int = 200,
                 riesgo_recencia_ms: int = 30_000, riesgo_puntos_60s: float = 12.0):
        self.umbral_ticks = umbral_ticks
        self.ventana_ms = ventana_ms
        self.riesgo_recencia_ms = riesgo_recencia_ms
        self.riesgo_puntos_60s = riesgo_puntos_60s
        self.pendientes: list[_Pendiente] = []
        self.lags: dict[str, deque] = {}                 # liga -> retrasos observados (ms)
        self.ultimo_evento: dict[str, int] = {}          # game_id -> ts del último evento
        self.puntos: dict[str, deque] = {}               # game_id -> (ts, puntos anotados)
        self.rows: list[dict[str, Any]] = []             # filas listas para persistir
        self.max_lags = max_lags
        self.descartadas_por_reloj = 0                   # mediciones imposibles: el libro venía de antes

    # ------------------------------------------------------------ eventos del partido
    def on_game(self, ts_ms: int, prev: GameState | None, g: GameState, mids: dict[str, tuple[str, float]]) -> str | None:
        """Registra un evento si el estado cambió de forma relevante. Devuelve el tipo de evento o None."""
        if not g.live or g.ended:
            return None
        evento = None
        if prev is None:
            evento = "inicio"
        elif (g.home_score, g.away_score) != (prev.home_score, prev.away_score):
            evento = "marcador"
        elif g.period != prev.period:
            evento = "periodo"
        if evento is None:
            return None
        self.ultimo_evento[g.game_id] = ts_ms
        if evento == "marcador" and prev is not None:
            pts = abs(g.home_score - prev.home_score) + abs(g.away_score - prev.away_score)
            self.puntos.setdefault(g.game_id, deque(maxlen=100)).append((ts_ms, pts))
        if mids:
            # un evento nuevo sustituye al pendiente del mismo partido: lo que no reaccionó, no reaccionó
            self._expirar_partido(g.game_id, ts_ms, forzado=True)
            self.pendientes.append(_Pendiente(g.game_id, g.league, evento, ts_ms, dict(mids)))
        return evento

    # ------------------------------------------------------------ libro
    def on_book(self, ts_ms: int, token_id: str, mid: float | None, tick: float) -> None:
        if mid is None:
            return
        for p in self.pendientes:
            if token_id in p.resueltos or token_id not in p.mids:
                continue
            cid, mid0 = p.mids[token_id]
            if abs(mid - mid0) + 1e-12 >= self.umbral_ticks * tick:
                lag = ts_ms - p.ts_evento
                if lag < 0:
                    # relojes distintos: esta observación no mide nada, pero la espera sigue abierta
                    self.descartadas_por_reloj += 1
                    continue
                p.resueltos.add(token_id)
                self.lags.setdefault(p.league, deque(maxlen=self.max_lags)).append(lag)
                self.rows.append({"ts_ms": ts_ms, "game_id": p.game_id, "league": p.league, "condition_id": cid,
                                  "token_id": token_id, "evento": p.evento, "ts_evento": p.ts_evento,
                                  "mid_antes": mid0, "mid_despues": mid, "lag_ms": lag,
                                  "movimiento": round(mid - mid0, 6), "reaccion": True, "reacciono": True})
        self.pendientes = [p for p in self.pendientes if len(p.resueltos) < len(p.mids)]

    def expirar(self, ts_ms: int) -> None:
        for p in list(self.pendientes):
            if ts_ms - p.ts_evento >= self.ventana_ms:
                self._cerrar_sin_reaccion(p, ts_ms)
                self.pendientes.remove(p)

    def _expirar_partido(self, game_id: str, ts_ms: int, forzado: bool = False) -> None:
        for p in list(self.pendientes):
            if p.game_id == game_id and (forzado or ts_ms - p.ts_evento >= self.ventana_ms):
                self._cerrar_sin_reaccion(p, ts_ms)
                self.pendientes.remove(p)

    def _cerrar_sin_reaccion(self, p: _Pendiente, ts_ms: int) -> None:
        for tok, (cid, mid0) in p.mids.items():
            if tok in p.resueltos:
                continue
            self.rows.append({"ts_ms": ts_ms, "game_id": p.game_id, "league": p.league, "condition_id": cid,
                              "token_id": tok, "evento": p.evento, "ts_evento": p.ts_evento, "mid_antes": mid0,
                              "mid_despues": None, "lag_ms": None, "movimiento": None, "reacciono": False})

    def drenar(self) -> list[dict[str, Any]]:
        rows, self.rows = self.rows, []
        for r in rows:
            r.pop("reaccion", None)
        return rows

    # ------------------------------------------------------------ lo que ven los detectores
    def typical_lag_ms(self, league: str) -> float | None:
        xs = self.lags.get(league)
        return float(statistics.median(xs)) if xs else None

    def estado(self, game_id: str, league: str, ts_ms: int) -> dict[str, Any]:
        ultimo = self.ultimo_evento.get(game_id)
        desde = None if ultimo is None else ts_ms - ultimo
        recencia = 0.0 if desde is None else max(0.0, 1.0 - desde / self.riesgo_recencia_ms)
        pts60 = sum(p for t, p in self.puntos.get(game_id, ()) if ts_ms - t <= 60_000)
        rafaga = min(1.0, pts60 / self.riesgo_puntos_60s) if self.riesgo_puntos_60s > 0 else 0.0
        pendiente = any(p.game_id == game_id and len(p.resueltos) < len(p.mids) for p in self.pendientes)
        return {
            "ms_since_event": desde,
            "typical_lag_ms": self.typical_lag_ms(league),
            "market_pending": pendiente,                     # el precio aún no reaccionó al último evento
            "event_risk_score": round(max(recencia, rafaga), 3),
            "event_risk_components": {"recencia": round(recencia, 3), "rafaga_puntos_60s": round(rafaga, 3)},
        }
