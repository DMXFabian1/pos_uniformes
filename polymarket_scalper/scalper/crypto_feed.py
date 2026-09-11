"""Precio de referencia de cripto en vivo (wss://ws-live-data.polymarket.com).

Es el mismo dato contra el que se resuelven los mercados "Up or Down": sin él no hay modelo,
solo adivinanza. Llegan ~6 actualizaciones por segundo para todos los símbolos; se guarda una
muestra por símbolo cada `sample_seconds` y el último valor queda siempre en memoria.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable

import websockets

log = logging.getLogger(__name__)

PriceHandler = Callable[[dict[str, Any]], Awaitable[None]]


def normalize_symbol(s: str) -> str:
    """'btcusdt' -> 'btc'."""
    s = (s or "").lower()
    for suf in ("usdt", "usdc", "usd"):
        if s.endswith(suf):
            return s[: -len(suf)]
    return s


class CryptoFeed:
    def __init__(self, url: str, handler: PriceHandler, symbols: set[str] | None = None):
        self.url = url
        self.handler = handler
        self.symbols = symbols          # None = todos
        self.last: dict[str, tuple[int, float]] = {}   # símbolo -> (ts_ms, precio)
        self._stop = asyncio.Event()
        self.messages = 0
        self.reconnects = 0

    def stop(self) -> None:
        self._stop.set()

    def price(self, symbol: str) -> tuple[int, float] | None:
        return self.last.get(symbol)

    async def run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(self.url, max_size=2**22, ping_interval=None, open_timeout=20) as ws:
                    await ws.send(json.dumps({"action": "subscribe",
                                              "subscriptions": [{"topic": "crypto_prices", "type": "update"}]}))
                    log.info("feed de precios cripto conectado")
                    backoff = 1.0
                    pinger = asyncio.create_task(self._ping(ws))
                    try:
                        await self._consume(ws)
                    finally:
                        pinger.cancel()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("feed de precios desconectado: %s (reintento en %.0fs)", e, backoff)
            if self._stop.is_set():
                break
            self.reconnects += 1
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    async def _ping(self, ws: Any) -> None:
        while True:
            await asyncio.sleep(5)
            try:
                await ws.send("PING")
            except Exception:  # noqa: BLE001
                return

    async def _consume(self, ws: Any) -> None:
        while not self._stop.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=60)
            except asyncio.TimeoutError:
                raise ConnectionError("feed de precios sin mensajes en 60s")
            if not raw or raw in ("PONG", "pong"):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for m in (msg if isinstance(msg, list) else [msg]):
                if not isinstance(m, dict) or m.get("topic") != "crypto_prices":
                    continue
                p = m.get("payload") or {}
                sym = normalize_symbol(str(p.get("symbol") or ""))
                if not sym or (self.symbols and sym not in self.symbols):
                    continue
                try:
                    price = float(p.get("full_accuracy_value") or p.get("value"))
                except (TypeError, ValueError):
                    continue
                ts = int(p.get("timestamp") or m.get("timestamp") or time.time() * 1000)
                self.messages += 1
                self.last[sym] = (ts, price)
                await self.handler({"ts_ms": ts, "symbol": sym, "price": price})
