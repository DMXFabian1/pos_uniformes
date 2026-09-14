"""Pata suelta: una captura de spread en la que solo se llenó uno de los dos lados.

La fase anterior dejó el problema localizado y sin resolver. `TENNIS_SPREAD_CAPTURE` entra por los
dos lados a la vez; cuando se llenan los dos, cobra el spread y gana +1,72 por operación, estable en
tres muestras. Cuando solo se llena uno, queda un direccional que nadie pidió, se sostiene una
mediana de 586 segundos y cuesta −6,9. Pasa la mitad de las veces.

Lo que **no** se sabe es cuándo aparece esa pérdida. Si aparece en el primer segundo, cerrar rápido
no sirve de nada y la estrategia no tiene arreglo por ese lado. Si se acumula a lo largo de los diez
minutos, cerrar pronto la rescataría. Los datos anteriores no pueden distinguir los dos casos porque
para la captura de spread nunca se guardó trayectoria posterior al llenado.

Este módulo construye ese dato y nada más. No cierra posiciones, no cambia entradas, no propone
umbrales. Mide qué habría costado salir en cada instante.

Dos reglas que no se saltan:

- **El precio de salida sale del libro, del lado correcto y por VWAP.** Cerrar una compra de 50
  shares significa vender contra los bids, atravesando los niveles que haga falta. El mid no es un
  precio ejecutable y aquí no se usa nunca como sustituto: si no hay profundidad para salir, el
  punto queda marcado como incompleto y se dice, en vez de rellenarlo con un número bonito.
- **El resultado hipotético nunca se mezcla con el real.** Todo lo que calcula este módulo lleva
  `contrafactual` en el nombre y vive en sus propias tablas. No toca el efectivo, no toca los topes
  de riesgo y no entra en ningún P&L realizado.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from .book import OrderBook

# Instantes en los que se fotografía la pata suelta, desde el primer llenado.
HORIZONTES_MS: tuple[int, ...] = (1_000, 5_000, 10_000, 20_000, 30_000, 60_000,
                                  120_000, 300_000, 600_000)

# Fracciones de la pérdida final cuyo momento de aparición se busca (el "punto de no retorno").
FRACCIONES = (0.25, 0.50, 0.75, 0.90)

# Cómo terminó la pata suelta.
RECUPERADA = "recuperada"          # la segunda pata llegó y la posición se completó
CERRADA = "cerrada"                # se deshizo el inventario sin completar
CADUCADA = "caducada"              # se agotó el tiempo máximo de sostén
ABIERTA = "abierta"                # la corrida terminó antes que la posición


@dataclass
class Salida:
    """Qué costaría deshacer una posición ahora mismo, con la liquidez que hay de verdad."""
    precio: float | None = None           # VWAP ejecutable para TODO el tamaño
    peor_nivel: float | None = None       # el nivel más malo que habría que atravesar
    shares: float = 0.0                   # cuánto se podría cerrar de verdad
    completa: bool = False                # ¿alcanza la profundidad para el tamaño entero?
    slippage: float | None = None         # VWAP contra el mejor precio del lado por el que se sale
    profundidad: float = 0.0              # shares disponibles en ese lado

    @property
    def ejecutable(self) -> bool:
        return self.precio is not None and self.completa


def coste_de_salir(book: OrderBook, lado_entrada: str, shares: float) -> Salida:
    """VWAP al que se podría deshacer `shares` ahora, saliendo por el lado correcto del libro.

    `lado_entrada` es el lado por el que se entró: una compra se deshace **vendiendo** contra los
    bids, y una venta se deshace **comprando** contra los asks. Es la parte que más fácil se
    equivoca y la que más engaña, porque usar el mid hace que salir parezca gratis.

    Si la profundidad no llega para el tamaño entero, `completa` queda en False y el precio es el
    del trozo que sí se podría cerrar. Quien lo consuma tiene que decidir qué hacer con eso; lo que
    no puede es no enterarse.
    """
    if shares <= 0 or book is None:
        return Salida()
    if lado_entrada.upper() == "BUY":
        w = book.walk_sell(shares)          # deshacer un largo: vender contra los bids
        mejor = book.best_bid
        profundidad = sum(book.bids.values())
    else:
        w = book.walk_buy(shares)           # deshacer un corto: comprar contra los asks
        mejor = book.best_ask
        profundidad = sum(book.asks.values())
    if w.shares <= 0:
        return Salida(profundidad=profundidad)
    slip = None if mejor is None else round(w.avg_price - mejor, 6)
    return Salida(precio=round(w.avg_price, 6), peor_nivel=w.worst_price, shares=round(w.shares, 6),
                  completa=w.shares >= shares - 1e-9, slippage=slip, profundidad=profundidad)


def contrafactual_pnl(lado_entrada: str, precio_entrada: float, shares: float,
                      salida: Salida) -> float | None:
    """Resultado **hipotético** de haber cerrado la pata en este instante, en USD.

    Una compra gana si se puede vender más caro de lo que se compró; una venta, al revés. Sin
    comisiones porque ambas patas serían maker en el caso que nos interesa, y porque el objeto de la
    medida es el movimiento del precio, no el coste de la comisión: añadirla mezclaría dos efectos
    que hay que poder mirar por separado.

    Devuelve `None` si no hay salida ejecutable. Nunca devuelve un número apoyado en el mid.
    """
    if not salida.ejecutable or precio_entrada is None or shares <= 0:
        return None
    if lado_entrada.upper() == "BUY":
        return round((salida.precio - precio_entrada) * shares, 6)
    return round((precio_entrada - salida.precio) * shares, 6)


@dataclass
class Punto:
    """Una foto de la pata suelta en un instante.

    `ts_ms` es el instante que el horizonte pedía; `ts_medido_ms` es cuándo se pudo mirar de verdad.
    Los dos casi nunca coinciden: el libro solo se observa cuando llega un evento o cuando pasa el
    reloj del motor, así que un horizonte que vence entre dos eventos se mide con el primero que
    llegue después. `desfase_medicion_ms` dice cuánto, para que nadie tenga que suponerlo — un
    horizonte de 1 s medido 800 ms tarde no es un horizonte de 1 s.
    """
    horizonte_ms: int
    ts_ms: int
    ts_medido_ms: int = 0
    desfase_medicion_ms: int = 0
    best_bid: float | None = None
    best_ask: float | None = None
    mid: float | None = None
    spread: float | None = None
    profundidad_salida: float = 0.0
    distancia_entrada: float | None = None     # mid menos nuestro precio de entrada
    salida_precio: float | None = None
    salida_peor_nivel: float | None = None
    salida_slippage: float | None = None
    salida_completa: bool = False
    contrafactual_pnl: float | None = None
    contrafactual_pnl_share: float | None = None
    contrafactual_pnl_pct: float | None = None
    incompleto: str = ""                       # por qué no se pudo calcular, si no se pudo

    def to_row(self, p: "PataSuelta", run_id: str) -> dict[str, Any]:
        return {
            "ts_ms": self.ts_ms, "run_id": run_id, "experiment": p.experiment,
            "partial_leg_id": p.partial_leg_id, "strategy": p.strategy,
            "condition_id": p.condition_id, "token_id": p.token_id,
            "horizonte_ms": self.horizonte_ms,
            "ts_medido_ms": self.ts_medido_ms or self.ts_ms,
            "desfase_medicion_ms": self.desfase_medicion_ms,
            "best_bid": self.best_bid, "best_ask": self.best_ask, "mid": self.mid,
            "spread": self.spread, "profundidad_salida": round(self.profundidad_salida, 4),
            "distancia_entrada": self.distancia_entrada,
            "salida_precio": self.salida_precio, "salida_peor_nivel": self.salida_peor_nivel,
            "salida_slippage": self.salida_slippage, "salida_completa": self.salida_completa,
            "contrafactual_pnl": self.contrafactual_pnl,
            "contrafactual_pnl_share": self.contrafactual_pnl_share,
            "contrafactual_pnl_pct": self.contrafactual_pnl_pct,
            "incompleto": self.incompleto or None,
        }


@dataclass
class PataSuelta:
    """Una posición de captura de spread con un solo lado llenado, seguida en el tiempo.

    Existe como entidad propia y con identificador propio: no se deduce del P&L ni del motivo de
    cierre. Que una posición perdiera dinero no la convierte en pata suelta, y que ganara no la
    excluye.
    """
    partial_leg_id: str
    experiment: str
    signal_id: str
    strategy: str
    condition_id: str
    event_id: str = ""
    # --- la pata que sí se llenó
    token_id: str = ""
    lado: str = ""                        # BUY | SELL
    precio_entrada: float = 0.0
    shares: float = 0.0
    # --- la que falta
    token_faltante: str = ""
    lado_faltante: str = ""
    precio_faltante: float = 0.0          # a qué precio la estábamos esperando
    # --- T0: el instante exacto del primer llenado
    t0_ms: int = 0
    t0_best_bid: float | None = None
    t0_best_ask: float | None = None
    t0_spread: float | None = None
    t0_profundidad: float = 0.0
    t0_precio_completar: float | None = None   # cruzar ahora para completar la pata que falta
    t0_coste_completar: float | None = None    # cuánto costaría eso, en USD
    t0_salida_precio: float | None = None      # cerrar la pata llenada ahora mismo
    t0_contrafactual_pnl: float | None = None
    spread_esperado: float = 0.0
    ventaja_prometida: float | None = None
    # --- lo que se va midiendo
    puntos: list[Punto] = field(default_factory=list)
    hechos: set[int] = field(default_factory=set)
    # --- desenlace
    desenlace: str = ABIERTA
    ts_fin: int = 0
    time_to_second_leg_ms: int | None = None
    pnl_realizado_final: float | None = None
    motivo_cierre: str = ""

    @property
    def duracion_ms(self) -> int:
        return max(self.ts_fin - self.t0_ms, 0) if self.ts_fin else 0

    def punto(self, horizonte_ms: int) -> Punto | None:
        for p in self.puntos:
            if p.horizonte_ms == horizonte_ms:
                return p
        return None

    def to_row(self, run_id: str) -> dict[str, Any]:
        return {
            "ts_ms": self.t0_ms, "run_id": run_id, "experiment": self.experiment,
            "partial_leg_id": self.partial_leg_id, "signal_id": self.signal_id,
            "strategy": self.strategy, "condition_id": self.condition_id, "event_id": self.event_id,
            "token_id": self.token_id, "lado": self.lado,
            "precio_entrada": round(self.precio_entrada, 6), "shares": round(self.shares, 4),
            "token_faltante": self.token_faltante, "lado_faltante": self.lado_faltante,
            "precio_faltante": round(self.precio_faltante, 6),
            "t0_ms": self.t0_ms, "t0_best_bid": self.t0_best_bid, "t0_best_ask": self.t0_best_ask,
            "t0_spread": self.t0_spread, "t0_profundidad": round(self.t0_profundidad, 4),
            "t0_precio_completar": self.t0_precio_completar,
            "t0_coste_completar": self.t0_coste_completar,
            "t0_salida_precio": self.t0_salida_precio,
            "t0_contrafactual_pnl": self.t0_contrafactual_pnl,
            "spread_esperado": round(self.spread_esperado, 6),
            "ventaja_prometida": self.ventaja_prometida,
            "desenlace": self.desenlace, "ts_fin": self.ts_fin or None,
            "duracion_ms": self.duracion_ms or None,
            "time_to_second_leg_ms": self.time_to_second_leg_ms,
            "pnl_realizado_final": self.pnl_realizado_final,
            "motivo_cierre": self.motivo_cierre or None,
            "puntos_medidos": len(self.puntos),
        }


def nuevo_id(experiment: str, signal_id: str, token_id: str, t0_ms: int) -> str:
    """Identificador estable y único: la misma pata da siempre el mismo, y dos patas nunca chocan."""
    crudo = f"{experiment}|{signal_id}|{token_id}|{t0_ms}"
    return "pl-" + hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:14]


def abrir(experiment: str, signal, llenada, faltante, t0_ms: int, shares: float,
          precio_entrada: float, book_propio: OrderBook | None,
          book_faltante: OrderBook | None) -> PataSuelta:
    """Crea la pata suelta y toma la foto de T0, que es el instante que más importa.

    En T0 se guardan las dos preguntas de golpe: qué costaría **completar** la pata que falta
    cruzando el libro ahora, y qué costaría **deshacer** la que ya tenemos. Las dos son la
    alternativa real a quedarse esperando, y sin ellas la comparación posterior no significa nada.
    """
    p = PataSuelta(
        partial_leg_id=nuevo_id(experiment, signal.signal_id, llenada.token_id, t0_ms),
        experiment=experiment, signal_id=signal.signal_id,
        strategy=signal.strategy or signal.kind, condition_id=signal.condition_id,
        event_id=getattr(signal, "event_id", "") or "",
        token_id=llenada.token_id, lado=llenada.side,
        precio_entrada=precio_entrada, shares=shares,
        token_faltante=faltante.token_id, lado_faltante=faltante.side,
        precio_faltante=faltante.price, t0_ms=t0_ms,
        ventaja_prometida=signal.meta.get("edge_net") if isinstance(signal.meta, dict) else None,
    )
    if book_propio is not None and book_propio.is_valid:
        p.t0_best_bid, p.t0_best_ask = book_propio.best_bid, book_propio.best_ask
        p.t0_spread = round(book_propio.best_ask - book_propio.best_bid, 6)
        s = coste_de_salir(book_propio, llenada.side, shares)
        p.t0_profundidad = s.profundidad
        p.t0_salida_precio = s.precio
        p.t0_contrafactual_pnl = contrafactual_pnl(llenada.side, precio_entrada, shares, s)
    if book_faltante is not None and book_faltante.is_valid:
        # completar ahora significa cruzar: la pata que falta se ejecutaría como taker
        w = book_faltante.walk_buy(shares) if faltante.side == "BUY" else book_faltante.walk_sell(shares)
        if w.shares > 0:
            p.t0_precio_completar = round(w.avg_price, 6)
            p.t0_coste_completar = round(w.notional, 6)
        p.spread_esperado = round(abs(faltante.price - precio_entrada), 6)
    return p


def medir(p: PataSuelta, ts_ms: int, book: OrderBook | None) -> list[Punto]:
    """Fotografía la pata en los horizontes que ya han vencido. Devuelve los puntos nuevos.

    Un horizonte se mide una sola vez. Si al vencer no hay libro válido o no hay profundidad para
    salir, el punto se guarda igual, marcado con el motivo: un hueco declarado vale y un hueco
    rellenado con el mid no.
    """
    nuevos: list[Punto] = []
    for h in HORIZONTES_MS:
        vence = p.t0_ms + h
        if h in p.hechos or ts_ms < vence:
            continue
        p.hechos.add(h)
        punto = Punto(horizonte_ms=h, ts_ms=vence, ts_medido_ms=ts_ms,
                      desfase_medicion_ms=max(ts_ms - vence, 0))
        if book is None or not book.is_valid:
            punto.incompleto = "sin_libro"
        else:
            punto.best_bid, punto.best_ask = book.best_bid, book.best_ask
            punto.mid = book.mid
            punto.spread = round(book.best_ask - book.best_bid, 6)
            punto.distancia_entrada = round(book.mid - p.precio_entrada, 6)
            s = coste_de_salir(book, p.lado, p.shares)
            punto.profundidad_salida = s.profundidad
            punto.salida_precio = s.precio
            punto.salida_peor_nivel = s.peor_nivel
            punto.salida_slippage = s.slippage
            punto.salida_completa = s.completa
            pnl = contrafactual_pnl(p.lado, p.precio_entrada, p.shares, s)
            if pnl is None:
                punto.incompleto = "sin_profundidad" if s.precio is not None else "sin_liquidez"
            else:
                punto.contrafactual_pnl = pnl
                punto.contrafactual_pnl_share = round(pnl / p.shares, 6) if p.shares else None
                base = p.precio_entrada * p.shares
                punto.contrafactual_pnl_pct = round(pnl / base, 6) if base else None
        p.puntos.append(punto)
        nuevos.append(punto)
    return nuevos


def cerrar(p: PataSuelta, ts_ms: int, desenlace: str, motivo: str = "",
           pnl_realizado: float | None = None, ts_segunda_pata: int | None = None) -> None:
    """Anota el desenlace. El P&L realizado se guarda **al lado** del hipotético, nunca encima."""
    p.desenlace = desenlace
    p.ts_fin = ts_ms
    p.motivo_cierre = motivo
    p.pnl_realizado_final = pnl_realizado
    if ts_segunda_pata is not None:
        p.time_to_second_leg_ms = max(ts_segunda_pata - p.t0_ms, 0)


def punto_de_no_retorno(p: PataSuelta, fracciones: tuple[float, ...] = FRACCIONES) -> dict[str, int | None]:
    """Cuándo el coste de salir alcanza cada fracción de la pérdida final.

    Solo tiene sentido si la pata terminó perdiendo: si acabó en positivo no hay "pérdida final"
    que fraccionar, y devolver un número igualmente sería inventarlo. Se recorren los horizontes en
    orden y se devuelve el primero que llega o supera cada fracción.
    """
    final = p.pnl_realizado_final
    out: dict[str, int | None] = {f"t_{int(f * 100)}pct_ms": None for f in fracciones}
    if final is None or final >= 0:
        return out
    puntos = sorted((x for x in p.puntos if x.contrafactual_pnl is not None),
                    key=lambda x: x.horizonte_ms)
    for f in fracciones:
        objetivo = final * f          # ambos negativos: alcanzar significa ser igual o más negativo
        for x in puntos:
            if x.contrafactual_pnl <= objetivo:
                out[f"t_{int(f * 100)}pct_ms"] = x.horizonte_ms
                break
    return out


def evitable(p: PataSuelta, horizonte_ms: int) -> float | None:
    """Cuánto de la pérdida final se habría ahorrado cerrando en ese horizonte.

    Positivo significa que cerrar ahí habría salido mejor que lo que pasó de verdad. Es una resta
    entre un número hipotético y uno real, así que solo sirve como orden de magnitud y se llama por
    su nombre en todas partes: ahorro **hipotético**.
    """
    x = p.punto(horizonte_ms)
    if x is None or x.contrafactual_pnl is None or p.pnl_realizado_final is None:
        return None
    return round(x.contrafactual_pnl - p.pnl_realizado_final, 6)
