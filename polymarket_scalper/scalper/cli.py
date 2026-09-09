"""CLI: scalper <comando>."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .config import load_config


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)


def cmd_discover(args: argparse.Namespace) -> None:
    from .discovery import GammaClient, discover_markets

    cfg = load_config(args.config)

    async def go() -> None:
        g = GammaClient(cfg.collector.gamma_url)
        try:
            ms = await discover_markets(cfg, g)
        finally:
            await g.close()
        for m in ms[: args.limit]:
            print(f"{m.category:8} fee={m.fee_rate:.2f} tick={m.tick_size:<6} v24={m.volume_24h:>10.0f} "
                  f"negRisk={int(m.event_neg_risk)} {m.question[:70]}")
        print(f"\n{len(ms)} mercados")

    asyncio.run(go())


def cmd_collect(args: argparse.Namespace) -> None:
    from .collector import Collector

    cfg = load_config(args.config)
    col = Collector(cfg)
    if args.duration:
        async def go() -> None:
            async def stopper() -> None:
                await asyncio.sleep(args.duration)
                col.stop()
            asyncio.create_task(stopper())
            await col.run()
        asyncio.run(go())
    else:
        asyncio.run(col.run())


def cmd_paper(args: argparse.Namespace) -> None:
    from .sim.paper import run_paper

    cfg = load_config(args.config)
    asyncio.run(run_paper(cfg, duration_seconds=args.duration, run_id=args.run_id,
                          persist_market_data=not args.no_persist))


def cmd_replay(args: argparse.Namespace) -> None:
    from .sim.metrics import load_ledger, report_text
    from .sim.replay import run_replay

    cfg = load_config(args.config)
    eng = run_replay(cfg, start=args.start, end=args.end, conditions=args.condition, run_id=args.run_id)
    print(eng.summary())
    df = load_ledger(cfg.data_dir, eng.run_id)
    if df is not None:
        print(report_text(df))


def cmd_report(args: argparse.Namespace) -> None:
    from .sim.metrics import load_ledger, report_text

    cfg = load_config(args.config)
    df = load_ledger(cfg.data_dir, args.run_id)
    if df is None:
        print("sin datos de ledger")
        return
    print(f"{df.height} posiciones, runs: {sorted(df['run_id'].unique().to_list())}")
    print(report_text(df))


def cmd_status(args: argparse.Namespace) -> None:
    from .storage import scan

    cfg = load_config(args.config)
    for t in ("markets", "book_snapshots", "book_deltas", "trades", "quotes", "resolutions", "signals", "ledger"):
        lf = scan(cfg.data_dir, t)
        if lf is None:
            print(f"{t:16} (vacío)")
            continue
        col = "ts_ms" if t != "ledger" else "ts_signal"
        import polars as pl
        st = lf.select(pl.len().alias("n"), pl.col(col).min().alias("min"), pl.col(col).max().alias("max")).collect()
        from datetime import datetime, timezone
        f = lambda x: datetime.fromtimestamp(x / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if x else "-"
        print(f"{t:16} {st['n'][0]:>10} filas  {f(st['min'][0])} → {f(st['max'][0])}")


def cmd_sql(args: argparse.Namespace) -> None:
    import duckdb

    cfg = load_config(args.config)
    con = duckdb.connect()
    for t in ("markets", "book_snapshots", "book_deltas", "trades", "quotes", "resolutions", "signals", "ledger"):
        p = cfg.data_path / t
        if p.exists() and any(p.rglob("*.parquet")):
            con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{p}/**/*.parquet', union_by_name=true)")
    print(con.sql(args.query))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="scalper", description="Bot de scalping para Polymarket")
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("discover", help="lista los mercados que se seguirían")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(fn=cmd_discover)

    s = sub.add_parser("collect", help="fase 1: recolectar datos 24/7")
    s.add_argument("--duration", type=int, help="segundos (por defecto, indefinido)")
    s.set_defaults(fn=cmd_collect)

    s = sub.add_parser("paper", help="fase 3: paper trading en vivo (también recolecta)")
    s.add_argument("--duration", type=int)
    s.add_argument("--run-id")
    s.add_argument("--no-persist", action="store_true", help="no guardar datos de mercado, solo ledger")
    s.set_defaults(fn=cmd_paper)

    s = sub.add_parser("replay", help="fase 3: simular sobre el histórico")
    s.add_argument("--start", help="ISO8601 o epoch ms")
    s.add_argument("--end")
    s.add_argument("--condition", action="append", help="limitar a condition_id (repetible)")
    s.add_argument("--run-id")
    s.set_defaults(fn=cmd_replay)

    s = sub.add_parser("report", help="métricas del ledger (predicho vs real)")
    s.add_argument("--run-id")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("status", help="qué datos hay en data/")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("sql", help="consulta SQL (DuckDB) sobre las tablas")
    s.add_argument("query")
    s.set_defaults(fn=cmd_sql)

    args = p.parse_args(argv)
    _setup_logging(args.verbose)
    try:
        args.fn(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
