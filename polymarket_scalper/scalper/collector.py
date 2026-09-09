"""Fase 1: recolector. Descubre mercados, mantiene libros en memoria y persiste todo.

Eventos que emite a los listeners (para paper trading):
    ("markets", ts_ms, list[MarketInfo])         tras cada discovery
    ("book",    ts_ms, token_id, OrderBook)      snapshot completo aplicado
    ("delta",   ts_ms, token_id, OrderBook)      nivel actualizado
    ("trade",   ts_ms, token_id, dict)           trade impreso
    ("resolution", ts_ms, condition_id, dict)    mercado resuelto
    ("game",    ts_ms, game_id, dict)            estado de partido en vivo (fila de `games`)
    ("flow",    ts_ms, condition_id, dict)       trade con wallet (fila de `flow_trades`)
"""
from __future__ import annotations

import asyncio
import logging
import signal
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .book import OrderBook
from .clob import ClobRest, WebSocketPool
from .config import Config
from .discovery import GammaClient, MarketInfo, discover_markets
from .flow import DataApi, FlowPoller, flow_row
from .sports_feed import SportsFeed, normalize_game, state_key
from .storage import ParquetWriter, dumps
from .wallets import WalletTracker

log = logging.getLogger(__name__)

Listener = Callable[[tuple], Awaitable[None]]


def now_ms() -> int:
    return int(time.time() * 1000)


class Collector:
    def __init__(self, cfg: Config, writer: ParquetWriter | None = None, persist: bool = True):
        self.cfg = cfg
        self.persist = persist
        self.writer = writer or ParquetWriter(cfg.data_dir, cfg.collector.flush_seconds, cfg.collector.flush_rows)
        self.gamma = GammaClient(cfg.collector.gamma_url)
        self.rest = ClobRest(cfg.collector.clob_url)
        self.pool = WebSocketPool(cfg.collector.ws_url, self._on_ws_message, cfg.collector.assets_per_connection)
        self.markets: dict[str, MarketInfo] = {}           # condition_id -> info
        self.token_to_cid: dict[str, str] = {}
        self.books: dict[str, OrderBook] = {}
        self.pending_resolution: dict[str, MarketInfo] = {}  # mercados retirados que aún no se resolvieron
        self.game_to_cids: dict[str, list[str]] = {}
        self.games: dict[str, dict[str, Any]] = {}          # último estado por game_id
        self.sports: SportsFeed | None = None
        self.data_api: DataApi | None = None
        self.flow: FlowPoller | None = None
        self.wallets: WalletTracker | None = None
        if cfg.sports_feed.enabled:
            self.sports = SportsFeed(cfg.sports_feed.ws_url, self._on_game)
        if cfg.flow.enabled:
            self.data_api = DataApi(cfg.flow.data_api_url)
            self.flow = FlowPoller(self.data_api, self._on_flow_trade, cfg.flow.poll_seconds, cfg.flow.page_size)
            self.wallets = WalletTracker(self.data_api, self.writer if persist else None, cfg.flow.profile_max_pages,
                                         cfg.flow.profile_refresh_hours, cfg.flow.per_wallet_delay_seconds)
        self.listeners: list[Listener] = []
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self.stats: dict[str, int] = {"book": 0, "delta": 0, "trade": 0, "tick": 0, "resync": 0, "resolved": 0,
                                      "game": 0, "flow": 0, "whale": 0}
        self.started_ms = now_ms()

    # ------------------------------------------------------------------ ciclo de vida
    def add_listener(self, fn: Listener) -> None:
        self.listeners.append(fn)

    async def _emit(self, event: tuple) -> None:
        for fn in self.listeners:
            try:
                await fn(event)
            except Exception:  # noqa: BLE001 - un listener roto no tumba la recolección
                log.exception("listener falló en evento %s", event[0])

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.stop)
            except NotImplementedError:
                pass
        await self.refresh_markets()
        self._tasks = [
            asyncio.create_task(self._discovery_loop(), name="discovery"),
            asyncio.create_task(self._quote_loop(), name="quotes"),
            asyncio.create_task(self._resync_loop(), name="resync"),
            asyncio.create_task(self._resolution_loop(), name="resolutions"),
            asyncio.create_task(self._flush_loop(), name="flush"),
            asyncio.create_task(self._status_loop(), name="status"),
        ]
        if self.cfg.retention.enabled and self.persist:
            self._tasks.append(asyncio.create_task(self._retention_loop(), name="retention"))
        if self.sports is not None:
            self._tasks.append(asyncio.create_task(self.sports.run(), name="sports"))
        if self.flow is not None and self.wallets is not None:
            self._tasks.append(asyncio.create_task(self.flow.run(), name="flow"))
            self._tasks.append(asyncio.create_task(self.wallets.run(), name="wallets"))
        await self._stop.wait()
        log.info("deteniendo recolector…")
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.pool.stop()
        self.writer.close()
        await self.gamma.close()
        await self.rest.close()
        if self.data_api is not None:
            await self.data_api.close()
        log.info("filas escritas: %s", dict(self.writer.rows_written))

    # ------------------------------------------------------------------ discovery
    async def refresh_markets(self) -> None:
        found = await discover_markets(self.cfg, self.gamma)
        ts = now_ms()
        new_ids = {m.condition_id for m in found}
        removed = [cid for cid in self.markets if cid not in new_ids]
        for cid in removed:
            mi = self.markets.pop(cid)
            self.pending_resolution[cid] = mi
            await self.pool.drop(mi.token_ids)
            for t in mi.token_ids:
                self.token_to_cid.pop(t, None)
                self.books.pop(t, None)
            if self.persist:
                self.writer.append("markets", mi.to_row(ts, status="removed"))
        new_tokens: list[str] = []
        for mi in found:
            is_new = mi.condition_id not in self.markets
            self.markets[mi.condition_id] = mi
            for t in mi.tokens:
                self.token_to_cid[t.token_id] = mi.condition_id
                if t.token_id not in self.books:
                    self.books[t.token_id] = OrderBook(t.token_id, mi.condition_id, mi.tick_size)
                    new_tokens.append(t.token_id)
                else:
                    self.books[t.token_id].tick_size = mi.tick_size
            if self.persist:
                self.writer.append("markets", mi.to_row(ts, status="new" if is_new else "active"))
        self.game_to_cids = {}
        for mi in self.markets.values():
            if mi.event_game_id:
                self.game_to_cids.setdefault(mi.event_game_id, []).append(mi.condition_id)
        if new_tokens:
            await self.pool.ensure(new_tokens)
        log.info("mercados activos=%d tokens=%d nuevos=%d retirados=%d", len(self.markets),
                 len(self.token_to_cid), len(new_tokens), len(removed))
        await self._emit(("markets", ts, list(self.markets.values())))

    async def _discovery_loop(self) -> None:
        while True:
            await asyncio.sleep(self.cfg.discovery.refresh_seconds)
            try:
                await self.refresh_markets()
            except Exception:  # noqa: BLE001
                log.exception("discovery falló")

    # ------------------------------------------------------------------ websocket
    async def _on_ws_message(self, msg: dict[str, Any]) -> None:
        et = msg.get("event_type")
        ts = int(msg.get("timestamp") or now_ms())
        if et == "book":
            await self._apply_snapshot(msg.get("asset_id", ""), msg.get("bids") or [], msg.get("asks") or [],
                                       ts, msg.get("hash", ""), source="ws")
        elif et == "price_change":
            for ch in msg.get("price_changes") or []:
                tid = ch.get("asset_id", "")
                book = self.books.get(tid)
                if book is None:
                    continue
                price, size = float(ch["price"]), float(ch["size"])
                book.apply_delta(ch.get("side", ""), price, size, ts, ch.get("hash", ""))
                self.stats["delta"] += 1
                if self.persist:
                    self.writer.append("book_deltas", {
                        "ts_ms": ts, "token_id": tid, "condition_id": book.condition_id, "side": ch.get("side", ""),
                        "price": price, "size": size, "best_bid": _fnum(ch.get("best_bid")),
                        "best_ask": _fnum(ch.get("best_ask")), "hash": ch.get("hash", ""),
                    })
                await self._emit(("delta", ts, tid, book))
        elif et == "last_trade_price":
            tid = msg.get("asset_id", "")
            cid = self.token_to_cid.get(tid, msg.get("market", ""))
            trade = {"ts_ms": ts, "token_id": tid, "condition_id": cid, "price": float(msg.get("price") or 0),
                     "size": float(msg.get("size") or 0), "side": msg.get("side", ""),
                     "fee_rate_bps": _fnum(msg.get("fee_rate_bps")), "tx_hash": msg.get("transaction_hash", "")}
            self.stats["trade"] += 1
            if self.persist:
                self.writer.append("trades", trade)
            await self._emit(("trade", ts, tid, trade))
        elif et == "tick_size_change":
            tid = msg.get("asset_id", "")
            book = self.books.get(tid)
            if book is not None:
                book.tick_size = float(msg.get("new_tick_size") or book.tick_size)
                self.stats["tick"] += 1

    async def _apply_snapshot(self, tid: str, bids: list, asks: list, ts: int, hash_: str, source: str) -> None:
        book = self.books.get(tid)
        if book is None:
            return
        book.apply_snapshot(bids, asks, ts, hash_)
        self.stats["book"] += 1
        if self.persist:
            self.writer.append("book_snapshots", {
                "ts_ms": ts, "token_id": tid, "condition_id": book.condition_id,
                "bids": dumps([[float(l["price"]), float(l["size"])] for l in bids]),
                "asks": dumps([[float(l["price"]), float(l["size"])] for l in asks]),
                "hash": hash_, "source": source,
            })
        await self._emit(("book", ts, tid, book))

    # ------------------------------------------------------------------ feed de deportes
    async def _on_game(self, msg: dict[str, Any]) -> None:
        ts = now_ms()
        row = normalize_game(msg, ts)
        gid = row["game_id"]
        linked = gid in self.game_to_cids
        if not linked and not self.cfg.sports_feed.store_all_leagues:
            return
        prev = self.games.get(gid)
        if prev is not None and state_key(prev) == state_key(row):
            return                                   # mismo estado repetido
        self.games[gid] = row
        self.stats["game"] += 1
        if self.persist:
            self.writer.append("games", row)
        await self._emit(("game", ts, gid, {**row, "condition_ids": self.game_to_cids.get(gid, [])}))

    # ------------------------------------------------------------------ flujo con wallet
    async def _on_flow_trade(self, t: dict[str, Any]) -> None:
        row = flow_row(t)
        followed = row["condition_id"] in self.markets
        if not followed and row["usd"] < self.cfg.flow.min_usd_global:
            return
        self.stats["flow"] += 1
        if self.persist:
            self.writer.append("flow_trades", row)
        if row["usd"] >= self.cfg.flow.whale_min_usd and self.wallets is not None:
            self.stats["whale"] += 1
            self.wallets.enqueue(row["wallet"], row["name"])
        await self._emit(("flow", row["ts_ms"], row["condition_id"], {**row, "followed": followed}))

    def live_games(self) -> list[dict[str, Any]]:
        return [g for g in self.games.values() if g["live"] and not g["ended"]]

    # ------------------------------------------------------------------ loops auxiliares
    async def _quote_loop(self) -> None:
        period = self.cfg.collector.quote_sample_seconds
        while True:
            await asyncio.sleep(period)
            if not self.persist:
                continue
            ts = now_ms()
            for tid, b in self.books.items():
                if not b.is_valid or b.snapshot_ts == 0:
                    continue
                self.writer.append("quotes", {
                    "ts_ms": ts, "token_id": tid, "condition_id": b.condition_id, "best_bid": b.best_bid,
                    "best_ask": b.best_ask, "bid_size": b.best_bid_size, "ask_size": b.best_ask_size,
                    "mid": b.mid, "spread": b.spread, "bid_depth_5t": b.depth_within("BUY", 5),
                    "ask_depth_5t": b.depth_within("SELL", 5),
                })

    async def _resync_loop(self) -> None:
        """Re-descarga cada libro por REST de forma escalonada. Corrige deltas perdidos."""
        while True:
            tokens = list(self.books)
            period = self.cfg.collector.rest_resync_seconds
            if not tokens:
                await asyncio.sleep(5)
                continue
            gap = max(period / max(len(tokens), 1), 0.25)
            for tid in tokens:
                await asyncio.sleep(gap)
                if tid not in self.books:
                    continue
                data = await self.rest.get_book(tid)
                if not data:
                    continue
                ts = int(data.get("timestamp") or now_ms())
                book = self.books.get(tid)
                if book is not None and data.get("tick_size"):
                    book.tick_size = float(data["tick_size"])
                await self._apply_snapshot(tid, data.get("bids") or [], data.get("asks") or [], ts,
                                           data.get("hash", ""), source="rest")
                self.stats["resync"] += 1

    async def _resolution_loop(self) -> None:
        while True:
            await asyncio.sleep(self.cfg.collector.resolution_poll_seconds)
            nowiso = datetime.now(timezone.utc).isoformat()
            # Mercados activos cuya fecha de fin ya pasó también se revisan
            candidates = dict(self.pending_resolution)
            for cid, mi in self.markets.items():
                if mi.end_date and mi.end_date < nowiso:
                    candidates[cid] = mi
            for cid, mi in candidates.items():
                await asyncio.sleep(0.3)
                data = await self.rest.get_market(cid)
                if not data:
                    continue
                toks = data.get("tokens") or []
                if data.get("closed") and any(t.get("winner") for t in toks):
                    ts = now_ms()
                    rows = []
                    for t in toks:
                        row = {"ts_ms": ts, "condition_id": cid, "token_id": str(t.get("token_id")),
                               "outcome": str(t.get("outcome")), "winner": bool(t.get("winner")),
                               "final_price": float(t.get("price") or 0)}
                        rows.append(row)
                        if self.persist:
                            self.writer.append("resolutions", row)
                    self.pending_resolution.pop(cid, None)
                    self.stats["resolved"] += 1
                    await self._emit(("resolution", ts, cid, {"tokens": rows}))

    async def _retention_loop(self) -> None:
        from .retention import apply_retention
        period = max(self.cfg.retention.run_hours, 0.05) * 3600
        while True:
            await asyncio.sleep(period)
            try:
                self.writer.flush()
                rep = await asyncio.to_thread(apply_retention, self.cfg)
                log.info("retención de disco: %s", rep.summary())
            except Exception:  # noqa: BLE001
                log.exception("retención falló")

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(5)
            self.writer.maybe_flush()

    async def _status_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            valid = sum(1 for b in self.books.values() if b.is_valid)
            extra = ""
            if self.flow is not None and self.wallets is not None:
                extra = (f" flow_polls={self.flow.polls} flow_lag={self.flow.lag_seconds}s"
                         f" wallets={len(self.wallets.profiles)} cola={self.wallets.pending}")
            if self.sports is not None:
                extra += f" partidos_vivos={len(self.live_games())}"
            log.info("estado: mercados=%d libros_validos=%d/%d ws=%s eventos=%s filas=%s%s",
                     len(self.markets), valid, len(self.books), self.pool.stats(), dict(self.stats),
                     dict(self.writer.rows_written), extra)


def _fnum(x: Any) -> float | None:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None
