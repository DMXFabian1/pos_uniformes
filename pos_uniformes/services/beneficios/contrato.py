"""Contrato del motor de beneficios (§2.3 del diseño, ampliado con D6).

Las entradas son explícitas e inmutables y se validan antes de calcular. Los
importes son `Decimal` en centavos exactos; un `float` se rechaza.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

CERO = Decimal("0.00")
CIEN = Decimal("100")

OFERTA = "oferta"
LIQUIDACION = "liquidacion"
TIPOS_REBAJA = (OFERTA, LIQUIDACION)

MODALIDAD_DESCUENTO = "descuento"
MODALIDAD_MONEDERO = "monedero"
MODALIDADES = (MODALIDAD_DESCUENTO, MODALIDAD_MONEDERO)

ORIGEN_KIOSKO_EN_LINEA = "kiosko_en_linea"
ORIGEN_KIOSKO_SIN_CONEXION = "kiosko_sin_conexion"
ORIGEN_SERVIDOR = "servidor"
ORIGENES = (ORIGEN_KIOSKO_EN_LINEA, ORIGEN_KIOSKO_SIN_CONEXION, ORIGEN_SERVIDOR)

MEDIO_EFECTIVO = "efectivo"
MEDIO_TARJETA = "tarjeta"
MEDIO_MONEDERO = "monedero"
MEDIOS = (MEDIO_EFECTIVO, MEDIO_TARJETA, MEDIO_MONEDERO)


class EntradaInvalida(ValueError):
    """La entrada no cumple el contrato. El texto dice qué campo y por qué."""


class SkuConCategoriasIncompatibles(EntradaInvalida):
    """A2 (Daniel, 2026-11-11): un mismo SKU llegó con categorías distintas.

    En el catálogo un SKU tiene una sola categoría (`variante.sku` único y
    `producto.categoria_id` único), así que dos categorías distintas en la misma
    venta indican un origen mezclado. El motor no elige ni normaliza: rechaza la
    entrada y conserva, por SKU, cada línea con la categoría tal como llegó.
    """

    codigo = "SKU_CATEGORIAS_INCOMPATIBLES"

    def __init__(self, conflictos: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]):
        self.conflictos = conflictos
        detalle = "; ".join(
            f"{sku!r}: " + ", ".join(f"{uid} → {cat!r}" for uid, cat in lineas) for sku, lineas in conflictos
        )
        super().__init__(f"SKU con categorías incompatibles: {detalle}")


# ─── Entradas ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Rebaja:
    tipo: str          # "oferta" | "liquidacion"
    precio: Decimal    # precio rebajado por pieza


@dataclass(frozen=True)
class LineaEntrada:
    linea_uid: str                 # D1: UUID v4 creado al capturar la línea
    sku: str | None
    cantidad: int
    precio_lista: Decimal          # por pieza
    categoria: str = ""            # vacío cuenta como uniforme
    rebaja: Rebaja | None = None
    promo_3pz: bool = False
    nombre: str = ""
    talla: str = ""


@dataclass(frozen=True)
class ClienteCtx:
    id: int | None
    programa_clave: str | None
    tasa_monedero: Decimal | None  # % de abono; None = sin programa
    pct_mayoreo: Decimal | None    # % de descuento si el programa lo ofrece
    activo: bool = True


@dataclass(frozen=True)
class CompradoraCtx:
    codigo: str
    pct_nivel: Decimal | None      # None o ≤ base: sin nivel (5 % parejo)
    restante_tope: Decimal | None  # None = sin tope


@dataclass(frozen=True)
class Pago:
    medio: str                     # "efectivo" | "tarjeta" | "monedero"
    importe: Decimal


@dataclass(frozen=True)
class ReglasCtx:
    version: str = "2026-11-12"  # regla B: Monedero sin la comisión de tarjeta
    pct_base_empleada: Decimal = Decimal("5")
    tope_pct_uniforme: Decimal = Decimal("10")
    categorias_no_uniforme: frozenset = frozenset(
        {"ropa casual", "temporada", "accesorio", "ropa interior", "deportivo casual"}
    )
    pct_comision_tarjeta: Decimal = Decimal("4.5")
    pct_otra_persona: Decimal = Decimal("5")


@dataclass(frozen=True)
class EntradaVenta:
    lineas: tuple[LineaEntrada, ...]
    fecha_venta: datetime                         # D6
    origen_calculo: str = ORIGEN_KIOSKO_EN_LINEA  # D6
    cliente: ClienteCtx | None = None
    modalidad_mayorista: str | None = None        # C4: "descuento" | "monedero" | None
    descuento_empleada: bool = False              # autorizado
    compradora: CompradoraCtx | None = None       # None con descuento = «otra persona» (R2)
    saldo_a_usar: Decimal = CERO
    saldo_disponible: Decimal = CERO
    pago_tarjeta: bool = False
    pagos: tuple[Pago, ...] = ()                  # D6: si viene, manda sobre pago_tarjeta
    vendedora: str | None = None                  # D6
    reglas: ReglasCtx = field(default_factory=ReglasCtx)


# ─── Validación ──────────────────────────────────────────────────────────


def _importe(nombre: str, valor, *, puede_cero: bool = True) -> None:
    if not isinstance(valor, Decimal):
        raise EntradaInvalida(f"{nombre} debe ser Decimal, no {type(valor).__name__}")
    if not valor.is_finite():
        raise EntradaInvalida(f"{nombre} no es un número finito")
    if valor < 0 or (not puede_cero and valor == 0):
        raise EntradaInvalida(f"{nombre} debe ser {'≥' if puede_cero else '>'} 0")
    if valor != valor.quantize(Decimal("0.01")):
        raise EntradaInvalida(f"{nombre} tiene fracciones de centavo: {valor}")


def _pct(nombre: str, valor) -> None:
    if valor is None:
        return
    if not isinstance(valor, Decimal) or not valor.is_finite():
        raise EntradaInvalida(f"{nombre} debe ser Decimal")
    if valor < 0 or valor > CIEN:
        raise EntradaInvalida(f"{nombre} debe ir de 0 a 100")


def _validar_categoria_unica_por_sku(lineas) -> None:
    """A2: todas las líneas de un SKU traen la misma categoría, comparada tal
    como llegó (sin normalizar). Las líneas sin SKU no se comparan."""
    por_sku: dict[str, list[tuple[str, str]]] = {}
    for linea in lineas:
        if linea.sku is not None:
            por_sku.setdefault(linea.sku, []).append((linea.linea_uid, linea.categoria))
    conflictos = tuple(
        (sku, tuple(sorted(filas)))
        for sku, filas in sorted(por_sku.items())
        if len({cat for _, cat in filas}) > 1
    )
    if conflictos:
        raise SkuConCategoriasIncompatibles(conflictos)


def validar(entrada: EntradaVenta) -> None:
    if not isinstance(entrada, EntradaVenta):
        raise EntradaInvalida("Se esperaba una EntradaVenta")
    if not entrada.lineas:
        raise EntradaInvalida("La venta no tiene líneas")
    if not isinstance(entrada.fecha_venta, datetime):
        raise EntradaInvalida("fecha_venta debe ser datetime")
    if entrada.origen_calculo not in ORIGENES:
        raise EntradaInvalida(f"origen_calculo desconocido: {entrada.origen_calculo!r}")
    if entrada.modalidad_mayorista not in (None, *MODALIDADES):
        raise EntradaInvalida(f"modalidad_mayorista desconocida: {entrada.modalidad_mayorista!r}")
    vistos: set[str] = set()
    for n, linea in enumerate(entrada.lineas, 1):
        donde = f"línea {n}"
        if not isinstance(linea, LineaEntrada):
            raise EntradaInvalida(f"{donde}: se esperaba LineaEntrada")
        try:
            uid = uuid.UUID(str(linea.linea_uid))
        except (ValueError, AttributeError, TypeError) as exc:
            raise EntradaInvalida(f"{donde}: linea_uid no es un UUID") from exc
        if str(uid) != str(linea.linea_uid).lower():
            raise EntradaInvalida(f"{donde}: linea_uid debe ir en forma canónica")
        if linea.linea_uid in vistos:
            raise EntradaInvalida(f"{donde}: linea_uid repetido")
        vistos.add(linea.linea_uid)
        if linea.sku is not None and not isinstance(linea.sku, str):
            raise EntradaInvalida(f"{donde}: sku debe ser texto")
        if not isinstance(linea.cantidad, int) or isinstance(linea.cantidad, bool) or linea.cantidad < 1:
            raise EntradaInvalida(f"{donde}: cantidad debe ser un entero ≥ 1")
        _importe(f"{donde}: precio_lista", linea.precio_lista)
        if linea.rebaja is not None:
            if linea.rebaja.tipo not in TIPOS_REBAJA:
                raise EntradaInvalida(f"{donde}: rebaja de tipo desconocido")
            _importe(f"{donde}: precio rebajado", linea.rebaja.precio, puede_cero=False)
    _validar_categoria_unica_por_sku(entrada.lineas)
    c = entrada.cliente
    if c is not None:
        _pct("tasa_monedero", c.tasa_monedero)
        _pct("pct_mayoreo", c.pct_mayoreo)
    if entrada.compradora is not None:
        _pct("pct_nivel", entrada.compradora.pct_nivel)
        if entrada.compradora.restante_tope is not None:
            if not isinstance(entrada.compradora.restante_tope, Decimal):
                raise EntradaInvalida("restante_tope debe ser Decimal")
        if not entrada.descuento_empleada:
            raise EntradaInvalida("Hay compradora pero no está autorizado el descuento de empleada")
    _importe("saldo_a_usar", entrada.saldo_a_usar)
    _importe("saldo_disponible", entrada.saldo_disponible)
    r = entrada.reglas
    for nombre in ("pct_base_empleada", "tope_pct_uniforme", "pct_comision_tarjeta", "pct_otra_persona"):
        _pct(nombre, getattr(r, nombre))
    for p in entrada.pagos:
        if not isinstance(p, Pago) or p.medio not in MEDIOS:
            raise EntradaInvalida("pagos: medio desconocido")
        _importe(f"pagos ({p.medio})", p.importe)


# ─── Resultados ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Descuento:
    pct: Decimal            # el % de la línea; con piezas al base, el del nivel
    importe: Decimal
    fuente: str | None      # "mayoreo" | "empleada" | "otra_persona" | None


@dataclass(frozen=True)
class LineaCalculo:
    linea_uid: str                               # D1 (en una agrupada, el menor)
    lineas_origen: tuple[tuple[str, int], ...]   # D1/P3: (uid, piezas) de cada línea original
    sku: str | None
    cantidad: int
    precio_lista: Decimal
    precio_unitario: Decimal                      # lista o rebajado
    importe: Decimal                              # precio_unitario × cantidad
    clasificacion_al_vender: str                  # "normal" | "oferta" | "liquidacion" | "3pz" (C7)
    piezas_con_nivel: int                         # C9
    piezas_al_base: int
    descuento: Descuento
    cobrado_antes_redondeo: Decimal
    parte_redondeo: Decimal                       # I8, con signo
    cobrado: Decimal
    consumo_tope: Decimal                         # C8/C9, a precio de lista
    parte_saldo: Decimal                          # C2
    base_monedero: Decimal
    abono_linea: Decimal
    base_leal: Decimal
    comision_linea: Decimal                       # D6
    motivos: tuple[str, ...]


@dataclass(frozen=True)
class MonederoCalculo:
    tasa: Decimal
    base: Decimal
    abono: Decimal


@dataclass(frozen=True)
class Calculo:
    version_motor: str
    version_reglas: str
    origen_calculo: str
    fecha_venta: datetime
    vendedora: str | None
    lineas: tuple[LineaCalculo, ...]
    subtotal_lista: Decimal          # Σ precio de lista × cantidad
    subtotal: Decimal                # Σ importe (con rebajas)
    descuento_total: Decimal
    ahorro_rebajas: Decimal
    total_antes_redondeo: Decimal
    redondeo: Decimal
    redondeo_rondas: int
    redondeo_excepcion_d2: Decimal
    total: Decimal
    saldo_usado: Decimal
    por_cobrar: Decimal
    pagos: tuple[Pago, ...]
    comision_tarjeta: Decimal
    neto_tienda: Decimal
    modalidad_mayorista_elegida: str | None
    descuento_aplicado: bool
    descuento_empleada: bool
    monedero: MonederoCalculo | None
    base_leal_total: Decimal
    consumo_tope_total: Decimal
    motivos_ticket: tuple[str, ...]
