"""Puntúa señales en vivo con el modelo promovido, mezclado con la heurística según cuánto se ha entrenado."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ..book import OrderBook
from ..discovery import MarketInfo
from ..signals.base import Signal
from .features import build_features
from .registry import ModelBundle, ModelStore

log = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    p_heuristic: float
    p_model: float | None
    p_blend: float
    n_train: int
    version: int | None
    trusted: bool
    size_mult: float
    gate: bool             # True = descartar la señal
    features: dict[str, Any]


class Scorer:
    def __init__(self, store: ModelStore, shrink_n: int = 50, min_train: int = 30, min_p_win: float = 0.5,
                 size_floor: float = 0.2, enabled: bool = True):
        self.store = store
        self.shrink_n = shrink_n
        self.min_train = min_train
        self.min_p_win = min_p_win
        self.size_floor = size_floor
        self.enabled = enabled
        self._bundles: dict[str, ModelBundle | None] = {}
        self.reload()

    def reload(self) -> None:
        self._bundles = {k: self.store.load_current(k) for k in self.store.kinds()}
        loaded = {k: b.version for k, b in self._bundles.items() if b is not None}
        if loaded:
            log.info("modelos cargados: %s", loaded)

    def score(self, s: Signal, m: MarketInfo | None, ts_ms: int, book: OrderBook | None) -> ScoreResult:
        f = build_features(s, m, ts_ms, book)
        p_h = float(s.confidence)
        b = self._bundles.get(s.kind) if self.enabled else None
        if b is None:
            return ScoreResult(p_h, None, p_h, 0, None, False, 1.0, False, f)
        try:
            p_m = b.model.predict_proba([b.schema.vector(f)])[0]
        except Exception:  # noqa: BLE001
            log.exception("scorer falló para %s", s.kind)
            return ScoreResult(p_h, None, p_h, b.n_train, b.version, False, 1.0, False, f)
        w = b.n_train / (b.n_train + self.shrink_n)
        p = w * p_m + (1 - w) * p_h
        trusted = b.n_train >= self.min_train
        gate = trusted and p < self.min_p_win
        size_mult = max(self.size_floor, min(1.0, (p - 0.5) / 0.3 + 0.5)) if trusted else 1.0
        return ScoreResult(p_h, p_m, p, b.n_train, b.version, trusted, size_mult, gate, f)
