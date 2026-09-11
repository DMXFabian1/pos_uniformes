"""Tipos base del motor de señales."""
from __future__ import annotations

import itertools
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..book import OrderBook
from ..discovery import MarketInfo
from ..fees import taker_fee
from ..models.base import GameState, WinProb
from ..models.crypto import UpDownState

_counter = itertools.count(1)


def strategy_id(kind: str, meta: dict[str, Any], category: str = "") -> str:
    """Identificador de estrategia: separa lo que no debe mezclarse en las métricas.

    `model_deviation` en NBA y en tenis son tesis distintas; una ventana de 5 minutos y una de 15
    también. Los arbitrajes deterministas van juntos porque su riesgo es solo de ejecución.
    """
    liga = str(meta.get("league") or category or "").upper().replace(" ", "_") or "OTRO"
    deporte = str(meta.get("sport") or "").lower()
    if kind == "model_deviation":
        if deporte == "basketball" or liga == "NBA":
            return f"{liga}_DIRECTIONAL" if liga else "NBA_DIRECTIONAL"
        if deporte == "tennis":
            return "TENNIS_DIRECTIONAL"
        return f"{liga}_DIRECTIONAL"
    if kind == "spread_capture":
        cat = (category or "").upper() or "OTRO"
        return f"{cat}_SPREAD_CAPTURE"
    if kind == "smart_money":
        return "SMART_MONEY"
    if kind == "updown_model":
        w = meta.get("window_s")
        return f"CRYPTO_{int(w) // 60}M" if w else "CRYPTO"
    if kind.startswith("complement") or kind.startswith("multi"):
        return "ARBITRAGE"
    return kind.upper()


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
    strategy: str = ""

    def __post_init__(self) -> None:
        if not self.signal_id:
            self.signal_id = f"{self.kind}-{self.ts_ms}-{next(_counter)}"
        if not self.strategy:
            self.strategy = strategy_id(self.kind, self.meta)

    @property
    def predicted_pnl(self) -> float:
        return self.edge_net * self.size


@dataclass
class TokenHistory:
    """Historia corta por token: trades, mids y cambios de nivel recientes.

    `flujo` guarda el cambio firmado de cada nivel del libro: positivo cuando alguien pone
    órdenes, negativo cuando las quita o se las llenan. Es lo que permite distinguir un libro
    que se está construyendo de uno que se está vaciando.
    """
    trades: deque = field(default_factory=lambda: deque(maxlen=500))   # (ts_ms, price, size, side)
    mids: deque = field(default_factory=lambda: deque(maxlen=2000))    # (ts_ms, mid)
    flujo: deque = field(default_factory=lambda: deque(maxlen=4000))   # (ts_ms, side, delta_size)

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
    rechazos: list[dict[str, Any]] = field(default_factory=list)   # candidatos que NO se operan, con motivo
    reaction: dict[str, Any] | None = None          # Market Reaction Engine: último evento y retraso típico

    def no_trade(self, kind: str, motivo: str, **detalle: Any) -> None:
        """Registra una oportunidad candidata que se descarta. El motor la persiste como decisión."""
        self.rechazos.append({"kind": kind, "motivo": motivo, **detalle})

    def book(self, token_id: str) -> OrderBook | None:
        return self.books.get(token_id) or self.event_books.get(token_id)

    def wallet_profile(self, wallet: str) -> Any | None:
        return self.wallets.get((wallet or "").lower())


def precio_maker(book: OrderBook, p_justo: float, min_edge: float) -> float | None:
    """Precio al que poner una orden de compra sin cruzar el libro.

    La comisión de Polymarket solo la paga quien cruza. Poniendo la orden y esperando, la
    ventaja es entera. A cambio puede no llenarse, que es un coste de oportunidad, no una
    pérdida.

    Se busca el precio más alto que cumpla las tres condiciones:
      1. no cruza (queda por debajo del mejor vendedor),
      2. deja al menos `min_edge` de ventaja frente al valor justo,
      3. no queda por detrás del mejor comprador, o no se llenaría nunca.
    """
    if not book.is_valid:
        return None
    tick = book.tick_size
    tope = min(book.best_ask - tick, p_justo - min_edge)
    limite = math.floor(round(tope / tick, 9)) * tick
    limite = round(limite, 10)
    if limite < book.best_bid - 1e-9 or limite <= 0:
        return None                       # habría que ponerse detrás de la cola: no compensa
    return limite


@dataclass
class Entrada:
    """Cómo se entraría en un token: precio, tamaño, comisión y rol. Incluye la alternativa taker
    aunque se opere maker, para poder calcular después el break-even de la tasa de llenado."""
    precio: float
    size: float
    fee_in: float                 # USD por share
    rol: str                      # maker | taker
    precio_limite: float
    taker_precio: float | None    # precio medio si se cruzara el libro ahora (None si no hay tamaño)
    taker_fee_in: float
    taker_size: float
    queue_ahead: float            # shares delante de nuestra orden en ese nivel (maker)


def planear_entrada(book: OrderBook, m: MarketInfo, p_justo: float, min_edge: float, target_size: float,
                    maker_first: bool) -> Entrada | None:
    """Bloque común de los detectores direccionales. Devuelve None si no hay forma de entrar."""
    w = book.walk_buy(target_size)
    taker_precio = w.avg_price if w.shares >= m.min_order_size else None
    taker_fee_ps = 0.0
    if taker_precio is not None:
        taker_fee_ps = taker_fee(w.shares, taker_precio, m.fee_rate) / w.shares
    if maker_first:
        entry = precio_maker(book, p_justo, min_edge)
        if entry is None:
            return None
        size = max(target_size, m.min_order_size)
        return Entrada(entry, size, 0.0, "maker", entry, taker_precio, taker_fee_ps, w.shares,
                       book.bids.get(entry, 0.0))
    if taker_precio is None:
        return None
    return Entrada(taker_precio, w.shares, taker_fee_ps, "taker", w.worst_price, taker_precio, taker_fee_ps,
                   w.shares, 0.0)


class Detector(Protocol):
    kind: str

    def detect(self, ctx: MarketContext, ts_ms: int) -> list[Signal]: ...


class FlowDetector(Protocol):
    kind: str

    def on_flow(self, ctx: MarketContext, flow: dict[str, Any], ts_ms: int) -> list[Signal]: ...
