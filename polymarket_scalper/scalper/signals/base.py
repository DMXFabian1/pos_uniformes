"""Tipos base del motor de señales."""
from __future__ import annotations

import itertools
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..book import OrderBook
from ..discovery import MarketInfo
from ..models.base import GameState, WinProb
from ..models.crypto import UpDownState

_counter = itertools.count(1)


@dataclass
class Leg:
    token_id: str
    side: str            # BUY | SELL
    price: float         # precio límite / precio esperado
    size: float          # shares
    role: str = "taker"  # taker | maker
    outcome: str = ""


@dataclass
class Signal:
    ts_ms: int
    kind: str
    condition_id: str
    event_id: str
    legs: list[Leg]
    size: float
    edge_gross: float    # USD por share antes de fees
    fee_est: float       # USD por share estimado en fees
    edge_net: float      # USD por share después de fees
    confidence: float    # 0..1 heurístico
    horizon: str         # merge | mint | resolution | mean_revert
    meta: dict[str, Any] = field(default_factory=dict)
    signal_id: str = ""

    def __post_init__(self) -> None:
        if not self.signal_id:
            self.signal_id = f"{self.kind}-{self.ts_ms}-{next(_counter)}"

    @property
    def predicted_pnl(self) -> float:
        return self.edge_net * self.size


@dataclass
class TokenHistory:
    """Historia corta por token: trades y mids recientes (para volatilidad/actividad)."""
    trades: deque = field(default_factory=lambda: deque(maxlen=500))   # (ts_ms, price, size, side)
    mids: deque = field(default_factory=lambda: deque(maxlen=2000))    # (ts_ms, mid)

    def trades_in(self, ts_ms: int, window_ms: int) -> list[tuple]:
        lo = ts_ms - window_ms
        return [t for t in self.trades if t[0] >= lo]

    def mid_vol(self, ts_ms: int, window_ms: int) -> float:
        """Desviación estándar de los cambios de mid en la ventana (en USD)."""
        lo = ts_ms - window_ms
        xs = [m for t, m in self.mids if t >= lo]
        if len(xs) < 3:
            return 0.0
        diffs = [b - a for a, b in zip(xs, xs[1:])]
        mean = sum(diffs) / len(diffs)
        var = sum((d - mean) ** 2 for d in diffs) / max(len(diffs) - 1, 1)
        return var ** 0.5


@dataclass
class MarketContext:
    """Todo lo que un detector necesita ver para un mercado."""
    market: MarketInfo
    books: dict[str, OrderBook]                      # token_id -> libro (de este mercado)
    history: dict[str, TokenHistory]                 # token_id -> historia
    event_markets: list[MarketInfo] = field(default_factory=list)   # hermanos del mismo evento
    event_books: dict[str, OrderBook] = field(default_factory=dict)  # libros de todos los tokens del evento
    game: GameState | None = None                    # partido enlazado (si hay)
    model_prob: WinProb | None = None                # salida del modelo para ese partido
    pregame: WinProb | None = None                   # probabilidad previa al partido (del mercado)
    outcome_side: dict[str, str] = field(default_factory=dict)      # token_id -> home | away | draw
    wallets: dict[str, Any] = field(default_factory=dict)           # wallet -> WalletProfile
    updown: UpDownState | None = None               # ventana "Up or Down" activa
    updown_prob: float | None = None                # P(Up) del modelo de difusión
    prev_window: dict[str, Any] | None = None       # cómo terminó la ventana anterior del símbolo

    def book(self, token_id: str) -> OrderBook | None:
        return self.books.get(token_id) or self.event_books.get(token_id)

    def wallet_profile(self, wallet: str) -> Any | None:
        return self.wallets.get((wallet or "").lower())


class Detector(Protocol):
    kind: str

    def detect(self, ctx: MarketContext, ts_ms: int) -> list[Signal]: ...


class FlowDetector(Protocol):
    kind: str

    def on_flow(self, ctx: MarketContext, flow: dict[str, Any], ts_ms: int) -> list[Signal]: ...
