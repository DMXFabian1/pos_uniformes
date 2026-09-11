"""Replay: reconstruye los libros desde Parquet y corre el motor sobre el histórico."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from ..config import Config
from ..discovery import MarketInfo
from ..experimento import congelar, registrar
from ..storage import ParquetWriter, latest_markets, latest_profiles, scan
from ..wallets import WalletProfile
from .engine import Engine

log = logging.getLogger(__name__)


def _parse_ts(s: str | None, default: int) -> int:
    if not s:
        return default
    if s.isdigit():
        return int(s)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _in_range(lf: pl.LazyFrame | None, t0: int, t1: int, tokens: set[str] | None) -> pl.DataFrame | None:
    if lf is None:
        return None
    lf = lf.filter((pl.col("ts_ms") >= t0) & (pl.col("ts_ms") <= t1))
    if tokens:
        lf = lf.filter(pl.col("token_id").is_in(list(tokens)))
    return lf.sort("ts_ms").collect()


def run_replay(cfg: Config, start: str | None = None, end: str | None = None, conditions: list[str] | None = None,
               run_id: str | None = None, persist: bool = True) -> Engine:
    data_dir = cfg.data_path
    mk = latest_markets(data_dir)
    if mk is None:
        raise SystemExit("no hay tabla markets en data/. Corre `scalper collect` primero.")
    markets = [MarketInfo.from_row(r) for r in mk.to_dicts()]
    if conditions:
        markets = [m for m in markets if m.condition_id in set(conditions)]
    tokens = {t.token_id for m in markets for t in m.tokens} if conditions else None
    t0, t1 = _parse_ts(start, 0), _parse_ts(end, int(time.time() * 1000))
    snaps = _in_range(scan(data_dir, "book_snapshots"), t0, t1, tokens)
    deltas = _in_range(scan(data_dir, "book_deltas"), t0, t1, tokens)
    trades = _in_range(scan(data_dir, "trades"), t0, t1, tokens)
    res_lf = scan(data_dir, "resolutions")
    resolutions = res_lf.filter((pl.col("ts_ms") >= t0) & (pl.col("ts_ms") <= t1)).collect() if res_lf is not None else None
    games_lf = scan(data_dir, "games")
    # los partidos se cargan desde antes del rango para tener el estado previo y el precio pregame
    games = games_lf.filter(pl.col("ts_ms") <= t1).sort("ts_ms").collect() if games_lf is not None else None
    flow_lf = scan(data_dir, "flow_trades")
    flows = flow_lf.filter((pl.col("ts_ms") >= t0) & (pl.col("ts_ms") <= t1)).sort("ts_ms").collect() if flow_lf is not None else None
    if conditions and flows is not None:
        flows = flows.filter(pl.col("condition_id").is_in(list(conditions)))

    run_id = run_id or f"replay-{int(time.time())}"
    exp = congelar(cfg, nota=f"replay {run_id}")
    if persist:
        registrar(cfg, exp)
    writer = ParquetWriter(data_dir, flush_seconds=10**9, flush_rows=10**9, subdir=f"run={run_id}") if persist else None
    eng = Engine(cfg, run_id, "replay", writer, experiment=exp.experiment_id)
    eng.set_markets(markets)
    prof = latest_profiles(data_dir)
    if prof is not None:
        fields = set(WalletProfile.__dataclass_fields__)
        eng.attach_wallets({r["wallet"]: WalletProfile(**{k: v for k, v in r.items() if k in fields and v is not None})
                            for r in prof.to_dicts()})

    # corriente unificada: (ts, prioridad, tipo, fila)
    stream: list[tuple[int, int, str, dict]] = []
    if snaps is not None:
        stream += [(r["ts_ms"], 0, "book", r) for r in snaps.to_dicts()]
    if deltas is not None:
        stream += [(r["ts_ms"], 1, "delta", r) for r in deltas.to_dicts()]
    if trades is not None:
        stream += [(r["ts_ms"], 2, "trade", r) for r in trades.to_dicts()]
    if resolutions is not None:
        by_cid: dict[str, list[dict]] = {}
        for r in resolutions.to_dicts():
            by_cid.setdefault(r["condition_id"], []).append(r)
        for cid, rows in by_cid.items():
            stream.append((rows[0]["ts_ms"], 3, "resolution", {"condition_id": cid, "tokens": rows}))
    if games is not None:
        # estados anteriores al rango se aplican primero (prioridad -1) para arrancar con contexto
        stream += [(max(r["ts_ms"], t0), -1 if r["ts_ms"] < t0 else 4, "game", r) for r in games.to_dicts()]
    if flows is not None:
        stream += [(r["ts_ms"], 5, "flow", r) for r in flows.to_dicts()]
    stream.sort(key=lambda x: (x[0], x[1]))
    log.info("replay %s: %d mercados, %d eventos (%s → %s)", run_id, len(markets), len(stream),
             datetime.fromtimestamp(t0 / 1000, tz=timezone.utc) if t0 else "inicio", datetime.fromtimestamp(t1 / 1000, tz=timezone.utc))

    last_tick = 0
    for ts, _, kind, r in stream:
        if kind == "book":
            b = eng.books.get(r["token_id"])
            if b is None:
                continue
            bids = [{"price": p, "size": s} for p, s in json.loads(r["bids"])]
            asks = [{"price": p, "size": s} for p, s in json.loads(r["asks"])]
            b.apply_snapshot(bids, asks, ts, r.get("hash") or "")
            eng.on_book(ts, r["token_id"], b)
        elif kind == "delta":
            b = eng.books.get(r["token_id"])
            if b is None or b.snapshot_ts == 0:
                continue
            cambio = b.apply_delta(r["side"], r["price"], r["size"], ts, r.get("hash") or "")
            eng.on_book(ts, r["token_id"], b, {"side": r["side"], "price": r["price"], "size": r["size"], "delta": cambio})
        elif kind == "trade":
            eng.on_trade(ts, r["token_id"], r)
        elif kind == "resolution":
            eng.on_resolution(ts, r["condition_id"], r)
        elif kind == "game":
            eng.on_game(ts, r["game_id"], r)
        elif kind == "flow":
            eng.on_flow(ts, r["condition_id"], r)
        if ts - last_tick > 1000:
            eng.tick(ts)
            last_tick = ts
    eng.close_all(t1 if stream else t0, "end")
    if writer is not None:
        writer.close()
    log.info("resumen: %s", eng.summary())
    return eng
