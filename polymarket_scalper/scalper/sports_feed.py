"""Feed en vivo de partidos de Polymarket (wss://sports-api.polymarket.com/ws).

Sin suscripción: el servidor manda cada actualización de cada partido (marcador, período,
estado). El `gameId` coincide con `event.gameId` de Gamma, que es como se enlaza con mercados.
Formatos vistos: esports `score="7-6|1-1|Bo3"`, tenis con `eventState` anidado. Se guarda
normalizado y además el JSON crudo para no perder nada de deportes aún no vistos.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable

import websockets

from .storage import dumps

log = logging.getLogger(__name__)

GameHandler = Callable[[dict[str, Any]], Awaitable[None]]


def normalize_game(msg: dict[str, Any], ts_ms: int) -> dict[str, Any]:
    """Aplana un mensaje del feed a la fila de la tabla `games`."""
    st = msg.get("eventState") if isinstance(msg.get("eventState"), dict) else {}
    g = lambda k, d=None: st.get(k, msg.get(k, d))  # noqa: E731
    return {
        "ts_ms": ts_ms,
        "game_id": str(msg.get("gameId") or ""),
        "league": str(msg.get("leagueAbbreviation") or "").lower(),
        "sport": str(st.get("type") or msg.get("sport") or ""),
        "home": str(msg.get("homeTeam") or ""),
        "away": str(msg.get("awayTeam") or ""),
        "status": str(msg.get("status") or "").lower(),
        "live": bool(g("live", False)),
        "ended": bool(g("ended", False)),
        "score": str(g("score") or ""),
        "period": str(g("period") or ""),
        "elapsed": str(g("elapsed") or ""),
        "raw": dumps(msg),
    }


def state_key(row: dict[str, Any]) -> tuple:
    """Lo que define 'un cambio': si no cambia nada de esto, el mensaje es repetido."""
    return (row["status"], row["live"], row["ended"], row["score"], row["period"], row["elapsed"])


class SportsFeed:
    def __init__(self, url: str, handler: GameHandler):
        self.url = url
        self.handler = handler
        self._stop = asyncio.Event()
        self.messages = 0
        self.reconnects = 0
        self.last_msg_ts = 0.0

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                # el servidor manda ping frames cada 5 s; websockets responde pong solo
                async with websockets.connect(self.url, max_size=2**24, ping_interval=None, open_timeout=20) as ws:
                    log.info("sports feed conectado")
                    backoff = 1.0
                    while not self._stop.is_set():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=120)
                        except asyncio.TimeoutError:
                            raise ConnectionError("sports feed sin mensajes en 120s")
                        self.last_msg_ts = time.time()
                        if isinstance(raw, (bytes, bytearray)):
                            continue
                        if raw in ("ping", "PING"):
                            await ws.send("pong")
                            continue
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        for msg in (data if isinstance(data, list) else [data]):
                            if isinstance(msg, dict) and msg.get("gameId") is not None:
                                self.messages += 1
                                await self.handler(msg)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("sports feed desconectado: %s (reintento en %.0fs)", e, backoff)
            if self._stop.is_set():
                break
            self.reconnects += 1
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
