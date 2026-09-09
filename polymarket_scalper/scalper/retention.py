"""Retención y compactación del directorio de datos.

Dos problemas distintos:
1. Volumen: `book_deltas` crece ~4 GB/día. El aprendizaje usa `quotes` (muestreo cada 5 s),
   `trades`, `games`, `flow_trades` y el `ledger`; los deltas solo hacen falta para hacer replay
   detallado de días recientes. Se conservan `keep_days` días y se borra lo anterior.
2. Cantidad de archivos: el recolector vuelca un archivo cada 30 s, unos 2.900 por tabla y día.
   Los días ya cerrados se compactan a un solo archivo por tabla, que se lee mucho más rápido.

Seguro con el recolector corriendo: solo toca particiones de días anteriores al actual (UTC) y
cuyo archivo más reciente lleva más de una hora sin cambios.
"""
from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl

from .config import Config

log = logging.getLogger(__name__)

TABLES = ("markets", "book_snapshots", "book_deltas", "trades", "quotes", "games", "flow_trades", "wallet_profiles",
          "wallet_closed", "resolutions", "signals", "ledger")


@dataclass
class RetentionReport:
    deleted_dirs: list[str] = field(default_factory=list)
    deleted_bytes: int = 0
    compacted_dirs: list[str] = field(default_factory=list)
    compacted_files_before: int = 0
    compacted_bytes_before: int = 0
    compacted_bytes_after: int = 0
    skipped: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"borrados {len(self.deleted_dirs)} días ({self.deleted_bytes / 1e6:.0f} MB); "
                f"compactados {len(self.compacted_dirs)} días: {self.compacted_files_before} archivos, "
                f"{self.compacted_bytes_before / 1e6:.0f} MB -> {self.compacted_bytes_after / 1e6:.0f} MB")


def _day_dirs(table_dir: Path) -> list[Path]:
    """Particiones date=YYYY-MM-DD, recorriendo también subcarpetas (run=… en signals/ledger)."""
    return sorted(p for p in table_dir.rglob("date=*") if p.is_dir())


def _day_of(p: Path) -> datetime | None:
    try:
        return datetime.strptime(p.name[5:], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _quiet(p: Path, min_age_s: float) -> bool:
    newest = max((f.stat().st_mtime for f in p.glob("*.parquet")), default=0)
    return time.time() - newest >= min_age_s


def apply_retention(cfg: Config, dry_run: bool = False, now: datetime | None = None) -> RetentionReport:
    now = now or datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    root = cfg.data_path
    rc = cfg.retention
    rep = RetentionReport()
    for table in TABLES:
        tdir = root / table
        if not tdir.exists():
            continue
        keep = rc.keep_days.get(table)
        for d in _day_dirs(tdir):
            day = _day_of(d)
            if day is None or day >= today:
                continue                                    # el día en curso nunca se toca
            if not _quiet(d, rc.min_quiet_seconds):
                rep.skipped.append(str(d))
                continue
            age_days = (today - day).days
            if keep is not None and age_days > keep:
                size = _dir_size(d)
                rep.deleted_dirs.append(str(d))
                rep.deleted_bytes += size
                if not dry_run:
                    shutil.rmtree(d, ignore_errors=True)
                continue
            if rc.compact:
                _compact(d, rep, dry_run)
    if not dry_run:
        log.info("retención: %s", rep.summary())
    return rep


def _compact(d: Path, rep: RetentionReport, dry_run: bool) -> None:
    files = sorted(d.glob("*.parquet"))
    if len(files) <= 1:
        return
    before = sum(f.stat().st_size for f in files)
    rep.compacted_dirs.append(str(d))
    rep.compacted_files_before += len(files)
    rep.compacted_bytes_before += before
    if dry_run:
        rep.compacted_bytes_after += before
        return
    tmp = d / f".compact_{int(time.time())}.parquet.tmp"
    out = d / f"compact_{int(time.time())}_{len(files)}.parquet"
    try:
        lf = pl.scan_parquet([str(f) for f in files], missing_columns="insert", extra_columns="ignore")
    except TypeError:
        lf = pl.scan_parquet([str(f) for f in files])
    sort_col = "ts_signal" if "ts_signal" in lf.collect_schema().names() else "ts_ms"
    lf.sort(sort_col).sink_parquet(str(tmp), compression="zstd") if hasattr(lf, "sink_parquet") else \
        lf.sort(sort_col).collect().write_parquet(str(tmp), compression="zstd")
    os.replace(tmp, out)
    for f in files:
        try:
            f.unlink()
        except FileNotFoundError:
            pass
    rep.compacted_bytes_after += out.stat().st_size


def disk_usage(cfg: Config) -> list[dict[str, float | str | int]]:
    root = cfg.data_path
    out = []
    for table in TABLES:
        tdir = root / table
        if not tdir.exists():
            continue
        files = [f for f in tdir.rglob("*.parquet")]
        days = len(_day_dirs(tdir))
        out.append({"table": table, "files": len(files), "days": days, "mb": round(sum(f.stat().st_size for f in files) / 1e6, 1),
                    "keep_days": cfg.retention.keep_days.get(table, "∞")})
    total = shutil.disk_usage(root if root.exists() else Path.cwd())
    out.append({"table": "(disco libre)", "files": 0, "days": 0, "mb": round(total.free / 1e6, 0), "keep_days": ""})
    return out


def estimate_growth(cfg: Config) -> dict[str, float]:
    """MB por día por tabla, estimado con el rango de tiempo real de los datos guardados."""
    from .storage import scan
    root = cfg.data_path
    out: dict[str, float] = {}
    for table in TABLES:
        lf = scan(root, table)
        tdir = root / table
        if lf is None or not tdir.exists():
            continue
        col = "ts_signal" if table == "ledger" else "ts_ms"
        st = lf.select(pl.col(col).min().alias("mn"), pl.col(col).max().alias("mx")).collect()
        span_days = max((st["mx"][0] - st["mn"][0]) / 86_400_000, 1 / 1440) if st["mn"][0] is not None else None
        if span_days:
            mb = sum(f.stat().st_size for f in tdir.rglob("*.parquet")) / 1e6
            out[table] = round(mb / span_days, 1)
    return out
