"""Métricas del ledger: cuánto se equivoca cada tipo de señal y en qué dirección."""
from __future__ import annotations

from pathlib import Path

import polars as pl

from ..storage import scan


def load_ledger(data_dir: str | Path, run_id: str | None = None) -> pl.DataFrame | None:
    lf = scan(data_dir, "ledger")
    if lf is None:
        return None
    if run_id:
        lf = lf.filter(pl.col("run_id") == run_id)
    df = lf.collect()
    return df if df.height else None


def by_kind(df: pl.DataFrame) -> pl.DataFrame:
    filled = df.filter(pl.col("size_filled") > 0)
    base = df.group_by("kind").agg(
        pl.len().alias("señales"),
        (pl.col("size_filled") > 0).sum().alias("llenadas"),
    )
    if filled.height == 0:
        return base.sort("kind")
    perf = filled.group_by("kind").agg(
        pl.col("predicted_pnl").sum().round(4).alias("pnl_predicho"),
        pl.col("realized_pnl").sum().round(4).alias("pnl_real"),
        pl.col("error").mean().round(4).alias("error_medio"),
        pl.col("error").abs().mean().round(4).alias("error_abs_medio"),
        (pl.col("realized_pnl") > 0).mean().round(3).alias("tasa_acierto"),
        pl.col("fees").sum().round(4).alias("fees"),
    )
    return base.join(perf, on="kind", how="left").with_columns(
        (pl.col("llenadas") / pl.col("señales")).round(3).alias("tasa_llenado")
    ).sort("kind")


def calibration(df: pl.DataFrame, buckets: int = 5) -> pl.DataFrame:
    """Confianza declarada vs. tasa real de acierto. Si divergen, la heurística está mal calibrada."""
    filled = df.filter(pl.col("size_filled") > 0)
    if filled.height == 0:
        return pl.DataFrame()
    return (filled.with_columns(((pl.col("confidence") * buckets).floor() / buckets).alias("conf_bucket"))
            .group_by("conf_bucket").agg(pl.len().alias("n"),
                                        (pl.col("realized_pnl") > 0).mean().round(3).alias("acierto_real"),
                                        pl.col("error").mean().round(4).alias("error_medio"))
            .sort("conf_bucket"))


def by_exit_reason(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by(["kind", "exit_reason"]).agg(
        pl.len().alias("n"), pl.col("realized_pnl").sum().round(4).alias("pnl_real")
    ).sort(["kind", "exit_reason"])


def model_vs_heuristic(df: pl.DataFrame) -> pl.DataFrame:
    """Brier de la confianza usada (mezcla), de la heurística y del modelo puro, por tipo de señal."""
    if "p_win_model" not in df.columns:
        return pl.DataFrame()
    filled = df.filter((pl.col("size_filled") > 0) & pl.col("p_win_model").is_not_null())
    if filled.height == 0:
        return pl.DataFrame()
    y = (pl.col("realized_pnl") > 0).cast(pl.Float64)
    return filled.group_by("kind").agg(
        pl.len().alias("n"),
        ((pl.col("confidence") - y) ** 2).mean().round(4).alias("brier_mezcla"),
        ((pl.col("conf_heuristic") - y) ** 2).mean().round(4).alias("brier_heuristica"),
        ((pl.col("p_win_model") - y) ** 2).mean().round(4).alias("brier_modelo"),
    ).sort("kind")


def report_text(df: pl.DataFrame) -> str:
    parts = ["== Por tipo de señal ==", str(by_kind(df)), "", "== Por motivo de cierre ==", str(by_exit_reason(df)),
             "", "== Calibración de confianza ==", str(calibration(df))]
    mv = model_vs_heuristic(df)
    if mv.height:
        parts += ["", "== Modelo aprendido vs heurística (Brier, menor es mejor) ==", str(mv)]
    return "\n".join(parts)
