"""Fase 1: recolector. Descubre mercados, mantiene libros en memoria y persiste todo.

Eventos que emite a los listeners (para paper trading):
    ("markets", ts_ms, list[MarketInfo])         tras cada discovery
    ("book",    ts_ms, token_id, OrderBook)      snapshot completo aplicado
    ("delta",   ts_ms, token_id, OrderBook)      nivel actualizado
    ("trade",   ts_ms, token_id, dict)           trade impreso
    ("resolution", ts_ms, condition_id, dict)    mercado resuelto
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
from .storage import ParquetWriter, dumps

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
        self.listeners: list[Listener] = []
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self.stats: dict[str, int] = {"book": 0, "delta": 0, "trade": 0, "tick": 0, "resync": 0, "resolved": 0}
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
        await self._stop.wait()
        log.info("deteniendo recolector…")
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.pool.stop()
        self.writer.close()
        await self.gamma.close()
        await self.rest.close()
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

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(5)
            self.writer.maybe_flush()

    async def _status_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            valid = sum(1 for b in self.books.values() if b.is_valid)
            log.info("estado: mercados=%d libros_validos=%d/%d ws=%s eventos=%s filas=%s",
                     len(self.markets), valid, len(self.books), self.pool.stats(), dict(self.stats),
                     dict(self.writer.rows_written))


def _fnum(x: Any) -> float | None:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None
