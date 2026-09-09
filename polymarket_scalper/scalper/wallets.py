"""Perfilado de wallets: quién es ballena y quién es dinero inteligente.

Tamaño no es señal. Una wallet que pone 7.000 USD a 0.999 está cosechando 0,1 %, no sabe algo.
Lo que importa es el historial: con `closed-positions` de data-api se obtiene la ganancia
realizada por mercado, y de ahí tasa de acierto, ROI y un score con encogimiento bayesiano
(pocas operaciones -> score cerca de neutral).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, asdict
from typing import Any

from .flow import DataApi

log = logging.getLogger(__name__)


@dataclass
class WalletProfile:
    ts_ms: int
    wallet: str
    name: str
    n_closed: int
    wins: int
    losses: int
    total_bought: float
    realized_pnl: float
    roi: float
    win_rate: float
    win_rate_adj: float
    roi_adj: float
    score: float
    biggest_win: float
    biggest_loss: float
    n_open: int
    open_value: float
    open_pnl: float
    first_ts: int
    last_ts: int
    truncated: bool = False      # el historial es más largo que la muestra (últimas max_pages*50)

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def score_wallet(closed: list[dict[str, Any]], prior_n: int = 4, roi_shrink_n: int = 10,
                 min_return: float = 0.02) -> dict[str, float]:
    """Métricas de historial con encogimiento hacia lo neutral cuando hay pocas operaciones.

    Una posición cuenta como ganada o perdida solo si su retorno supera `min_return` (2 %):
    cosechar 0,1 % en mercados ya decididos no es evidencia de saber algo.
    """
    n = len(closed)
    pnls = [float(p.get("realizedPnl") or 0) for p in closed]
    bought = [float(p.get("totalBought") or 0) for p in closed]
    rets = [pnl / b if b > 0 else 0.0 for pnl, b in zip(pnls, bought)]
    wins = sum(1 for r in rets if r >= min_return)
    losses = sum(1 for r in rets if r <= -min_return)
    n_eff = wins + losses
    total_bought = sum(bought)
    realized = sum(pnls)
    roi = realized / total_bought if total_bought > 0 else 0.0
    win_rate = wins / n_eff if n_eff else 0.0
    win_rate_adj = (wins + prior_n / 2) / (n_eff + prior_n)        # prior 50 %
    roi_adj = roi * n_eff / (n_eff + roi_shrink_n)                 # ROI encogido a 0
    raw = (win_rate_adj - 0.5) * 2 + 3 * max(min(roi_adj, 1.0), -1.0)
    score = max(0.0, min(1.0, 0.5 + raw / 4))                      # 0.5 = neutral
    return {
        "n_closed": n, "wins": wins, "losses": losses, "total_bought": round(total_bought, 2),
        "realized_pnl": round(realized, 2), "roi": round(roi, 4), "win_rate": round(win_rate, 4),
        "win_rate_adj": round(win_rate_adj, 4), "roi_adj": round(roi_adj, 4), "score": round(score, 4),
        "biggest_win": round(max(pnls, default=0.0), 2), "biggest_loss": round(min(0.0, min(pnls, default=0.0)), 2),
        "first_ts": min((int(p.get("timestamp") or 0) for p in closed), default=0),
        "last_ts": max((int(p.get("timestamp") or 0) for p in closed), default=0),
    }


def closed_row(wallet: str, p: dict[str, Any], ts_ms: int) -> dict[str, Any]:
    return {
        "ts_ms": ts_ms, "wallet": wallet, "condition_id": str(p.get("conditionId") or ""),
        "token_id": str(p.get("asset") or ""), "outcome": str(p.get("outcome") or ""),
        "title": str(p.get("title") or ""), "event_slug": str(p.get("eventSlug") or ""),
        "avg_price": float(p.get("avgPrice") or 0), "total_bought": float(p.get("totalBought") or 0),
        "realized_pnl": float(p.get("realizedPnl") or 0), "cur_price": float(p.get("curPrice") or 0),
        "end_date": str(p.get("endDate") or ""), "closed_ts": int(p.get("timestamp") or 0),
    }


class WalletTracker:
    """Cola de wallets a perfilar + refresco periódico. Escribe `wallet_profiles` y `wallet_closed`."""

    def __init__(self, api: DataApi, writer: Any, max_pages: int = 10, refresh_hours: float = 12,
                 per_wallet_delay: float = 1.5):
        self.api = api
        self.writer = writer
        self.max_pages = max_pages
        self.refresh_ms = int(refresh_hours * 3600 * 1000)
        self.delay = per_wallet_delay
        self.profiles: dict[str, WalletProfile] = {}
        self.names: dict[str, str] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._queued: set[str] = set()
        self._written_closed: set[tuple[str, str]] = set()
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    def enqueue(self, wallet: str, name: str = "") -> None:
        wallet = wallet.lower()
        if name:
            self.names[wallet] = name
        if wallet in self._queued:
            return
        prof = self.profiles.get(wallet)
        if prof is not None and int(time.time() * 1000) - prof.ts_ms < self.refresh_ms:
            return
        self._queued.add(wallet)
        self._queue.put_nowait(wallet)

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    async def profile(self, wallet: str) -> WalletProfile:
        wallet = wallet.lower()
        closed, opened = await asyncio.gather(self.api.closed_positions(wallet, self.max_pages),
                                              self.api.positions(wallet))
        ts = int(time.time() * 1000)
        m = score_wallet(closed)
        prof = WalletProfile(
            ts_ms=ts, wallet=wallet, name=self.names.get(wallet, ""),
            n_open=len(opened),
            open_value=round(sum(float(p.get("currentValue") or 0) for p in opened), 2),
            open_pnl=round(sum(float(p.get("cashPnl") or 0) for p in opened), 2),
            truncated=len(closed) >= self.max_pages * 50,
            **m,
        )
        self.profiles[wallet] = prof
        if self.writer is not None:
            self.writer.append("wallet_profiles", prof.to_row())
            for p in closed:
                k = (wallet, str(p.get("asset") or ""))
                if k in self._written_closed:
                    continue
                self._written_closed.add(k)
                self.writer.append("wallet_closed", closed_row(wallet, p, ts))
        return prof

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                wallet = await asyncio.wait_for(self._queue.get(), timeout=30)
            except asyncio.TimeoutError:
                self._refresh_stale()
                continue
            self._queued.discard(wallet)
            try:
                prof = await self.profile(wallet)
                log.info("wallet %s… %s: n=%d%s win=%.0f%% roi=%+.1f%% pnl=%+.0f score=%.2f", wallet[:10],
                         prof.name or prof.wallet[:8], prof.n_closed, "+" if prof.truncated else "",
                         prof.win_rate * 100, prof.roi * 100, prof.realized_pnl, prof.score)
            except Exception:  # noqa: BLE001
                log.exception("perfil de %s falló", wallet)
            await asyncio.sleep(self.delay)

    def _refresh_stale(self) -> None:
        now = int(time.time() * 1000)
        for w, p in list(self.profiles.items()):
            if now - p.ts_ms >= self.refresh_ms:
                self.enqueue(w)

    def is_smart(self, wallet: str, min_score: float = 0.65, min_closed: int = 20) -> bool:
        p = self.profiles.get(wallet.lower())
        return p is not None and p.n_closed >= min_closed and p.score >= min_score
