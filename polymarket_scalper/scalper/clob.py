"""Clientes del CLOB de Polymarket: REST (libros, mercados) y websocket (canal market)."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable

import httpx
import websockets

log = logging.getLogger(__name__)

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class ClobRest:
    def __init__(self, base_url: str, timeout: float = 15.0):
        self._c = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers={"User-Agent": "polymarket-scalper/0.1"})
        self._sem = asyncio.Semaphore(4)

    async def close(self) -> None:
        await self._c.aclose()

    async def get_book(self, token_id: str) -> dict[str, Any] | None:
        async with self._sem:
            try:
                r = await self._c.get("/book", params={"token_id": token_id})
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError as e:
                log.warning("REST /book %s… falló: %s", token_id[:12], e)
                return None

    async def get_market(self, condition_id: str) -> dict[str, Any] | None:
        async with self._sem:
            try:
                r = await self._c.get(f"/markets/{condition_id}")
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError as e:
                log.warning("REST /markets/%s… falló: %s", condition_id[:12], e)
                return None


class MarketWebSocket:
    """Una conexión al canal `market`. Reconecta sola y manda PING cada 10 s."""

    def __init__(self, url: str, asset_ids: list[str], handler: MessageHandler, name: str = "ws"):
        self.url = url
        self.assets: set[str] = set(asset_ids)
        self.handler = handler
        self.name = name
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._stop = asyncio.Event()
        self.connected = asyncio.Event()
        self.messages = 0
        self.reconnects = 0
        self.last_msg_ts = 0.0

    def stop(self) -> None:
        self._stop.set()

    async def subscribe(self, asset_ids: list[str]) -> None:
        new = [a for a in asset_ids if a not in self.assets]
        self.assets.update(new)
        if new and self._ws is not None:
            await self._ws.send(json.dumps({"assets_ids": new, "operation": "subscribe"}))

    async def unsubscribe(self, asset_ids: list[str]) -> None:
        old = [a for a in asset_ids if a in self.assets]
        self.assets.difference_update(old)
        if old and self._ws is not None:
            await self._ws.send(json.dumps({"assets_ids": old, "operation": "unsubscribe"}))

    async def run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            if not self.assets:
                await asyncio.sleep(2)
                continue
            try:
                async with websockets.connect(self.url, max_size=2**25, ping_interval=None, open_timeout=20) as ws:
                    self._ws = ws
                    await ws.send(json.dumps({"assets_ids": sorted(self.assets), "type": "market",
                                              "custom_feature_enabled": True}))
                    self.connected.set()
                    backoff = 1.0
                    log.info("%s conectado, %d assets", self.name, len(self.assets))
                    pinger = asyncio.create_task(self._ping_loop(ws))
                    try:
                        await self._consume(ws)
                    finally:
                        pinger.cancel()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - cualquier fallo de red reconecta
                log.warning("%s desconectado: %s (reintento en %.0fs)", self.name, e, backoff)
            self._ws = None
            self.connected.clear()
            if self._stop.is_set():
                break
            self.reconnects += 1
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    async def _ping_loop(self, ws: websockets.WebSocketClientProtocol) -> None:
        while True:
            await asyncio.sleep(10)
            try:
                await ws.send("PING")
            except Exception:  # noqa: BLE001
                return

    async def _consume(self, ws: websockets.WebSocketClientProtocol) -> None:
        while not self._stop.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=60)
            except asyncio.TimeoutError:
                raise ConnectionError("sin mensajes en 60s")
            self.last_msg_ts = time.time()
            if raw == "PONG" or not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            items = data if isinstance(data, list) else [data]
            for msg in items:
                if isinstance(msg, dict) and msg.get("event_type"):
                    self.messages += 1
                    await self.handler(msg)


class WebSocketPool:
    """Reparte tokens entre varias conexiones para no sobrecargar una sola."""

    def __init__(self, url: str, handler: MessageHandler, per_conn: int = 150):
        self.url = url
        self.handler = handler
        self.per_conn = per_conn
        self.conns: list[MarketWebSocket] = []
        self._tasks: list[asyncio.Task] = []
        self._where: dict[str, MarketWebSocket] = {}

    @property
    def assets(self) -> set[str]:
        return set(self._where)

    async def ensure(self, asset_ids: list[str]) -> None:
        pending = [a for a in asset_ids if a not in self._where]
        for a in pending:
            target = next((c for c in self.conns if len(c.assets) < self.per_conn), None)
            if target is None:
                target = MarketWebSocket(self.url, [], self.handler, name=f"ws{len(self.conns)}")
                self.conns.append(target)
                self._tasks.append(asyncio.create_task(target.run()))
            await target.subscribe([a])
            self._where[a] = target

    async def drop(self, asset_ids: list[str]) -> None:
        for a in asset_ids:
            c = self._where.pop(a, None)
            if c is not None:
                await c.unsubscribe([a])

    async def stop(self) -> None:
        for c in self.conns:
            c.stop()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def stats(self) -> dict[str, Any]:
        return {"connections": len(self.conns), "assets": len(self._where),
                "messages": sum(c.messages for c in self.conns), "reconnects": sum(c.reconnects for c in self.conns)}
