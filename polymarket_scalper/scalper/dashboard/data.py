"""Arma el JSON que consume el panel a partir de las tablas Parquet. Tolera tablas vacías."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import polars as pl

from ..config import Config
from ..discovery import MarketInfo
from ..learn.registry import ModelStore
from ..models import ModelRegistry, WinProb, match_outcome, parse_game
from ..opportunities import listar as listar_oportunidades, por_grupo, resumen_grupo
from ..storage import latest_markets, latest_profiles, scan

log = logging.getLogger(__name__)

EXCLUDED_EXITS = ["end", "end_stuck", "unfilled", "expired_unfilled", "spread_gone", "no_book", "price_moved"]


def _first(df: pl.DataFrame | None, col: str, default: Any = None) -> Any:
    return df[col][0] if df is not None and df.height else default


def _rows(df: pl.DataFrame | None) -> list[dict[str, Any]]:
    return df.to_dicts() if df is not None and df.height else []


def _table_status(data_dir: Path) -> list[dict[str, Any]]:
    out = []
    for t in ("markets", "book_snapshots", "book_deltas", "trades", "quotes", "games", "flow_trades", "wallet_profiles",
              "wallet_closed", "resolutions", "signals", "ledger"):
        lf = scan(data_dir, t)
        if lf is None:
            out.append({"table": t, "rows": 0, "min_ts": None, "max_ts": None})
            continue
        col = "ts_signal" if t == "ledger" else "ts_ms"
        st = lf.select(pl.len().alias("n"), pl.col(col).min().alias("mn"), pl.col(col).max().alias("mx")).collect()
        out.append({"table": t, "rows": int(st["n"][0]), "min_ts": st["mn"][0], "max_ts": st["mx"][0]})
    return out


def _ledger(data_dir: Path, run_id: str | None) -> pl.DataFrame | None:
    lf = scan(data_dir, "ledger")
    if lf is None:
        return None
    if run_id:
        lf = lf.filter(pl.col("run_id") == run_id)
    df = lf.sort("ts_signal").collect()
    return df if df.height else None


def _ledger_sections(df: pl.DataFrame | None, start_cash: float) -> dict[str, Any]:
    if df is None:
        return {"equity": [], "by_kind": [], "exit_reasons": [], "calibration": [], "model_vs_heuristic": [],
                "recent_positions": [], "summary": {"equity": start_cash, "pnl": 0.0, "positions_closed": 0,
                                                    "positions_filled": 0, "fill_rate": None, "win_rate": None,
                                                    "pnl_valid": 0.0, "n_valid": 0}}
    valid = df.filter(~pl.col("exit_reason").is_in(EXCLUDED_EXITS) & (pl.col("size_filled") > 0))
    filled = df.filter(pl.col("size_filled") > 0)
    y = (pl.col("realized_pnl") > 0).cast(pl.Float64)
    closed = df.filter(pl.col("ts_exit") > 0).sort("ts_exit")
    eq = closed.select("ts_exit", pl.col("realized_pnl").cum_sum().alias("cum")).to_dicts()
    equity = [{"ts": r["ts_exit"], "equity": round(start_cash + r["cum"], 4)} for r in eq]
    by_kind = df.group_by("kind").agg(
        pl.len().alias("senales"), (pl.col("size_filled") > 0).sum().alias("llenadas"),
        pl.col("predicted_pnl").filter(pl.col("size_filled") > 0).sum().round(4).alias("pnl_predicho"),
        pl.col("realized_pnl").filter(pl.col("size_filled") > 0).sum().round(4).alias("pnl_real"),
        pl.col("error").filter(pl.col("size_filled") > 0).mean().round(4).alias("error_medio"),
        pl.col("error").filter(pl.col("size_filled") > 0).abs().mean().round(4).alias("error_abs_medio"),
        (pl.col("realized_pnl") > 0).filter(pl.col("size_filled") > 0).mean().round(3).alias("tasa_acierto"),
        pl.col("fees").sum().round(4).alias("fees"),
        pl.col("realized_pnl").filter(~pl.col("exit_reason").is_in(EXCLUDED_EXITS) & (pl.col("size_filled") > 0)).sum().round(4).alias("pnl_valido"),
        (~pl.col("exit_reason").is_in(EXCLUDED_EXITS) & (pl.col("size_filled") > 0)).sum().alias("n_valido"),
    ).with_columns((pl.col("llenadas") / pl.col("senales")).round(3).alias("tasa_llenado")).sort("kind")
    exit_reasons = df.group_by(["kind", "exit_reason"]).agg(pl.len().alias("n"), pl.col("realized_pnl").sum().round(4).alias("pnl_real")).sort(["kind", "n"], descending=[False, True])
    calib = (filled.with_columns(((pl.col("confidence") * 5).floor() / 5).alias("bucket"))
             .group_by("bucket").agg(pl.len().alias("n"), y.mean().round(3).alias("acierto_real"),
                                    pl.col("confidence").mean().round(3).alias("conf_media"),
                                    pl.col("error").mean().round(4).alias("error_medio")).sort("bucket")) if filled.height else None
    mv = None
    if "p_win_model" in df.columns:
        fm = filled.filter(pl.col("p_win_model").is_not_null())
        if fm.height:
            mv = fm.group_by("kind").agg(pl.len().alias("n"), ((pl.col("confidence") - y) ** 2).mean().round(4).alias("brier_mezcla"),
                                         ((pl.col("conf_heuristic") - y) ** 2).mean().round(4).alias("brier_heuristica"),
                                         ((pl.col("p_win_model") - y) ** 2).mean().round(4).alias("brier_modelo")).sort("kind")
    recent = df.sort("ts_signal", descending=True).head(60).select(
        "ts_signal", "ts_exit", "kind", "condition_id", "size_filled", "predicted_pnl", "realized_pnl", "error", "exit_reason",
        "confidence", "run_id", "mode").to_dicts()
    summary = {
        "equity": round(start_cash + float(df["realized_pnl"].sum()), 4), "pnl": round(float(df["realized_pnl"].sum()), 4),
        "positions_closed": int(df.height), "positions_filled": int(filled.height),
        "fill_rate": round(filled.height / df.height, 3) if df.height else None,
        "win_rate": round(float((filled["realized_pnl"] > 0).mean()), 3) if filled.height else None,
        "pnl_valid": round(float(valid["realized_pnl"].sum()), 4) if valid.height else 0.0, "n_valid": int(valid.height),
        "fees": round(float(df["fees"].sum()), 4), "last_ts": int(df["ts_signal"].max()),
        "runs": sorted(df["run_id"].unique().to_list()), "mode": str(df.sort("ts_signal")["mode"][-1]),
    }
    return {"equity": equity, "by_kind": _rows(by_kind), "exit_reasons": _rows(exit_reasons), "calibration": _rows(calib),
            "model_vs_heuristic": _rows(mv), "recent_positions": recent, "summary": summary}


def _signals_timeline(data_dir: Path, bucket_min: int = 15) -> dict[str, Any]:
    lf = scan(data_dir, "signals")
    if lf is None:
        return {"timeline": [], "by_kind": [], "last_hour": 0}
    df = lf.select("ts_ms", "kind", "edge_net", "confidence").collect()
    if not df.height:
        return {"timeline": [], "by_kind": [], "last_hour": 0}
    b = bucket_min * 60_000
    tl = df.with_columns((pl.col("ts_ms") // b * b).alias("t")).group_by(["t", "kind"]).agg(pl.len().alias("n")).sort("t")
    bk = df.group_by("kind").agg(pl.len().alias("n"), pl.col("edge_net").mean().round(4).alias("edge_medio"),
                                 pl.col("confidence").mean().round(3).alias("conf_media")).sort("n", descending=True)
    now = int(time.time() * 1000)
    return {"timeline": _rows(tl), "by_kind": _rows(bk), "last_hour": int(df.filter(pl.col("ts_ms") >= now - 3_600_000).height)}


def _games(cfg: Config, data_dir: Path, limit: int = 30) -> list[dict[str, Any]]:
    mk, glf, qlf = latest_markets(data_dir), scan(data_dir, "games"), scan(data_dir, "quotes")
    if mk is None or glf is None:
        return []
    games = glf.sort("ts_ms").group_by("game_id").last().sort("ts_ms", descending=True).collect()
    qmap: dict[str, dict[str, Any]] = {}
    if qlf is not None:
        q = qlf.sort("ts_ms").group_by("token_id").agg(pl.col("mid").last().alias("mid"), pl.col("mid").first().alias("mid_first"),
                                                     pl.col("best_bid").last().alias("bid"), pl.col("best_ask").last().alias("ask")).collect()
        qmap = {r["token_id"]: r for r in q.to_dicts()}
    markets = [MarketInfo.from_row(r) for r in mk.to_dicts()]
    by_game: dict[str, list[MarketInfo]] = {}
    for m in markets:
        if m.event_game_id:
            by_game.setdefault(m.event_game_id, []).append(m)
    reg = ModelRegistry(cfg.models.sigma_basketball, cfg.models.sigma_by_league, cfg.models.soccer_total_goals)
    out = []
    for r in games.to_dicts():
        ms = by_game.get(r["game_id"])
        if not ms:
            continue
        g = parse_game(r)
        mls = [m for m in ms if m.sports_market_type in ("", "moneyline", "child_moneyline")]
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
        wp = None
        if g.sport in ("basketball", "tennis", "soccer"):
            try:
                wp = reg.prob(g, pre)
            except Exception:  # noqa: BLE001
                wp = None
        mrows = []
        for m in mls:
            toks = []
            for t in m.tokens:
                side = match_outcome(t.outcome, g.home, g.away, m.question)
                q = qmap.get(t.token_id)
                pm = wp.for_side(side) if (wp is not None and side) else None
                mid = q["mid"] if q else None
                toks.append({"outcome": t.outcome, "side": side, "mid": mid, "bid": q["bid"] if q else None,
                             "ask": q["ask"] if q else None, "model": None if pm is None else round(pm, 4),
                             "dev": None if (pm is None or mid is None) else round(pm - mid, 4)})
            mrows.append({"question": m.question, "fee_rate": m.fee_rate, "condition_id": m.condition_id, "tokens": toks})
        out.append({"game_id": g.game_id, "league": g.league, "sport": g.sport, "home": g.home, "away": g.away,
                    "score": r["score"], "period": r["period"], "elapsed": r["elapsed"], "live": g.live, "ended": g.ended,
                    "ts_ms": r["ts_ms"], "model": wp.model if wp else None, "has_model": wp is not None,
                    "pregame": None if pre is None else {"home": round(pre.home, 3), "away": round(pre.away, 3), "draw": round(pre.draw, 3)},
                    "markets": mrows})
        if len(out) >= limit:
            break
    out.sort(key=lambda x: (not x["live"], x["ended"], -x["ts_ms"]))
    return out


def _wallets(data_dir: Path, limit: int = 40) -> list[dict[str, Any]]:
    df = latest_profiles(data_dir)
    if df is None:
        return []
    cols = ["wallet", "name", "n_closed", "wins", "losses", "win_rate", "roi", "realized_pnl", "total_bought", "n_open",
            "open_value", "score", "ts_ms", "truncated", "biggest_win", "biggest_loss"]
    cols = [c for c in cols if c in df.columns]
    return df.sort("score", descending=True).head(limit).select(cols).to_dicts()


def _flow(data_dir: Path, min_usd: float, limit: int = 60) -> list[dict[str, Any]]:
    lf = scan(data_dir, "flow_trades")
    if lf is None:
        return []
    df = lf.filter(pl.col("usd") >= min_usd).sort("ts_ms", descending=True).head(limit).collect()
    prof = latest_profiles(data_dir)
    scores = dict(zip(prof["wallet"], prof["score"])) if prof is not None else {}
    out = []
    for r in df.to_dicts():
        r["score"] = scores.get(r["wallet"])
        out.append(r)
    return out


def _markets(data_dir: Path) -> dict[str, Any]:
    mk = latest_markets(data_dir)
    if mk is None:
        return {"by_category": [], "top": [], "active": 0}
    act = mk.filter(pl.col("status") != "removed")
    byc = act.group_by("category").agg(pl.len().alias("n"), pl.col("volume_24h").sum().round(0).alias("volume")).sort("n", descending=True)
    top = act.sort("volume_24h", descending=True).head(15).select("question", "category", "fee_rate", "volume_24h", "sports_market_type", "event_title").to_dicts()
    return {"by_category": _rows(byc), "top": top, "active": int(act.height)}


def _models(data_dir: Path) -> list[dict[str, Any]]:
    store = ModelStore(data_dir)
    out = []
    for k in store.kinds():
        for h in store.history(k):
            out.append({"kind": k, **h})
    return out


def _oportunidades(cfg: Config) -> dict[str, Any]:
    ops = listar_oportunidades(cfg.data_dir, minutos=30)
    grupos = por_grupo(ops)
    return {
        "total": len(ops), "vigentes": sum(1 for o in ops if o.fresca),
        "grupos": [{"nombre": g, "resumen": resumen_grupo(lista),
                    "lista": [o.to_dict() for o in lista[:10]]} for g, lista in grupos.items()],
    }


def _ejecucion(cfg: Config, run_id: str | None) -> list[dict[str, Any]]:
    """Métricas de ejecución por estrategia, de la misma fuente que el veredicto de 'listo'."""
    from ..evaluacion import evaluar as evaluar_metricas
    try:
        return [e.to_dict() for e in evaluar_metricas(cfg.data_path, run_id, cfg.sim.fill_baseline_prob)]
    except Exception:  # noqa: BLE001 - el panel nunca debe caerse por un informe
        log.exception("no se pudieron calcular las métricas de ejecución")
        return []


def _decisiones(data_dir: Path, horas: float = 24) -> dict[str, Any]:
    """Qué decidió el motor, incluidas las de NO operar. Sin esto no se ve lo que se descartó."""
    lf = scan(data_dir, "decisions")
    if lf is None:
        return {"motivos": [], "total": 0, "no_trade": 0, "trade": 0}
    desde = int((time.time() - horas * 3600) * 1000)
    df = lf.filter(pl.col("ts_ms") >= desde).collect()
    if not df.height:
        return {"motivos": [], "total": 0, "no_trade": 0, "trade": 0}
    nt = df.filter(pl.col("decision") == "no_trade")
    motivos = (nt.group_by(["strategy", "motivo"]).agg(pl.len().alias("n"))
               .sort("n", descending=True).head(20)) if nt.height else None
    return {"motivos": _rows(motivos), "total": int(df.height), "no_trade": int(nt.height),
            "trade": int(df.filter(pl.col("decision") == "trade").height)}


def _reacciones(data_dir: Path, limite: int = 12) -> dict[str, Any]:
    """Cuánto tarda el mercado en reaccionar a lo que pasa en el partido, por liga."""
    lf = scan(data_dir, "reactions")
    if lf is None:
        return {"por_liga": [], "n": 0}
    df = lf.collect()
    if not df.height:
        return {"por_liga": [], "n": 0}
    por_liga = (df.group_by("league").agg(
        pl.len().alias("eventos"),
        pl.col("reacciono").mean().round(3).alias("tasa_reaccion"),
        pl.col("lag_ms").median().alias("lag_mediano_ms"),
        pl.col("movimiento").abs().mean().round(5).alias("movimiento_medio"),
    ).sort("eventos", descending=True).head(limite))
    return {"por_liga": _rows(por_liga), "n": int(df.height)}


def build_payload(cfg: Config, run_id: str | None = None) -> dict[str, Any]:
    data_dir = cfg.data_path
    led = _ledger(data_dir, run_id)
    sections = _ledger_sections(led, cfg.sim.start_cash)
    tables = _table_status(data_dir)
    games = _games(cfg, data_dir)
    wallets = _wallets(data_dir)
    sig = _signals_timeline(data_dir)
    now = int(time.time() * 1000)
    last_data = max((t["max_ts"] or 0) for t in tables if t["table"] in ("book_deltas", "quotes", "trades")) or None
    summary = {
        **sections["summary"], "start_cash": cfg.sim.start_cash,
        "signals_total": sum(b["n"] for b in sig["by_kind"]), "signals_last_hour": sig["last_hour"],
        "last_data_ts": last_data, "data_age_s": None if not last_data else max(0, (now - last_data) // 1000),
        "markets_active": _markets(data_dir)["active"], "games_live": sum(1 for g in games if g["live"] and not g["ended"]),
        "games_with_model": sum(1 for g in games if g["live"] and g["has_model"]),
        "wallets_profiled": len(wallets), "wallets_smart": sum(1 for w in wallets if w.get("score", 0) >= cfg.flow.smart_min_score and w.get("n_closed", 0) >= cfg.flow.smart_min_closed),
        "models_current": sum(1 for m in _models(data_dir) if m["current"]),
    }
    ops = _oportunidades(cfg)
    summary["oportunidades_vigentes"] = ops["vigentes"]
    ejec = _ejecucion(cfg, run_id)
    dec = _decisiones(data_dir)
    summary["no_trade_24h"] = dec["no_trade"]
    con_ordenes = [e for e in ejec if e["ejecucion"]["ordenes"]]
    summary["tasa_llenado_observada"] = (
        round(sum(e["ejecucion"]["llenadas"] for e in con_ordenes) /
              sum(e["ejecucion"]["ordenes"] for e in con_ordenes), 4) if con_ordenes else None)
    return {
        "generated_ms": now, "config": {"categories": list(cfg.categories), "min_edge_net": cfg.signals.min_edge_net,
                                        "target_size": cfg.signals.target_size, "latency_ms": cfg.sim.latency_ms,
                                        "fill_baseline_prob": cfg.sim.fill_baseline_prob, "whale_min_usd": cfg.flow.whale_min_usd,
                                        "smart_min_score": cfg.flow.smart_min_score, "sigma_basketball": cfg.models.sigma_basketball,
                                        "learn_min_train": cfg.learn.min_train, "learn_min_examples": cfg.learn.min_examples},
        "summary": summary, "equity": sections["equity"], "by_kind": sections["by_kind"], "exit_reasons": sections["exit_reasons"],
        "calibration": sections["calibration"], "model_vs_heuristic": sections["model_vs_heuristic"],
        "recent_positions": sections["recent_positions"], "signals": sig, "games": games, "wallets": wallets,
        "oportunidades": ops, "ejecucion": ejec, "decisiones": dec, "reacciones": _reacciones(data_dir),
        "flow": _flow(data_dir, cfg.flow.whale_min_usd / 2), "markets": _markets(data_dir), "models": _models(data_dir),
        "tables": tables,
    }


def snapshot_html(cfg: Config, run_id: str | None = None) -> str:
    """Página autónoma con los datos embebidos (para compartir o publicar sin servidor)."""
    html = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
    payload = json.dumps(build_payload(cfg, run_id), default=str).replace("</", "<\\/")
    return html.replace("<!--SNAPSHOT-->", f"<script>window.__SNAPSHOT__ = {payload};</script>")
