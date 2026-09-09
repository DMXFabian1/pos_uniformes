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


def cmd_wallets(args: argparse.Namespace) -> None:
    import polars as pl
    from .storage import latest_profiles

    cfg = load_config(args.config)
    df = latest_profiles(cfg.data_dir)
    if df is None:
        print("sin perfiles todavía (corre `scalper collect` o `scalper profile <wallet>`)")
        return
    df = df.filter(pl.col("n_closed") >= args.min_closed).sort("score", descending=True)
    print(f"{df.height} wallets con >= {args.min_closed} posiciones cerradas. Top {args.top} por score:\n")
    print(f"{'wallet':12} {'nombre':18} {'n':>5} {'acierto':>8} {'roi':>8} {'pnl_real':>12} {'abiertas':>9} {'score':>6}")
    for r in df.head(args.top).to_dicts():
        n = f"{r['n_closed']}{'+' if r.get('truncated') else ''}"
        print(f"{r['wallet'][:12]} {(r['name'] or '')[:18]:18} {n:>5} {r['win_rate']*100:>7.0f}% "
              f"{r['roi']*100:>7.1f}% {r['realized_pnl']:>12,.0f} {r['n_open']:>9} {r['score']:>6.2f}")


def cmd_profile(args: argparse.Namespace) -> None:
    from .flow import DataApi
    from .storage import ParquetWriter
    from .wallets import WalletTracker

    cfg = load_config(args.config)

    async def go() -> None:
        api = DataApi(cfg.flow.data_api_url)
        writer = ParquetWriter(cfg.data_dir, flush_seconds=10**9, flush_rows=10**9)
        tr = WalletTracker(api, writer, cfg.flow.profile_max_pages)
        try:
            for w in args.wallet:
                p = await tr.profile(w)
                print(f"{p.wallet}  n_cerradas={p.n_closed}{'+' if p.truncated else ''} ganadas={p.wins} perdidas={p.losses} "
                      f"acierto={p.win_rate*100:.0f}% roi={p.roi*100:+.1f}% pnl={p.realized_pnl:+,.0f} "
                      f"mayor_ganancia={p.biggest_win:,.0f} mayor_perdida={p.biggest_loss:,.0f} "
                      f"abiertas={p.n_open} valor_abierto={p.open_value:,.0f} score={p.score:.2f}")
        finally:
            writer.close()
            await api.close()

    asyncio.run(go())


def cmd_flow(args: argparse.Namespace) -> None:
    import polars as pl
    from .storage import scan, latest_profiles

    cfg = load_config(args.config)
    lf = scan(cfg.data_dir, "flow_trades")
    if lf is None:
        print("sin flow_trades todavía")
        return
    df = lf.filter(pl.col("usd") >= args.min_usd).sort("ts_ms", descending=True).head(args.limit).collect()
    prof = latest_profiles(cfg.data_dir)
    scores = dict(zip(prof["wallet"], prof["score"])) if prof is not None else {}
    from datetime import datetime, timezone
    for r in df.to_dicts():
        t = datetime.fromtimestamp(r["ts_ms"] / 1000, tz=timezone.utc).strftime("%m-%d %H:%M:%S")
        sc = scores.get(r["wallet"])
        print(f"{t} {r['usd']:>9,.0f} {r['side']:4} {r['outcome'][:14]:14} @{r['price']:.3f} "
              f"{(r['name'] or r['wallet'][:10])[:16]:16} score={sc:.2f} {r['title'][:45]}" if sc is not None else
              f"{t} {r['usd']:>9,.0f} {r['side']:4} {r['outcome'][:14]:14} @{r['price']:.3f} "
              f"{(r['name'] or r['wallet'][:10])[:16]:16} score=  -  {r['title'][:45]}")


def cmd_games(args: argparse.Namespace) -> None:
    import polars as pl
    from .storage import scan

    cfg = load_config(args.config)
    lf = scan(cfg.data_dir, "games")
    if lf is None:
        print("sin partidos todavía")
        return
    df = lf.sort("ts_ms").group_by("game_id").last().sort("ts_ms", descending=True).collect()
    if not args.all:
        df = df.filter(pl.col("live") & ~pl.col("ended"))
    from datetime import datetime, timezone
    for r in df.head(args.limit).to_dicts():
        t = datetime.fromtimestamp(r["ts_ms"] / 1000, tz=timezone.utc).strftime("%m-%d %H:%M:%S")
        print(f"{t} {r['league']:14} {r['home'][:22]:22} vs {r['away'][:22]:22} {r['score']:18} {r['period']:6} {r['status']}")


def cmd_status(args: argparse.Namespace) -> None:
    from .storage import scan

    cfg = load_config(args.config)
    for t in ("markets", "book_snapshots", "book_deltas", "trades", "quotes", "resolutions", "games", "flow_trades",
              "wallet_profiles", "wallet_closed", "signals", "ledger"):
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
    for t in ("markets", "book_snapshots", "book_deltas", "trades", "quotes", "resolutions", "games", "flow_trades",
              "wallet_profiles", "wallet_closed", "signals", "ledger"):
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

    s = sub.add_parser("wallets", help="ranking de wallets perfiladas (dinero inteligente)")
    s.add_argument("--top", type=int, default=30)
    s.add_argument("--min-closed", type=int, default=20)
    s.set_defaults(fn=cmd_wallets)

    s = sub.add_parser("profile", help="perfilar una o más wallets ahora")
    s.add_argument("wallet", nargs="+")
    s.set_defaults(fn=cmd_profile)

    s = sub.add_parser("flow", help="últimos trades grandes con wallet y score")
    s.add_argument("--min-usd", type=float, default=2000)
    s.add_argument("--limit", type=int, default=40)
    s.set_defaults(fn=cmd_flow)

    s = sub.add_parser("games", help="partidos en vivo enlazados a mercados")
    s.add_argument("--all", action="store_true")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(fn=cmd_games)

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
