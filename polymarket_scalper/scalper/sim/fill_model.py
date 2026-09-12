"""Modelo de ejecución simulada: fills taker contra el libro y fills maker por cola.

Regla central: **ninguna orden maker se llena por azar**. Se llena cuando el volumen que cruza
su precio consume lo que había delante en la cola y llega hasta ella. Como no sabemos con
exactitud dónde quedamos en la cola, cada orden lleva tres escenarios y los tres se registran:

- CONSERVADOR: todo lo que había en el nivel al poner la orden está delante y nadie lo cancela.
- BASE: lo que había delante se reduce con los trades y también con las cancelaciones que se
  observan en el nivel (se asume que quien cancela estaba delante). Es el que opera el ledger.
- OPTIMISTA: la orden está al frente de la cola: cualquier volumen que cruza es nuestro.

Un trade impreso **por debajo** de nuestro precio de compra (o por encima del de venta) significa
que el nivel entero fue barrido: en los tres escenarios nos llenaron. Lo mismo si el libro llega
**atravesado**, con el mejor vendedor por debajo de nuestra compra. Esos fills son los que más
selección adversa sufren, y se marcan.

**Lo que no es un barrido.** Que el libro llegue *empatado* —el mejor vendedor exactamente a
nuestro precio de compra— no es que nos hayan pasado por encima: es una contrapartida que viene a
nuestro precio, que es el caso bueno del maker. Antes los dos casos se metían en el mismo saco y,
además, el empate llenaba la orden entera al instante saltándose la cola. De 349 llenados de
`TENNIS_SPREAD_CAPTURE` marcados como barrido, 301 no tenían ni un solo trade cruzando nuestro
precio: eran empates. La conclusión que salía de ahí —"casi nunca nos llena una contrapartida que
viene a nuestro precio"— la producía este archivo, no el mercado.

Cada orden guarda ahora la causa de su llenado (`causa`), para que la diferencia se pueda medir en
vez de suponerse.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..book import OrderBook
from ..fees import taker_fee
from ..signals.base import Leg

ESCENARIOS = ("conservador", "base", "optimista")


@dataclass
class Fill:
    token_id: str
    side: str
    shares: float
    avg_price: float
    notional: float
    fee: float
    ts_ms: int
    role: str


@dataclass
class MakerOrder:
    token_id: str
    side: str
    price: float
    size: float
    queue_ahead: float               # cola delante en el escenario BASE (baja con trades y cancelaciones)
    ts_placed: int
    filled: float = 0.0              # llenado BASE: lo que usa el motor
    fills: list[Fill] = field(default_factory=list)
    queue_inicial: float = 0.0       # lo que había en el nivel al poner la orden
    vol_cruzado: float = 0.0         # volumen que cruzó nuestro precio desde que se puso
    nivel_visto: float = 0.0         # último tamaño observado del nivel (para detectar cancelaciones)
    vol_nivel_desde_libro: float = 0.0   # trades en el nivel desde la última observación del libro
    cancelado_delante: float = 0.0   # cancelaciones observadas en el nivel (BASE las descuenta)
    barrido: bool = False            # nos pasaron por encima: el precio atravesó nuestro nivel
    causa: str = ""                  # "trade" (cola), "barrido" (nos atravesaron) o "empate" (vienen a nuestro precio)
    lock_aplicado: float = 0.0       # volumen del empate ya consumido, para no contarlo dos veces
    ts_fill: dict[str, int | None] = field(default_factory=lambda: {e: None for e in ESCENARIOS})

    def __post_init__(self) -> None:
        if self.queue_inicial == 0.0:
            self.queue_inicial = self.queue_ahead
        self.nivel_visto = self.queue_inicial

    @property
    def remaining(self) -> float:
        return max(self.size - self.filled, 0.0)

    @property
    def done(self) -> bool:
        return self.remaining <= 1e-9

    # ---- escenarios: derivados del volumen cruzado, no del azar
    @property
    def filled_conservador(self) -> float:
        if self.barrido:
            return self.size
        return max(0.0, min(self.size, self.vol_cruzado - self.queue_inicial))

    @property
    def filled_optimista(self) -> float:
        if self.barrido:
            return self.size
        return max(0.0, min(self.size, self.vol_cruzado))

    def escenarios(self) -> dict[str, float]:
        return {"conservador": round(self.filled_conservador, 6), "base": round(self.filled, 6),
                "optimista": round(self.filled_optimista, 6)}

    def _marcar(self, ts_ms: int) -> None:
        for esc, sh in (("conservador", self.filled_conservador), ("base", self.filled), ("optimista", self.filled_optimista)):
            if sh > 1e-9 and self.ts_fill[esc] is None:
                self.ts_fill[esc] = ts_ms


class FillModel:
    """`fill_baseline_prob` solo se conserva como referencia para los informes: no decide nada."""

    def __init__(self, slippage_ticks: int = 1, fill_baseline_prob: float = 0.6, seed: int = 7):
        self.slippage_ticks = slippage_ticks
        self.fill_baseline_prob = fill_baseline_prob
        self.seed = seed

    # ------------------------------------------------------------ taker
    def fill_taker(self, leg: Leg, book: OrderBook, fee_rate: float, ts_ms: int, size: float | None = None) -> Fill:
        want = leg.size if size is None else size
        slip = self.slippage_ticks * book.tick_size
        if leg.side == "BUY":
            w = book.walk_buy(want)
            notional = w.notional + slip * w.shares
        else:
            w = book.walk_sell(want)
            notional = max(w.notional - slip * w.shares, 0.0)
        avg = notional / w.shares if w.shares > 0 else 0.0
        fee = taker_fee(w.shares, avg, fee_rate)
        return Fill(leg.token_id, leg.side, w.shares, avg, notional, fee, ts_ms, "taker")

    # ------------------------------------------------------------ maker
    def place_maker(self, leg: Leg, book: OrderBook, ts_ms: int) -> MakerOrder:
        levels = book.bids if leg.side == "BUY" else book.asks
        ahead = levels.get(leg.price, 0.0)
        return MakerOrder(leg.token_id, leg.side, leg.price, leg.size, ahead, ts_ms, queue_inicial=ahead)

    def maker_on_trade(self, order: MakerOrder, trade: dict, ts_ms: int) -> float:
        """Devuelve shares llenados (escenario BASE) por este trade. 0 si no aplica."""
        if order.done or trade["token_id"] != order.token_id:
            return 0.0
        px = float(trade["price"])
        if order.side == "BUY":
            cruza = trade["side"] == "SELL" and px <= order.price + 1e-9
            barre = trade["side"] == "SELL" and px < order.price - 1e-9
        else:
            cruza = trade["side"] == "BUY" and px >= order.price - 1e-9
            barre = trade["side"] == "BUY" and px > order.price + 1e-9
        if not cruza:
            return 0.0
        avail = float(trade["size"])
        order.vol_cruzado += avail
        antes = order.filled
        if barre:
            # el agresor pasó de largo por nuestro nivel: todo lo que había ahí, incluidos nosotros, se consumió
            order.barrido = True
            order.causa = "barrido"
            order.queue_ahead = 0.0
            got = order.remaining
        else:
            order.vol_nivel_desde_libro += avail
            used = min(order.queue_ahead, avail)
            order.queue_ahead -= used
            avail -= used
            got = min(order.remaining, avail)
            if got > 1e-9 and not order.causa:
                order.causa = "trade"
        if got > 1e-9:
            self._record(order, got, ts_ms)
        order._marcar(ts_ms)
        return order.filled - antes

    def maker_on_book(self, order: MakerOrder, book: OrderBook, ts_ms: int) -> float:
        """Libro nuevo: si cruzó nuestro precio nos llenaron todo; si no, se actualiza la cola BASE."""
        if order.done or book.token_id != order.token_id:
            return 0.0
        ba, bb = book.best_ask, book.best_bid
        tick = book.tick_size or 1e-9
        if order.side == "BUY":
            atravesado = ba is not None and ba < order.price - tick / 2
            empatado = ba is not None and abs(ba - order.price) <= tick / 2
            opuesto = book.asks.get(order.price, 0.0) if empatado else 0.0
        else:
            atravesado = bb is not None and bb > order.price + tick / 2
            empatado = bb is not None and abs(bb - order.price) <= tick / 2
            opuesto = book.bids.get(order.price, 0.0) if empatado else 0.0
        if atravesado:
            # El precio pasó de largo por nuestro nivel: lo que hubiera ahí se consumió entero.
            order.barrido = True
            order.causa = "barrido"
            order.queue_ahead = 0.0
            got = order.remaining
            self._record(order, got, ts_ms)
            order._marcar(ts_ms)
            return got
        if empatado and opuesto > 0:
            # Empate: hay contrapartida exactamente a nuestro precio. Eso no nos pasa por encima,
            # así que **no salta la cola**: el volumen ofrecido consume primero lo que hay delante.
            # Solo cuenta el incremento sobre lo ya aplicado, o un empate que dure varios libros se
            # contaría tantas veces como libros lleguen.
            nuevo_vol = max(opuesto - order.lock_aplicado, 0.0)
            order.lock_aplicado = opuesto
            if nuevo_vol > 0:
                order.vol_cruzado += nuevo_vol
                usado = min(order.queue_ahead, nuevo_vol)
                order.queue_ahead -= usado
                got = min(order.remaining, nuevo_vol - usado)
                if got > 1e-9:
                    if not order.causa:
                        order.causa = "empate"
                    self._record(order, got, ts_ms)
                order._marcar(ts_ms)
                return got
            return 0.0
        order.lock_aplicado = 0.0
        levels = book.bids if order.side == "BUY" else book.asks
        ahora = levels.get(order.price, 0.0)
        esperado = max(order.nivel_visto - order.vol_nivel_desde_libro, 0.0)
        if ahora < esperado - 1e-9:
            cancelado = esperado - ahora
            order.cancelado_delante += cancelado
            order.queue_ahead = max(order.queue_ahead - cancelado, 0.0)
        order.nivel_visto = ahora
        order.vol_nivel_desde_libro = 0.0
        return 0.0

    @staticmethod
    def _record(order: MakerOrder, shares: float, ts_ms: int) -> None:
        order.filled += shares
        order.fills.append(Fill(order.token_id, order.side, shares, order.price, shares * order.price, 0.0, ts_ms, "maker"))
