"""Libro de órdenes en memoria para un token (SÍ o NO de un mercado)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WalkResult:
    shares: float          # shares realmente disponibles
    notional: float        # USD totales
    avg_price: float       # precio promedio (0 si no hay nada)
    worst_price: float     # peor nivel tocado


@dataclass
class OrderBook:
    token_id: str
    condition_id: str = ""
    tick_size: float = 0.01
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)
    last_ts: int = 0
    hash: str = ""
    snapshot_ts: int = 0

    # ---------- actualización ----------
    def apply_snapshot(self, bids: list[dict], asks: list[dict], ts: int, hash_: str = "") -> None:
        self.bids = {float(l["price"]): float(l["size"]) for l in bids if float(l["size"]) > 0}
        self.asks = {float(l["price"]): float(l["size"]) for l in asks if float(l["size"]) > 0}
        self.last_ts = ts
        self.snapshot_ts = ts
        self.hash = hash_

    def apply_delta(self, side: str, price: float, size: float, ts: int, hash_: str = "") -> None:
        """`size` es el tamaño absoluto que queda en el nivel (0 = nivel eliminado)."""
        levels = self.bids if side.upper() == "BUY" else self.asks
        if size <= 0:
            levels.pop(price, None)
        else:
            levels[price] = size
        self.last_ts = ts
        if hash_:
            self.hash = hash_

    # ---------- lectura ----------
    @property
    def best_bid(self) -> float | None:
        return max(self.bids) if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return min(self.asks) if self.asks else None

    @property
    def best_bid_size(self) -> float:
        bb = self.best_bid
        return self.bids[bb] if bb is not None else 0.0

    @property
    def best_ask_size(self) -> float:
        ba = self.best_ask
        return self.asks[ba] if ba is not None else 0.0

    @property
    def mid(self) -> float | None:
        bb, ba = self.best_bid, self.best_ask
        if bb is None or ba is None:
            return None
        return (bb + ba) / 2.0

    @property
    def spread(self) -> float | None:
        bb, ba = self.best_bid, self.best_ask
        if bb is None or ba is None:
            return None
        return ba - bb

    @property
    def spread_ticks(self) -> float | None:
        s = self.spread
        return None if s is None else round(s / self.tick_size, 6)

    @property
    def is_valid(self) -> bool:
        bb, ba = self.best_bid, self.best_ask
        return bb is not None and ba is not None and bb < ba

    def imbalance(self) -> float:
        """(bid_size - ask_size) / (bid_size + ask_size) en el mejor nivel. Rango [-1, 1]."""
        b, a = self.best_bid_size, self.best_ask_size
        tot = a + b
        return 0.0 if tot == 0 else (b - a) / tot

    def depth_within(self, side: str, ticks: int) -> float:
        """Shares acumulados dentro de `ticks` del mejor precio de ese lado."""
        if side.upper() == "BUY":
            bb = self.best_bid
            if bb is None:
                return 0.0
            lim = bb - ticks * self.tick_size - 1e-9
            return sum(s for p, s in self.bids.items() if p >= lim)
        ba = self.best_ask
        if ba is None:
            return 0.0
        lim = ba + ticks * self.tick_size + 1e-9
        return sum(s for p, s in self.asks.items() if p <= lim)

    def walk_buy(self, shares: float) -> WalkResult:
        """Costo de comprar `shares` cruzando los asks (de menor a mayor precio)."""
        remaining = shares
        notional = 0.0
        worst = 0.0
        for p in sorted(self.asks):
            if remaining <= 1e-12:
                break
            take = min(remaining, self.asks[p])
            notional += take * p
            remaining -= take
            worst = p
        got = shares - remaining
        return WalkResult(got, notional, notional / got if got > 0 else 0.0, worst)

    def walk_sell(self, shares: float) -> WalkResult:
        """Ingreso por vender `shares` cruzando los bids (de mayor a menor precio)."""
        remaining = shares
        notional = 0.0
        worst = 0.0
        for p in sorted(self.bids, reverse=True):
            if remaining <= 1e-12:
                break
            take = min(remaining, self.bids[p])
            notional += take * p
            remaining -= take
            worst = p
        got = shares - remaining
        return WalkResult(got, notional, notional / got if got > 0 else 0.0, worst)

    def levels(self, side: str, n: int = 10) -> list[tuple[float, float]]:
        if side.upper() == "BUY":
            return sorted(self.bids.items(), reverse=True)[:n]
        return sorted(self.asks.items())[:n]

    def copy(self) -> "OrderBook":
        return OrderBook(self.token_id, self.condition_id, self.tick_size, dict(self.bids), dict(self.asks),
                         self.last_ts, self.hash, self.snapshot_ts)
