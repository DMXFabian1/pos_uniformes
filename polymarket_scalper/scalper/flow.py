"""Flujo de trades con identidad (data-api.polymarket.com/trades).

A diferencia del canal `market` del CLOB, aquí cada trade trae la wallet y el nombre de quien lo
hizo. Se sondea periódicamente (ordenado por tiempo desc, hasta 2000 por página), se deduplica
y se guarda lo que interesa: todo lo de los mercados seguidos y cualquier trade grande global.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable

import httpx

log = logging.getLogger(__name__)

FlowHandler = Callable[[dict[str, Any]], Awaitable[None]]


def trade_key(t: dict[str, Any]) -> tuple:
    return (t.get("transactionHash"), t.get("proxyWallet"), t.get("asset"), t.get("side"),
            str(t.get("size")), str(t.get("price")), t.get("timestamp"))


def flow_row(t: dict[str, Any]) -> dict[str, Any]:
    size = float(t.get("size") or 0)
    price = float(t.get("price") or 0)
    return {
        "ts_ms": int(t.get("timestamp") or 0) * 1000,
        "wallet": str(t.get("proxyWallet") or "").lower(),
        "name": str(t.get("name") or ""),
        "pseudonym": str(t.get("pseudonym") or ""),
        "side": str(t.get("side") or ""),
        "size": size,
        "price": price,
        "usd": round(size * price, 4),
        "token_id": str(t.get("asset") or ""),
        "condition_id": str(t.get("conditionId") or ""),
        "outcome": str(t.get("outcome") or ""),
        "outcome_index": int(t.get("outcomeIndex") or 0),
        "title": str(t.get("title") or ""),
        "slug": str(t.get("slug") or ""),
        "event_slug": str(t.get("eventSlug") or ""),
        "tx_hash": str(t.get("transactionHash") or ""),
    }


class DataApi:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self._c = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers={"User-Agent": "polymarket-scalper/0.1"})
        self._sem = asyncio.Semaphore(3)

    async def close(self) -> None:
        await self._c.aclose()

    async def _get(self, path: str, **params: Any) -> list[dict[str, Any]]:
        async with self._sem:
            for attempt in range(3):
                try:
                    r = await self._c.get(path, params=params)
                    if r.status_code in (403, 429):        # límite de tasa: esperar y reintentar
                        await asyncio.sleep(3 * (attempt + 1))
                        continue
                    r.raise_for_status()
                    data = r.json()
                    return data if isinstance(data, list) else []
                except httpx.HTTPError as e:
                    log.warning("data-api %s falló: %s", path, e)
                    await asyncio.sleep(1 + attempt)
        return []

    async def trades(self, limit: int = 1000, offset: int = 0, **extra: Any) -> list[dict[str, Any]]:
        return await self._get("/trades", limit=limit, offset=offset, **extra)

    async def trades_by_user(self, wallet: str, limit: int = 1000, offset: int = 0) -> list[dict[str, Any]]:
        return await self._get("/trades", user=wallet, limit=limit, offset=offset)

    async def closed_positions(self, wallet: str, max_pages: int = 10, page_delay: float = 0.3) -> list[dict[str, Any]]:
        """Últimas `max_pages*50` posiciones cerradas, de la más reciente a la más antigua.

        El orden por defecto del endpoint es por ganancia realizada descendente, lo que sesga
        cualquier muestra truncada hacia las mejores operaciones. Por eso se pide por fecha.
        """
        out: list[dict[str, Any]] = []
        for page in range(max_pages):
            batch = await self._get("/closed-positions", user=wallet, limit=50, offset=page * 50,
                                    sortBy="TIMESTAMP", sortDirection="DESC")
            out.extend(batch)
            if len(batch) < 50:
                break
            await asyncio.sleep(page_delay)
        return out

    async def positions(self, wallet: str, limit: int = 500) -> list[dict[str, Any]]:
        return await self._get("/positions", user=wallet, limit=limit, sizeThreshold=1)


class FlowPoller:
    def __init__(self, api: DataApi, handler: FlowHandler, poll_seconds: float = 10, page_size: int = 1000,
                 seen_capacity: int = 50000):
        self.api = api
        self.handler = handler
        self.poll_seconds = poll_seconds
        self.page_size = page_size
        self.paginas_llenas = 0      # veces que la página vino entera nueva: señal de datos perdidos
        self._seen: OrderedDict[tuple, None] = OrderedDict()
        self._cap = seen_capacity
        self._stop = asyncio.Event()
        self.polls = 0
        self.new_trades = 0
        self.last_ts = 0
        self._prev_nonempty = False

    def stop(self) -> None:
        self._stop.set()

    def _remember(self, k: tuple) -> bool:
        """True si es nuevo."""
        if k in self._seen:
            return False
        self._seen[k] = None
        if len(self._seen) > self._cap:
            self._seen.popitem(last=False)
        return True

    async def poll_once(self) -> int:
        batch = await self.api.trades(limit=self.page_size)
        self.polls += 1
        fresh = [t for t in batch if self._remember(trade_key(t))]
        # llegan desc; los entregamos en orden cronológico
        for t in reversed(fresh):
            self.last_ts = max(self.last_ts, int(t.get("timestamp") or 0))
            await self.handler(t)
        self.new_trades += len(fresh)
        if batch and len(fresh) == len(batch) and self._prev_nonempty:
            # todo lo que vino era nuevo: entre esta consulta y la anterior hubo más trades de los
            # que caben en una página, así que se perdieron. Se cuenta para poder dimensionarlo.
            self.paginas_llenas += 1
            log.warning("flow: la página completa era nueva (%d); hay huecos (%d veces). Subir page_size "
                        "o bajar poll_seconds", len(batch), self.paginas_llenas)
        self._prev_nonempty = bool(batch)
        return len(fresh)

    @property
    def lag_seconds(self) -> int:
        """Retraso del indexador de data-api frente al reloj (suele ser de 2 a 3 minutos)."""
        return int(time.time()) - self.last_ts if self.last_ts else -1

    async def run(self) -> None:
        while not self._stop.is_set():
            t0 = time.time()
            try:
                await self.poll_once()
            except Exception:  # noqa: BLE001
                log.exception("flow poll falló")
            await asyncio.sleep(max(self.poll_seconds - (time.time() - t0), 1))
