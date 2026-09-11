"""CLI: scalper <comando>."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .config import load_config


def _setup_logging(verbose: bool, log_file: str | None = None) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        from logging.handlers import RotatingFileHandler
        from pathlib import Path

        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        # 10 MB por archivo, 5 archivos: el log nunca llena el disco
        handlers.append(RotatingFileHandler(log_file, maxBytes=10_000_000, backupCount=5, encoding="utf-8"))
    logging.basicConfig(level=level, handlers=handlers, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S" if log_file else "%H:%M:%S")
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


def cmd_retention(args: argparse.Namespace) -> None:
    from .retention import apply_retention, disk_usage, estimate_growth

    cfg = load_config(args.config)
    print(f"{'tabla':16}{'archivos':>10}{'días':>6}{'MB':>10}{'conserva':>10}")
    for r in disk_usage(cfg):
        print(f"{r['table']:16}{r['files']:>10}{r['days']:>6}{r['mb']:>10}{str(r['keep_days']):>10}")
    growth = estimate_growth(cfg)
    if growth:
        total = sum(growth.values())
        print("\ncrecimiento estimado (MB/día): " + ", ".join(f"{k}={v}" for k, v in sorted(growth.items(), key=lambda kv: -kv[1])) + f"  · total ≈ {total:.0f} MB/día")
        kept = sum(v for k, v in growth.items() if k not in cfg.retention.keep_days)
        print(f"con la retención activa, el crecimiento permanente es ≈ {kept:.0f} MB/día ({kept * 30 / 1000:.1f} GB/mes)")
    if args.apply or args.dry_run:
        rep = apply_retention(cfg, dry_run=not args.apply)
        print(("\n[simulación] " if not args.apply else "\n") + rep.summary())
        for d in rep.deleted_dirs:
            print("  borrar   ", d)
        for d in rep.compacted_dirs:
            print("  compactar", d)
        if rep.skipped:
            print(f"  omitidos {len(rep.skipped)} días con escrituras recientes")


def cmd_gui(args: argparse.Namespace) -> None:
    """Ventana de escritorio. Usa PyQt6 si está instalado; si no, la versión en Tkinter."""
    import os
    from pathlib import Path

    proyecto = Path(args.config).resolve().parent
    nombre = Path(args.config).name
    # sin GPU dedicada (máquinas virtuales, escritorio remoto) el componente web necesita esto
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu-compositing")

    if not args.tk:
        try:
            from .qtapp import lanzar as lanzar_qt

            sys.exit(lanzar_qt(proyecto, nombre))
        except ImportError:
            print("PyQt6 no está instalado; abriendo la versión sencilla.\n"
                  "Para la interfaz completa:  pip install PyQt6 PyQt6-WebEngine")

    from .gui import lanzar as lanzar_tk

    sys.exit(lanzar_tk(proyecto, nombre))


def cmd_dashboard(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    if args.snapshot:
        from .dashboard.data import snapshot_html
        from pathlib import Path
        Path(args.snapshot).write_text(snapshot_html(cfg, args.run_id), encoding="utf-8")
        print(f"panel guardado en {args.snapshot}")
        return
    from .dashboard.server import serve
    serve(cfg, args.host, args.port, args.refresh)


def cmd_listo(args: argparse.Namespace) -> None:
    """¿Está el bot listo para operar con dinero real? La respuesta la dan los números."""
    from .readiness import evaluar, formatear

    cfg = load_config(args.config)
    etiquetas = {"updown_model": "Cripto: modelo", "model_deviation": "Deporte: modelo",
                 "smart_money": "Dinero inteligente", "spread_capture": "Captura de spread",
                 "complement_buy": "Arbitraje SÍ+NO", "complement_sell": "Arbitraje SÍ+NO (venta)",
                 "multi_buy_all_yes": "Arbitraje multi (SÍ)", "multi_buy_all_no": "Arbitraje multi (NO)"}
    print(formatear(evaluar(cfg.data_dir), etiquetas))


def cmd_ahora(args: argparse.Namespace) -> None:
    """Qué comprar ahora mismo, por mercado, explicado en palabras."""
    from .opportunities import formatear, listar

    cfg = load_config(args.config)
    ops = listar(cfg.data_dir, minutos=args.minutos, solo_frescas=args.solo_vigentes, min_edge=args.min_edge)
    if args.grupo:
        ops = [o for o in ops if o.grupo.lower() == args.grupo.lower()]
    print(formatear(ops))


def cmd_overview(args: argparse.Namespace) -> None:
    """Todos los informes de una pasada, en el orden en que conviene leerlos."""
    def titulo(t: str) -> None:
        print("\n" + "=" * 74 + f"\n  {t}\n" + "=" * 74)

    secciones = [
        ("OPORTUNIDADES AHORA MISMO", cmd_ahora),
        ("QUÉ DATOS HAY GUARDADOS", cmd_status),
        ("ARRASTRE ENTRE VENTANAS DE CRIPTO: ¿a favor o en contra de la racha?", cmd_updown_study),
        ("RESULTADOS POR TIPO DE SEÑAL (predicho contra real)", cmd_report),
        ("WALLETS CON HISTORIAL", cmd_wallets),
        ("MODELOS APRENDIDOS", cmd_models),
        ("¿LISTO PARA DINERO REAL?", cmd_listo),
        ("USO DE DISCO", cmd_retention),
    ]
    for nombre, fn in secciones:
        titulo(nombre)
        try:
            fn(args)
        except Exception as e:  # noqa: BLE001
            print(f"(no se pudo mostrar: {e})")


def cmd_updown_study(args: argparse.Namespace) -> None:
    from .studies import estudiar, formatear

    cfg = load_config(args.config)
    print(formatear(estudiar(cfg.data_dir, args.offset, args.size)))


def cmd_train(args: argparse.Namespace) -> None:
    from .learn.train import format_reports, train_all

    cfg = load_config(args.config)
    reps = train_all(cfg.data_dir, kinds=args.kind or None, backend=args.backend or cfg.learn.backend,
                     min_examples=args.min_examples or cfg.learn.min_examples, val_fraction=cfg.learn.val_fraction,
                     promote=not args.no_promote)
    print(format_reports(reps))


def cmd_models(args: argparse.Namespace) -> None:
    from .learn.registry import ModelStore

    cfg = load_config(args.config)
    store = ModelStore(cfg.data_dir)
    kinds = store.kinds()
    if not kinds:
        print("sin modelos entrenados (corre `scalper train`)")
        return
    from datetime import datetime, timezone
    for k in kinds:
        print(f"\n{k}:")
        for h in store.history(k):
            t = datetime.fromtimestamp(h["trained_at"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            f = lambda x: "  -  " if x is None else f"{x:.4f}"
            print(f"  v{h['version']:<3} {'*' if h['current'] else ' '} {t} n={h['n_train']:<5} {h['backend']:8} "
                  f"brier={f(h['brier_val'])} heur={f(h['brier_heuristic_val'])} val={h['n_val']} "
                  f"{'promovido' if h['promoted'] else 'no'}: {h['reason']}")


def cmd_model(args: argparse.Namespace) -> None:
    """Diagnóstico: partidos en vivo enlazados, lado de cada token, mid del mercado y salida del modelo."""
    import polars as pl
    from .discovery import MarketInfo
    from .models import ModelRegistry, WinProb, match_outcome, parse_game
    from .storage import latest_markets, scan

    cfg = load_config(args.config)
    mk = latest_markets(cfg.data_dir)
    glf, qlf = scan(cfg.data_dir, "games"), scan(cfg.data_dir, "quotes")
    if mk is None or glf is None or qlf is None:
        print("faltan tablas (markets, games, quotes)")
        return
    games = glf.sort("ts_ms").group_by("game_id").last().collect()
    if not args.all:
        games = games.filter(pl.col("live") & ~pl.col("ended"))
    quotes = qlf.sort("ts_ms").group_by("token_id").agg(pl.col("mid").last().alias("mid"), pl.col("mid").first().alias("mid_first"),
                                                       pl.col("best_bid").last(), pl.col("best_ask").last()).collect()
    qmap = {r["token_id"]: r for r in quotes.to_dicts()}
    markets = [MarketInfo.from_row(r) for r in mk.to_dicts()]
    by_game: dict[str, list[MarketInfo]] = {}
    for m in markets:
        if m.event_game_id:
            by_game.setdefault(m.event_game_id, []).append(m)
    reg = ModelRegistry(cfg.models.sigma_basketball, cfg.models.sigma_by_league, cfg.models.soccer_total_goals)
    for r in games.sort("ts_ms", descending=True).to_dicts():
        ms = by_game.get(r["game_id"])
        if not ms:
            continue
        g = parse_game(r)
        print(f"\n[{g.league}/{g.sport}] {g.home} vs {g.away}  score={r['score']} period={r['period']} live={g.live}")
        mls = [m for m in ms if m.sports_market_type in ("", "moneyline", "child_moneyline")]
        # proxy de precio previo: primer mid visto por lado, agregando los mercados del partido (en fútbol el
        # visitante y el empate viven en mercados hermanos). El motor solo lo acepta al inicio del partido.
        first: dict[str, list[float]] = {}
        for m in mls:
            for t in m.tokens:
                side = match_outcome(t.outcome, g.home, g.away, m.question)
                q = qmap.get(t.token_id)
                if side and q and q["mid_first"] is not None:
                    first.setdefault(side, []).append(q["mid_first"])
        pre = None
        if "home" in first and "away" in first:
            ph, pa = sum(first["home"]) / len(first["home"]), sum(first["away"]) / len(first["away"])
            pd = sum(first["draw"]) / len(first["draw"]) if "draw" in first else 0.0
            tot = ph + pa + pd
            pre = WinProb(ph / tot, pa / tot, pd / tot)
        wp = reg.prob(g, pre) if g.sport in ("basketball", "tennis", "soccer") else None
        if pre is not None:
            print(f"  previo(proxy)= local {pre.home:.3f} visitante {pre.away:.3f} empate {pre.draw:.3f}")
        for m in mls:
            sides = {t.token_id: match_outcome(t.outcome, g.home, g.away, m.question) for t in m.tokens}
            mids = {t.token_id: qmap.get(t.token_id) for t in m.tokens}
            print(f"  {m.question[:60]}  fee={m.fee_rate}")
            for t in m.tokens:
                q = mids[t.token_id]
                side = sides[t.token_id]
                pm = wp.for_side(side) if (wp is not None and side) else None
                mid = q["mid"] if q else None
                dev = f"{pm - mid:+.3f}" if (pm is not None and mid is not None) else "   -  "
                print(f"     {t.outcome[:24]:24} lado={str(side):5} mid={mid if mid is None else round(mid, 3)!s:6} "
                      f"modelo={'-' if pm is None else round(pm, 3)!s:6} desvío={dev}")


def cmd_calibrate(args: argparse.Namespace) -> None:
    from .models.calibrate import (calibrate_from_trajectories, format_report, load_nba_pbp,
                                   trajectories_from_games_table)
    from .storage import scan

    cfg = load_config(args.config)
    if args.nba_csv:
        games = load_nba_pbp(args.nba_csv)
        print(f"play-by-play: {len(games)} partidos")
        print(format_report(calibrate_from_trajectories(games.values())))
        return
    lf = scan(cfg.data_dir, "games")
    if lf is None:
        print("sin tabla games. Pasa --nba-csv <archivo> para calibrar con histórico.")
        return
    trajs = trajectories_from_games_table(lf.collect().to_dicts(), league=args.league)
    print(f"tabla games: {len(trajs)} partidos terminados de {args.league}")
    print(format_report(calibrate_from_trajectories(trajs)))


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
    p.add_argument("--log-file", help="además de la consola, escribir el log aquí (rota a los 10 MB)")
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

    s = sub.add_parser("retention", help="uso de disco, crecimiento estimado y limpieza/compactación")
    s.add_argument("--apply", action="store_true", help="ejecutar borrado y compactación")
    s.add_argument("--dry-run", action="store_true", help="mostrar qué haría sin tocar nada")
    s.set_defaults(fn=cmd_retention)

    s = sub.add_parser("gui", help="ventana de escritorio con botones (sin usar la terminal)")
    s.add_argument("--tk", action="store_true", help="usar la versión sencilla en Tkinter")
    s.set_defaults(fn=cmd_gui)

    s = sub.add_parser("dashboard", help="panel web local (http://127.0.0.1:8787) que lee data/ en vivo")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8787)
    s.add_argument("--refresh", type=float, default=10, help="segundos entre recálculos de datos")
    s.add_argument("--snapshot", help="en vez de servir, guardar una página autónoma con los datos actuales")
    s.add_argument("--run-id")
    s.set_defaults(fn=cmd_dashboard)

    s = sub.add_parser("overview", help="todos los informes de una pasada")
    s.add_argument("--offset", type=float, default=20)
    s.add_argument("--size", type=float, default=50)
    s.add_argument("--run-id")
    s.add_argument("--top", type=int, default=20)
    s.add_argument("--min-closed", type=int, default=20)
    s.add_argument("--apply", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--minutos", type=float, default=30)
    s.add_argument("--solo-vigentes", action="store_true")
    s.add_argument("--min-edge", type=float, default=0.0)
    s.add_argument("--grupo")
    s.set_defaults(fn=cmd_overview)

    s = sub.add_parser("listo", help="¿está el bot listo para dinero real? veredicto por señal, con números")
    s.set_defaults(fn=cmd_listo)

    s = sub.add_parser("ahora", help="qué comprar ahora mismo, por mercado, explicado en palabras")
    s.add_argument("--minutos", type=float, default=30, help="cuánto atrás mirar")
    s.add_argument("--solo-vigentes", action="store_true", help="ocultar las que ya caducaron")
    s.add_argument("--min-edge", type=float, default=0.0, help="ventaja mínima por share")
    s.add_argument("--grupo", help="filtrar: Cripto, NBA o Tenis")
    s.set_defaults(fn=cmd_ahora)

    s = sub.add_parser("updown-study", help="¿el sesgo al abrir una ventana es información o sobrerreacción?")
    s.add_argument("--offset", type=float, default=20, help="segundos tras la apertura en que se mide el precio")
    s.add_argument("--size", type=float, default=50, help="shares por operación en el cálculo")
    s.set_defaults(fn=cmd_updown_study)

    s = sub.add_parser("train", help="fase 5: entrenar P(ganancia) por tipo de señal desde el ledger")
    s.add_argument("--kind", action="append")
    s.add_argument("--backend", choices=["auto", "hgb", "logistic"])
    s.add_argument("--min-examples", type=int)
    s.add_argument("--no-promote", action="store_true")
    s.set_defaults(fn=cmd_train)

    s = sub.add_parser("models", help="versiones de modelos entrenados y cuál está en uso")
    s.set_defaults(fn=cmd_models)

    s = sub.add_parser("model", help="diagnóstico: partidos en vivo, lado de cada token, mid vs modelo")
    s.add_argument("--all", action="store_true")
    s.set_defaults(fn=cmd_model)

    s = sub.add_parser("calibrate", help="calibrar σ del modelo de básquet (tabla games o play-by-play NBA)")
    s.add_argument("--nba-csv", help="CSV de stats.nba.com (dataset shufinskiy/nba_data, nbastats_<año>.csv)")
    s.add_argument("--league", default="nba")
    s.set_defaults(fn=cmd_calibrate)

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
    _setup_logging(args.verbose, args.log_file)
    try:
        args.fn(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
