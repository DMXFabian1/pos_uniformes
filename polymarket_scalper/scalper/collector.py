"""Fase 1: recolector. Descubre mercados, mantiene libros en memoria y persiste todo.

Eventos que emite a los listeners (para paper trading):
    ("markets", ts_ms, list[MarketInfo])         tras cada discovery
    ("book",    ts_ms, token_id, OrderBook)      snapshot completo aplicado
    ("delta",   ts_ms, token_id, OrderBook, dict) nivel actualizado; dict = {side, price, size, delta}
    ("trade",   ts_ms, token_id, dict)           trade impreso
    ("resolution", ts_ms, condition_id, dict)    mercado resuelto
    ("game",    ts_ms, game_id, dict)            estado de partido en vivo (fila de `games`)
    ("flow",    ts_ms, condition_id, dict)       trade con wallet (fila de `flow_trades`)
    ("price",   ts_ms, symbol, dict)             precio de referencia de cripto
    ("updown",  ts_ms, condition_id, dict)       ventana "Up or Down" activa, con su strike
    ("updown_settle", ts_ms, condition_id, dict) ventana cerrada: quién ganó
"""
from __future__ import annotations

import asyncio
import bisect
import logging
import signal
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .book import OrderBook
from .clob import ClobRest, WebSocketPool
from .config import Config
from .crypto_feed import CryptoFeed
from .discovery import GammaClient, MarketInfo, discover_markets, discover_updown
from .flow import DataApi, FlowPoller, flow_row
from .keepawake import KeepAwake
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
        self.crypto: CryptoFeed | None = None
        self.prices: dict[str, deque] = defaultdict(lambda: deque(maxlen=20000))  # símbolo -> (ts_ms, precio)
        self._price_last_saved: dict[str, int] = {}
        self.updown: dict[str, MarketInfo] = {}             # condition_id -> ventana activa
        self.strikes: dict[str, tuple[float, int]] = {}     # condition_id -> (strike, ts del strike)
        self._updown_done: set[str] = set()
        if cfg.updown.enabled:
            syms = {sl.split("-")[0] for sl in cfg.updown.series}
            self.crypto = CryptoFeed(cfg.updown.ws_url, self._on_price, syms or None)
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
        self._closed = False
        self._tasks: list[asyncio.Task] = []
        self.stats: dict[str, int] = {"book": 0, "delta": 0, "trade": 0, "tick": 0, "resync": 0, "resolved": 0,
                                      "game": 0, "flow": 0, "whale": 0, "updown_resueltas": 0}
        self.started_ms = now_ms()
        self.latencias: deque = deque(maxlen=5000)     # recv_ms - ts_ms de los últimos mensajes del CLOB

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
        """Recolecta hasta stop() o Ctrl+C. El cierre siempre vuelca los buffers a disco."""
        with KeepAwake(self.cfg.collector.prevent_sleep):
            try:
                await self._run_inner()
            except (KeyboardInterrupt, asyncio.CancelledError):
                # en Windows no hay add_signal_handler: Ctrl+C llega como excepción aquí
                log.info("interrumpido; guardando lo pendiente…")
            finally:
                await self._shutdown()

    async def _run_inner(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.stop)
            except (NotImplementedError, AttributeError, ValueError):
                pass        # Windows, o un hilo que no es el principal
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
        if self.crypto is not None:
            self._tasks.append(asyncio.create_task(self.crypto.run(), name="precios"))
            self._tasks.append(asyncio.create_task(self._updown_loop(), name="updown"))
        if self.sports is not None:
            self._tasks.append(asyncio.create_task(self.sports.run(), name="sports"))
        if self.flow is not None and self.wallets is not None:
            self._tasks.append(asyncio.create_task(self.flow.run(), name="flow"))
            self._tasks.append(asyncio.create_task(self.wallets.run(), name="wallets"))
        await self._stop.wait()

    async def _shutdown(self) -> None:
        """Idempotente: se puede llamar dos veces sin efectos raros."""
        if self._closed:
            return
        self._closed = True
        log.info("deteniendo recolector…")
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        try:
            await self.pool.stop()
        except Exception:  # noqa: BLE001
            log.exception("error cerrando websockets")
        self.writer.close()                 # lo importante: los datos en disco
        for closer in (self.gamma.close, self.rest.close):
            try:
                await closer()
            except Exception:  # noqa: BLE001
                pass
        if self.data_api is not None:
            try:
                await self.data_api.close()
            except Exception:  # noqa: BLE001
                pass
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
        recv = now_ms()
        ts = int(msg.get("timestamp") or recv)
        if msg.get("timestamp"):
            self.latencias.append(recv - ts)
        if et == "book":
            await self._apply_snapshot(msg.get("asset_id", ""), msg.get("bids") or [], msg.get("asks") or [],
                                       ts, msg.get("hash", ""), source="ws", recv_ms=recv)
        elif et == "price_change":
            for ch in msg.get("price_changes") or []:
                tid = ch.get("asset_id", "")
                book = self.books.get(tid)
                if book is None:
                    continue
                price, size = float(ch["price"]), float(ch["size"])
                delta = book.apply_delta(ch.get("side", ""), price, size, ts, ch.get("hash", ""))
                self.stats["delta"] += 1
                if self.persist:
                    self.writer.append("book_deltas", {
                        "ts_ms": ts, "token_id": tid, "condition_id": book.condition_id, "side": ch.get("side", ""),
                        "price": price, "size": size, "best_bid": _fnum(ch.get("best_bid")),
                        "best_ask": _fnum(ch.get("best_ask")), "hash": ch.get("hash", ""),
                        "recv_ms": recv, "delta_size": delta,
                    })
                await self._emit(("delta", ts, tid, book, {"side": ch.get("side", ""), "price": price, "size": size,
                                                            "delta": delta}))
        elif et == "last_trade_price":
            tid = msg.get("asset_id", "")
            cid = self.token_to_cid.get(tid, msg.get("market", ""))
            trade = {"ts_ms": ts, "token_id": tid, "condition_id": cid, "price": float(msg.get("price") or 0),
                     "size": float(msg.get("size") or 0), "side": msg.get("side", ""),
                     "fee_rate_bps": _fnum(msg.get("fee_rate_bps")), "tx_hash": msg.get("transaction_hash", ""),
                     "recv_ms": recv}
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

    async def _apply_snapshot(self, tid: str, bids: list, asks: list, ts: int, hash_: str, source: str,
                              recv_ms: int | None = None) -> None:
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
                "hash": hash_, "source": source, "recv_ms": recv_ms or now_ms(),
            })
        await self._emit(("book", ts, tid, book))

    # ------------------------------------------------------------------ cripto: precio y ventanas
    async def _on_price(self, row: dict[str, Any]) -> None:
        sym, ts = row["symbol"], int(row["ts_ms"])
        self.prices[sym].append((ts, float(row["price"])))
        cada = int(self.cfg.updown.price_sample_seconds * 1000)
        if self.persist and ts - self._price_last_saved.get(sym, 0) >= cada:
            self._price_last_saved[sym] = ts
            self.writer.append("crypto_prices", {"ts_ms": ts, "symbol": sym, "price": float(row["price"])})
        await self._emit(("price", ts, sym, row))

    def price_at(self, symbol: str, ts_ms: int, tolerancia_s: float) -> tuple[float, int] | None:
        """Precio más cercano a ts_ms dentro de la tolerancia. None si no estábamos escuchando."""
        serie = self.prices.get(symbol)
        if not serie:
            return None
        datos = list(serie)
        ts = [t for t, _ in datos]
        i = bisect.bisect_left(ts, ts_ms)
        mejor: tuple[float, int] | None = None
        for j in (i - 1, i):
            if 0 <= j < len(datos):
                t, p = datos[j]
                if mejor is None or abs(t - ts_ms) < abs(mejor[1] - ts_ms):
                    mejor = (p, t)
        if mejor is None or abs(mejor[1] - ts_ms) > tolerancia_s * 1000:
            return None
        return mejor

    def price_from(self, symbol: str, ts_ms: int, tolerancia_s: float) -> tuple[float, int] | None:
        """Primer precio en ts_ms o después, dentro de la tolerancia.

        Para el strike y la liquidación hace falta esto y no el más cercano: las ventanas se
        descubren por adelantado, y tomar el precio anterior a la apertura sesga el modelo.
        """
        serie = self.prices.get(symbol)
        if not serie:
            return None
        datos = list(serie)
        ts = [t for t, _ in datos]
        i = bisect.bisect_left(ts, ts_ms)
        if i >= len(datos):
            return None
        t, p = datos[i]
        return (p, t) if t - ts_ms <= tolerancia_s * 1000 else None

    async def _updown_loop(self) -> None:
        ucfg = self.cfg.updown
        while True:
            try:
                await self._refresh_updown()
            except Exception:  # noqa: BLE001
                log.exception("ciclo up/down falló")
            await asyncio.sleep(ucfg.refresh_seconds)

    async def _refresh_updown(self) -> None:
        ucfg = self.cfg.updown
        ahora = now_ms()
        encontrados = await discover_updown(self.cfg, self.gamma)
        nuevos: list[str] = []
        for mi in encontrados:
            cid = mi.condition_id
            if cid in self._updown_done:
                continue
            if cid not in self.updown:
                self.updown[cid] = mi
                self.markets[cid] = mi
                for t in mi.tokens:
                    self.token_to_cid[t.token_id] = cid
                    if t.token_id not in self.books:
                        self.books[t.token_id] = OrderBook(t.token_id, cid, mi.tick_size)
                        nuevos.append(t.token_id)
                if self.persist:
                    self.writer.append("markets", mi.to_row(ahora, status="updown"))
            if cid not in self.strikes and ahora >= mi.updown_start_ms:
                golpe = self.price_from(mi.updown_symbol, mi.updown_start_ms, ucfg.strike_tolerance_seconds)
                if golpe is not None:
                    self.strikes[cid] = golpe
                    if self.persist:
                        self.writer.append("updown_windows", {
                            "ts_ms": ahora, "condition_id": cid, "slug": mi.slug, "symbol": mi.updown_symbol,
                            "window_s": mi.updown_window_s, "start_ms": mi.updown_start_ms, "end_ms": mi.updown_end_ms,
                            "strike": golpe[0], "strike_ts_ms": golpe[1], "settle_price": None, "up_won": None,
                            "status": "abierta"})
            strike = self.strikes.get(cid)
            if strike is not None:
                await self._emit(("updown", ahora, cid, {"market": mi, "strike": strike[0], "strike_ts_ms": strike[1],
                                                          "symbol": mi.updown_symbol, "start_ms": mi.updown_start_ms,
                                                          "end_ms": mi.updown_end_ms, "window_s": mi.updown_window_s}))
        if nuevos:
            await self.pool.ensure(nuevos)
        await self._liquidar_updown(ahora)

    async def _liquidar_updown(self, ahora: int) -> None:
        """Ventana vencida: el ganador sale del precio de referencia al cierre."""
        ucfg = self.cfg.updown
        for cid, mi in list(self.updown.items()):
            if ahora < mi.updown_end_ms + 3000:
                continue
            self.updown.pop(cid, None)
            self._updown_done.add(cid)
            strike = self.strikes.get(cid)
            cierre = self.price_from(mi.updown_symbol, mi.updown_end_ms, ucfg.strike_tolerance_seconds)
            up_won = None if (strike is None or cierre is None) else cierre[0] > strike[0]
            if self.persist:
                self.writer.append("updown_windows", {
                    "ts_ms": ahora, "condition_id": cid, "slug": mi.slug, "symbol": mi.updown_symbol,
                    "window_s": mi.updown_window_s, "start_ms": mi.updown_start_ms, "end_ms": mi.updown_end_ms,
                    "strike": None if strike is None else strike[0], "strike_ts_ms": None if strike is None else strike[1],
                    "settle_price": None if cierre is None else cierre[0], "up_won": up_won,
                    "status": "resuelta" if up_won is not None else "sin_datos"})
            await self.pool.drop(mi.token_ids)
            for t in mi.token_ids:
                self.books.pop(t, None)
                self.token_to_cid.pop(t, None)
            self.strikes.pop(cid, None)
            self.stats["updown_resueltas"] += 1
            if up_won is not None:
                ganador = next((t.token_id for t in mi.tokens if t.outcome.lower() == ("up" if up_won else "down")), None)
                await self._emit(("updown_settle", ahora, cid, {"up_won": up_won, "winner_token": ganador,
                                                                 "market": mi, "settle_price": cierre[0]}))

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
                         f" flow_huecos={self.flow.paginas_llenas}"
                         f" wallets={len(self.wallets.profiles)} cola={self.wallets.pending}")
            if self.sports is not None:
                extra += f" partidos_vivos={len(self.live_games())}"
            if self.crypto is not None:
                btc = self.crypto.price("btc")
                extra += f" updown={len(self.updown)} strikes={len(self.strikes)}"
                if btc:
                    extra += f" btc={btc[1]:,.0f}"
            lat = self.latencia()
            if lat:
                extra += f" latencia_feed_ms(mediana/p95)={lat['mediana']:.0f}/{lat['p95']:.0f}"
            # el indexador de data-api se congela a ratos; cuando pasa, el dinero inteligente queda
            # ciego y conviene saberlo en vez de creer que no hay ballenas operando
            if self.flow is not None and self.flow.lag_seconds > self.cfg.flow.stale_warn_seconds:
                log.warning("flujo de trades detenido: el último trade de data-api es de hace %d s. "
                            "Las señales de dinero inteligente no pueden dispararse mientras dure.",
                            self.flow.lag_seconds)
            log.info("estado: mercados=%d libros_validos=%d/%d ws=%s eventos=%s filas=%s%s",
                     len(self.markets), valid, len(self.books), self.pool.stats(), dict(self.stats),
                     dict(self.writer.rows_written), extra)

    def latencia(self) -> dict[str, float] | None:
        """Retraso entre el reloj del exchange y el nuestro, sobre los últimos mensajes del CLOB."""
        if not self.latencias:
            return None
        xs = sorted(self.latencias)
        return {"n": len(xs), "mediana": xs[len(xs) // 2], "p95": xs[min(len(xs) - 1, int(len(xs) * 0.95))],
                "max": xs[-1]}


def _fnum(x: Any) -> float | None:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None
