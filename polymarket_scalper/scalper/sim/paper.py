"""Paper trading en vivo: recolector + motor sobre los mismos libros, sin dinero real."""
from __future__ import annotations

import asyncio
import logging
import time

from ..collector import Collector
from ..config import Config
from ..storage import ParquetWriter
from .engine import Engine

log = logging.getLogger(__name__)


async def run_paper(cfg: Config, duration_seconds: int | None = None, run_id: str | None = None,
                    persist_market_data: bool = True) -> Engine:
    run_id = run_id or f"paper-{int(time.time())}"
    col = Collector(cfg, persist=persist_market_data)
    writer = ParquetWriter(cfg.data_dir, cfg.collector.flush_seconds, cfg.collector.flush_rows, subdir=f"run={run_id}")
    eng = Engine(cfg, run_id, "paper", writer)
    eng.attach_books(col.books)
    if col.wallets is not None:
        eng.attach_wallets(col.wallets.profiles)
    col.add_listener(eng.on_event)

    async def ticker() -> None:
        while True:
            await asyncio.sleep(1)
            eng.tick(int(time.time() * 1000))
            writer.maybe_flush()

    async def reporter() -> None:
        while True:
            await asyncio.sleep(120)
            log.info("paper: %s", eng.summary())

    tasks = [asyncio.create_task(ticker()), asyncio.create_task(reporter())]
    if duration_seconds:
        async def stopper() -> None:
            await asyncio.sleep(duration_seconds)
            col.stop()
        tasks.append(asyncio.create_task(stopper()))
    try:
        await col.run()
    finally:
        for t in tasks:
            t.cancel()
        eng.close_all(int(time.time() * 1000), "end")
        writer.close()
        log.info("paper terminado: %s", eng.summary())
    return eng
