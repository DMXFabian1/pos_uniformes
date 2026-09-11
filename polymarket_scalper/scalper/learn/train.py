"""Entrenamiento por tipo de señal con partición temporal y promoción campeón/retador.

Regla de promoción: el retador sustituye al campeón solo si, en la misma ventana de validación
(el último tramo temporal), su Brier es mejor que el del campeón Y mejor que el de la heurística.
Un modelo que no le gana a la heurística no aporta nada y no se usa.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from ..storage import scan
from .features import FeatureSchema, features_from_ledger_row
from .model import WinModel, brier, logloss
from .registry import ModelBundle, ModelStore

log = logging.getLogger(__name__)

# cierres que no dicen nada de la señal: liquidación forzada al final de una corrida, o sin llenar
EXCLUDED_EXITS = {"end", "end_stuck", "unfilled", "expired_unfilled", "spread_gone", "no_book", "price_moved"}


@dataclass
class TrainReport:
    kind: str
    n_total: int = 0
    n_train: int = 0
    n_val: int = 0
    brier_val: float | None = None
    logloss_val: float | None = None
    brier_heuristic_val: float | None = None
    brier_champion_val: float | None = None
    promoted: bool = False
    version: int | None = None
    reason: str = ""
    base_rate: float | None = None
    top_features: list[tuple[str, float]] = field(default_factory=list)


def load_examples(data_dir: str | Path, kind: str, run_ids: list[str] | None = None) -> list[dict[str, Any]]:
    lf = scan(data_dir, "ledger")
    if lf is None:
        return []
    lf = lf.filter((pl.col("kind") == kind) & (pl.col("size_filled") > 0) & ~pl.col("exit_reason").is_in(list(EXCLUDED_EXITS)))
    if run_ids:
        lf = lf.filter(pl.col("run_id").is_in(run_ids))
    out = []
    for r in lf.sort("ts_signal").collect().to_dicts():
        f = features_from_ledger_row(r)
        if f is None:
            continue
        out.append({"features": f, "y": 1 if r["realized_pnl"] > 0 else 0, "ts": r["ts_signal"],
                    "conf_heuristic": float(f.get("conf_heuristic", r.get("confidence") or 0.5)),
                    "signal_id": r["signal_id"]})
    # una señal por id (por si se re-simuló la misma corrida)
    seen: set[str] = set()
    uniq = []
    for e in out:
        if e["signal_id"] in seen:
            continue
        seen.add(e["signal_id"])
        uniq.append(e)
    return uniq


def train_kind(data_dir: str | Path, kind: str, min_examples: int = 40, val_fraction: float = 0.3,
               backend: str = "auto", promote: bool = True, min_val: int = 12) -> TrainReport:
    store = ModelStore(data_dir)
    ex = load_examples(data_dir, kind)
    rep = TrainReport(kind=kind, n_total=len(ex))
    if len(ex) < min_examples:
        rep.reason = f"pocos ejemplos ({len(ex)} < {min_examples})"
        return rep
    rep.base_rate = sum(e["y"] for e in ex) / len(ex)
    if rep.base_rate in (0.0, 1.0):
        rep.reason = "todas las etiquetas iguales"
        return rep
    n_val = max(min_val, int(len(ex) * val_fraction))
    train, val = ex[:-n_val], ex[-n_val:]
    if len(train) < min_examples // 2:
        rep.reason = "pocos ejemplos tras separar validación"
        return rep
    schema = FeatureSchema.from_rows([e["features"] for e in train])
    Xtr, ytr = [schema.vector(e["features"]) for e in train], [e["y"] for e in train]
    Xva, yva = [schema.vector(e["features"]) for e in val], [e["y"] for e in val]
    model = WinModel(backend).fit(Xtr, ytr)
    p_val = model.predict_proba(Xva)
    rep.n_train, rep.n_val = len(train), len(val)
    rep.brier_val, rep.logloss_val = brier(p_val, yva), logloss(p_val, yva)
    rep.brier_heuristic_val = brier([e["conf_heuristic"] for e in val], yva)
    champ = store.load_current(kind)
    if champ is not None:
        try:
            rep.brier_champion_val = brier(champ.model.predict_proba([champ.schema.vector(e["features"]) for e in val]), yva)
        except Exception:  # noqa: BLE001
            rep.brier_champion_val = None
    rep.top_features = _importance(model, schema, Xva, yva)
    # modelo final: reentrenado con todo (la validación ya juzgó la receta)
    schema_all = FeatureSchema.from_rows([e["features"] for e in ex])
    final = WinModel(backend).fit([schema_all.vector(e["features"]) for e in ex], [e["y"] for e in ex])
    bundle = ModelBundle(kind, 0, schema_all, final, len(ex), trained_at=int(time.time() * 1000),
                         train_range=(ex[0]["ts"], ex[-1]["ts"]))
    beats_heur = rep.brier_val < rep.brier_heuristic_val - 1e-6
    beats_champ = rep.brier_champion_val is None or rep.brier_val < rep.brier_champion_val - 1e-6
    if beats_heur and beats_champ:
        rep.promoted = promote
        rep.reason = "mejor que heurística y que el campeón" if champ is not None else "mejor que heurística"
    else:
        rep.reason = ("no mejora a la heurística" if not beats_heur else "no mejora al campeón")
    bundle.metrics = {"brier_val": rep.brier_val, "logloss_val": rep.logloss_val,
                      "brier_heuristic_val": rep.brier_heuristic_val, "brier_champion_val": rep.brier_champion_val,
                      "n_val": rep.n_val, "base_rate": rep.base_rate, "promoted": rep.promoted, "reason": rep.reason,
                      "top_features": rep.top_features}
    rep.version = store.save(bundle)
    if rep.promoted:
        store.promote(kind, rep.version)
    return rep


def _importance(model: WinModel, schema: FeatureSchema, X: list[list[float]], y: list[int], top: int = 8) -> list[tuple[str, float]]:
    """Importancia por permutación sobre validación (aumento del Brier al barajar cada columna)."""
    if len(X) < 8:
        return []
    import random
    rng = random.Random(7)
    base = brier(model.predict_proba(X), y)
    out = []
    for j, name in enumerate(schema.names):
        col = [row[j] for row in X]
        if len(set(col)) <= 1:
            continue
        shuffled = col[:]
        rng.shuffle(shuffled)
        Xp = [row[:j] + [shuffled[i]] + row[j + 1:] for i, row in enumerate(X)]
        out.append((name, round(brier(model.predict_proba(Xp), y) - base, 5)))
    out.sort(key=lambda kv: -kv[1])
    return out[:top]


@dataclass
class FoldReport:
    fold: int
    n_train: int
    n_val: int
    brier_modelo: float | None = None
    brier_heuristica: float | None = None
    gana: bool = False


@dataclass
class WalkForward:
    """Validación hacia adelante: entrenar con el pasado, evaluar con el futuro inmediato, repetir.

    Una sola partición 70/30 puede acertar por casualidad con el tramo que tocó. Aquí el modelo se
    reentrena en cada pliegue con todo lo anterior y se juzga con lo siguiente, que es exactamente
    como se usaría en vivo. Se considera estable si le gana a la heurística en la mayoría de los
    pliegues, no en uno.
    """
    kind: str
    n_total: int = 0
    folds: list[FoldReport] = field(default_factory=list)
    estable: bool = False
    razon: str = ""

    @property
    def ganados(self) -> int:
        return sum(1 for f in self.folds if f.gana)


def walk_forward(data_dir: str | Path, kind: str, folds: int = 4, min_train: int = 40,
                 min_val: int = 12, backend: str = "auto") -> WalkForward:
    ex = load_examples(data_dir, kind)
    wf = WalkForward(kind=kind, n_total=len(ex))
    necesario = min_train + folds * min_val
    if len(ex) < necesario:
        wf.razon = f"pocos ejemplos ({len(ex)} < {necesario} para {folds} pliegues)"
        return wf
    tam = (len(ex) - min_train) // folds
    for i in range(folds):
        corte = min_train + i * tam
        train, val = ex[:corte], ex[corte:corte + tam]
        if len(val) < min_val:
            break
        ytr = [e["y"] for e in train]
        if len(set(ytr)) < 2:
            continue                       # sin las dos clases no hay nada que aprender todavía
        schema = FeatureSchema.from_rows([e["features"] for e in train])
        model = WinModel(backend).fit([schema.vector(e["features"]) for e in train], ytr)
        yva = [e["y"] for e in val]
        p = model.predict_proba([schema.vector(e["features"]) for e in val])
        bm, bh = brier(p, yva), brier([e["conf_heuristic"] for e in val], yva)
        wf.folds.append(FoldReport(i + 1, len(train), len(val), round(bm, 4), round(bh, 4), bm < bh - 1e-6))
    if not wf.folds:
        wf.razon = "no se pudo formar ningún pliegue válido"
        return wf
    wf.estable = wf.ganados > len(wf.folds) / 2
    wf.razon = f"le gana a la heurística en {wf.ganados} de {len(wf.folds)} pliegues"
    return wf


def walk_forward_all(data_dir: str | Path, kinds: list[str] | None = None, **kw: Any) -> list[WalkForward]:
    lf = scan(data_dir, "ledger")
    if lf is None:
        return []
    if kinds is None:
        kinds = sorted(lf.select("kind").unique().collect()["kind"].to_list())
    return [walk_forward(data_dir, k, **kw) for k in kinds]


def formatear_walk_forward(reps: list[WalkForward]) -> str:
    if not reps:
        return "sin ledger"
    lineas = []
    for r in reps:
        if not r.folds:
            lineas.append(f"{r.kind:20} ejemplos={r.n_total:<5} sin validar: {r.razon}")
            continue
        estado = "ESTABLE" if r.estable else "inestable"
        lineas.append(f"{r.kind:20} ejemplos={r.n_total:<5} {estado} ({r.razon})")
        for f in r.folds:
            marca = "gana" if f.gana else "pierde"
            lineas.append(f"   pliegue {f.fold}  train={f.n_train:<5} val={f.n_val:<4} "
                          f"brier modelo={f.brier_modelo:.4f} heurística={f.brier_heuristica:.4f}  {marca}")
    return "\n".join(lineas)


def train_all(data_dir: str | Path, kinds: list[str] | None = None, **kw: Any) -> list[TrainReport]:
    lf = scan(data_dir, "ledger")
    if lf is None:
        return []
    if kinds is None:
        kinds = sorted(lf.select("kind").unique().collect()["kind"].to_list())
    return [train_kind(data_dir, k, **kw) for k in kinds]


def format_reports(reps: list[TrainReport]) -> str:
    lines = []
    for r in reps:
        if r.n_train == 0:
            lines.append(f"{r.kind:18} ejemplos={r.n_total:<5} sin entrenar: {r.reason}")
            continue
        f = lambda x: "  -  " if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.4f}"
        lines.append(f"{r.kind:18} ejemplos={r.n_total:<5} train={r.n_train:<5} val={r.n_val:<4} tasa_base={r.base_rate:.2f} "
                     f"brier modelo={f(r.brier_val)} heurística={f(r.brier_heuristic_val)} campeón={f(r.brier_champion_val)} "
                     f"-> v{r.version} {'PROMOVIDO' if r.promoted else 'no promovido'} ({r.reason})")
        if r.top_features:
            lines.append("      features: " + ", ".join(f"{n}={v:+.4f}" for n, v in r.top_features))
    return "\n".join(lines) if lines else "sin ledger"
