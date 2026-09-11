"""Reentrenamiento periódico dentro de paper trading."""
from __future__ import annotations

import logging

from ..config import Config
from ..learn.train import format_reports, train_all
from .engine import Engine

log = logging.getLogger(__name__)


def retrain_and_reload(cfg: Config, eng: Engine) -> None:
    try:
        reps = train_all(cfg.data_dir, backend=cfg.learn.backend, min_examples=cfg.learn.min_examples,
                         val_fraction=cfg.learn.val_fraction)
        log.info("reentrenamiento:\n%s", format_reports(reps))
        if any(r.promoted for r in reps):
            eng.scorer.reload()
        # con más posiciones cerradas, el mínimo requerido de cada estrategia puede haber cambiado
        eng.recargar_minimos()
    except Exception:  # noqa: BLE001
        log.exception("reentrenamiento falló")
