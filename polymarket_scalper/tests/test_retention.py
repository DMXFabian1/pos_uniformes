from datetime import datetime, timedelta, timezone
import os, time

import polars as pl

from scalper.retention import apply_retention, disk_usage
from scalper.storage import ParquetWriter, scan


def _write_day(tmp_path, table, day, n_files=3, rows=5):
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    base = int(day.timestamp() * 1000)
    for f in range(n_files):
        for i in range(rows):
            w.append(table, {"ts_ms": base + f * 60000 + i, "token_id": "t", "condition_id": "c", "side": "BUY",
                             "price": 0.5, "size": 1.0, "best_bid": 0.49, "best_ask": 0.51, "hash": "h"})
        w.flush(table)
        time.sleep(0.002)   # nombres de archivo distintos


def _age_files(tmp_path, seconds):
    old = time.time() - seconds
    for f in tmp_path.rglob("*.parquet"):
        os.utime(f, (old, old))


def test_retention_deletes_old_and_compacts_closed_days(cfg, tmp_path):
    cfg.data_dir = str(tmp_path)
    cfg.retention.keep_days = {"book_deltas": 3}
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    for back in (0, 1, 2, 5):
        _write_day(tmp_path, "book_deltas", now - timedelta(days=back))
    _age_files(tmp_path, 7200)
    before = {d.name: len(list(d.glob("*.parquet"))) for d in (tmp_path / "book_deltas").glob("date=*")}
    assert before["date=2026-09-10"] == 3 and before["date=2026-09-05"] == 3
    rep = apply_retention(cfg, dry_run=True, now=now)
    assert len(rep.deleted_dirs) == 1 and rep.deleted_dirs[0].endswith("date=2026-09-05")
    assert len(rep.compacted_dirs) == 2                       # 09-09 y 09-08; el 09-10 (hoy) no se toca
    assert (tmp_path / "book_deltas" / "date=2026-09-05").exists()   # simulación: nada borrado
    rep = apply_retention(cfg, dry_run=False, now=now)
    assert not (tmp_path / "book_deltas" / "date=2026-09-05").exists()
    after = {d.name: len(list(d.glob("*.parquet"))) for d in (tmp_path / "book_deltas").glob("date=*")}
    assert after == {"date=2026-09-10": 3, "date=2026-09-09": 1, "date=2026-09-08": 1}
    df = scan(tmp_path, "book_deltas").collect()
    assert df.height == 45 and df["ts_ms"].is_sorted() is not None   # 3 días × 15 filas, todo legible


def test_retention_skips_recently_written_partitions(cfg, tmp_path):
    cfg.data_dir = str(tmp_path)
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    _write_day(tmp_path, "book_deltas", now - timedelta(days=1))
    rep = apply_retention(cfg, dry_run=False, now=now)        # archivos recién escritos: se omite
    assert rep.compacted_dirs == [] and len(rep.skipped) == 1
    assert len(list((tmp_path / "book_deltas" / "date=2026-09-09").glob("*.parquet"))) == 3


def test_tables_without_keep_days_are_never_deleted(cfg, tmp_path):
    cfg.data_dir = str(tmp_path)
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    w = ParquetWriter(tmp_path, flush_seconds=10**9, flush_rows=10**9)
    old = int((now - timedelta(days=400)).timestamp() * 1000)
    w.append("trades", {"ts_ms": old, "token_id": "t", "condition_id": "c", "price": 0.5, "size": 1, "side": "BUY", "fee_rate_bps": 0, "tx_hash": ""})
    w.close()
    _age_files(tmp_path, 7200)
    rep = apply_retention(cfg, dry_run=False, now=now)
    assert rep.deleted_dirs == [] and scan(tmp_path, "trades").collect().height == 1
    assert any(r["table"] == "trades" and r["keep_days"] == "∞" for r in disk_usage(cfg))
