"""El precio de cada talla de una prenda nueva, con «de dónde» salió.

Tanda 2 del rediseño de «Nueva prenda» (2026-11-13). En la caja, el 93 % de
los precios de escuela es el que más se repite para su pieza, nivel y talla,
y el 95 % termina en 5 o 9 (`alta_datos.md` §6). Las plantillas del asistente
viejo traían precios escritos en el código (la bata a $65 cuando en la caja
vale $75); aquí el precio sale de la caja.

Para cada talla:

- **«como las demás»**: el precio que más se repite en la base para esa pieza,
  nivel y talla (a empate, el más alto: nunca se sugiere bajar).
- **«del modelo»**: el de la prenda que se está copiando, cuando la base no
  tiene esa talla (o cuando se pide copiar los precios del modelo, como en
  «escuela igual a otra»).
- **«a mano»**: el que se escribió.

Además, sin bloquear nada:

- Regla 5/9 (Daniel, 2026-11-13): **solo se sugiere** («¿$289?») y siempre
  hacia arriba; un precio que ya es el de las demás escuelas no se discute
  (corbata a $70 o camiseta a $52 son excepciones válidas).
- Aviso ámbar si queda más bajo que en las demás escuelas.
- $0 o vacío no deja guardar (`CatalogService.validar_precio_venta`).

`no_bajar` es la regla de oro para cualquier precio que ya existe.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from typing import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Producto, Variante
from pos_uniformes.services.catalogo_valores_service import forma_oficial_talla

ORIGEN_COMO_LAS_DEMAS = "como las demás"
ORIGEN_DEL_MODELO = "del modelo"
ORIGEN_A_MANO = "a mano"
ORIGEN_FALTA = "falta precio"

PREFERIR_BASE = "base"
PREFERIR_MODELO = "modelo"

_CENTAVO = Decimal("0.01")
_PESO = Decimal("1")


def dinero(valor: object) -> Decimal | None:
    """Decimal con centavos, o None si está vacío o no es número."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    texto = str(valor).strip().replace("$", "").replace(",", "")
    try:
        return Decimal(texto).quantize(_CENTAVO)
    except (InvalidOperation, ValueError):
        return None


def termina_en_5_o_9(precio: object) -> bool:
    valor = dinero(precio)
    if valor is None or valor != valor.to_integral_value():
        return False
    return int(valor) % 10 in (5, 9)


def redondeo_5_9(precio: object) -> Decimal | None:
    """Hacia arriba al peso cerrado y luego el último dígito al 5 o al 9
    (la regla del 22-ago): 280 → 285, 286 → 289, 285.40 → 289, 52 → 55."""
    valor = dinero(precio)
    if valor is None or valor <= 0:
        return None
    entero = int(valor.to_integral_value(rounding=ROUND_CEILING))
    unidad = entero % 10
    if unidad in (5, 9):
        return Decimal(entero).quantize(_CENTAVO)
    destino = entero - unidad + (5 if unidad < 5 else 9)
    return Decimal(destino).quantize(_CENTAVO)


def no_bajar(actual: object, nuevo: object) -> Decimal | None:
    """Regla de oro: `MAX(actual, nuevo)`."""
    a, n = dinero(actual), dinero(nuevo)
    if a is None:
        return n
    if n is None:
        return a
    return max(a, n)


def moda(precios: Counter) -> Decimal | None:
    """El precio que más se repite; a empate, el más alto."""
    if not precios:
        return None
    return max(precios.items(), key=lambda pc: (pc[1], pc[0]))[0]


@dataclass(frozen=True)
class PrecioSugerido:
    talla: str
    precio: Decimal | None
    origen: str
    #: El que más se repite en la base y en cuántas prendas está.
    moda: Decimal | None = None
    prendas_con_moda: int = 0
    #: «¿$289?», solo si el precio no termina en 5 o 9 y no es el de las demás.
    sugerencia_5_9: Decimal | None = None
    aviso: str = ""

    @property
    def falta(self) -> bool:
        return self.precio is None or self.precio <= 0

    @property
    def texto_sugerencia(self) -> str:
        return f"¿${self.sugerencia_5_9:.0f}?" if self.sugerencia_5_9 is not None else ""


def precios_de_la_base(
    session: Session,
    tipo_pieza_id: int,
    nivel_id: int | None,
    *,
    excluir_escuela_id: int | None = None,
) -> dict[str, Counter]:
    """{talla oficial: Counter(precio → cuántas prendas)} en una consulta.

    Cada prenda cuenta una vez por talla (si una talla está en dos colores,
    con su precio más alto)."""
    stmt = (
        select(Variante.producto_id, Variante.talla, Variante.precio_venta)
        .join(Producto, Producto.id == Variante.producto_id)
        .where(
            Producto.activo.is_(True),
            Variante.activo.is_(True),
            Producto.tipo_pieza_id == int(tipo_pieza_id),
        )
    )
    stmt = stmt.where(
        Producto.nivel_educativo_id.is_(None) if nivel_id is None else Producto.nivel_educativo_id == int(nivel_id)
    )
    if excluir_escuela_id is not None:
        stmt = stmt.where((Producto.escuela_id.is_(None)) | (Producto.escuela_id != int(excluir_escuela_id)))
    por_prenda: dict[tuple[int, str], Decimal] = {}
    for producto_id, talla, precio in session.execute(stmt).all():
        clave = (int(producto_id), forma_oficial_talla(talla))
        valor = dinero(precio)
        if valor is None or valor <= 0:
            continue
        if clave not in por_prenda or valor > por_prenda[clave]:
            por_prenda[clave] = valor
    conteos: dict[str, Counter] = defaultdict(Counter)
    for (_pid, talla), precio in por_prenda.items():
        conteos[talla][precio] += 1
    return dict(conteos)


def sugerir_desde(
    tallas: Iterable[str],
    conteos: Mapping[str, Counter] | None = None,
    *,
    modelo: Mapping[str, object] | None = None,
    a_mano: Mapping[str, object] | None = None,
    preferir: str = PREFERIR_BASE,
) -> list[PrecioSugerido]:
    """Puro: el precio de cada talla con su origen, sugerencia 5/9 y aviso."""
    conteos = conteos or {}
    modelo = {forma_oficial_talla(t): dinero(p) for t, p in (modelo or {}).items()}
    a_mano = {forma_oficial_talla(t): dinero(p) for t, p in (a_mano or {}).items() if dinero(p) is not None}
    salida: list[PrecioSugerido] = []
    for talla_cruda in tallas:
        talla = forma_oficial_talla(talla_cruda)
        contador = conteos.get(talla) or Counter()
        la_moda = moda(contador)
        con_moda = contador.get(la_moda, 0) if la_moda is not None else 0
        del_modelo = modelo.get(talla)
        if talla in a_mano:
            precio, origen = a_mano[talla], ORIGEN_A_MANO
        elif preferir == PREFERIR_MODELO and del_modelo is not None:
            precio, origen = del_modelo, ORIGEN_DEL_MODELO
        elif la_moda is not None:
            precio, origen = la_moda, ORIGEN_COMO_LAS_DEMAS
        elif del_modelo is not None:
            precio, origen = del_modelo, ORIGEN_DEL_MODELO
        else:
            precio, origen = None, ORIGEN_FALTA
        if origen == ORIGEN_DEL_MODELO and la_moda is not None and precio == la_moda:
            origen = ORIGEN_COMO_LAS_DEMAS
        salida.append(
            PrecioSugerido(
                talla=talla,
                precio=precio,
                origen=origen,
                moda=la_moda,
                prendas_con_moda=con_moda,
                sugerencia_5_9=_sugerencia(precio, la_moda),
                aviso=aviso_precio(precio, la_moda),
            )
        )
    return salida


def _sugerencia(precio: Decimal | None, la_moda: Decimal | None) -> Decimal | None:
    if precio is None or precio <= 0 or termina_en_5_o_9(precio):
        return None
    if la_moda is not None and precio == la_moda:
        return None  # ya es el precio de las demás escuelas (corbata $70, camiseta $52)
    sugerida = redondeo_5_9(precio)
    return sugerida if sugerida is not None and sugerida != precio else None


def aviso_precio(precio: Decimal | None, la_moda: Decimal | None) -> str:
    """Texto de aviso (no bloquea, salvo el de $0, que `validar` rechaza)."""
    if precio is None:
        return "Falta el precio."
    if precio <= 0:
        return "El precio no puede quedar en $0."
    if la_moda is not None and precio < la_moda:
        return f"Queda más bajo que en las demás escuelas (${la_moda:.0f})."
    return ""


def origen_de(
    precio: Decimal | None,
    la_moda: Decimal | None,
    precio_modelo: Decimal | None,
    origen_actual: str = ORIGEN_A_MANO,
) -> str:
    """Puro: de dónde sale un precio después de editarlo. Igual al que más
    se repite → «como las demás»; igual al del modelo → «del modelo»; si ya
    no coincide con ninguno, «a mano». Un origen que no se puede comprobar
    (sin moda ni modelo, como en un plan de la skill) se respeta."""
    if precio is None:
        return ORIGEN_FALTA
    if la_moda is not None and precio == la_moda:
        return ORIGEN_COMO_LAS_DEMAS
    if precio_modelo is not None and precio == precio_modelo:
        return ORIGEN_DEL_MODELO
    if origen_actual in (ORIGEN_COMO_LAS_DEMAS, ORIGEN_DEL_MODELO, ORIGEN_FALTA):
        return ORIGEN_A_MANO
    return origen_actual


def sugerir(
    session: Session,
    tipo_pieza_id: int | None,
    nivel_id: int | None,
    tallas: Iterable[str],
    *,
    modelo: Mapping[str, object] | None = None,
    a_mano: Mapping[str, object] | None = None,
    preferir: str = PREFERIR_BASE,
    excluir_escuela_id: int | None = None,
) -> list[PrecioSugerido]:
    """`sugerir_desde` con los precios de la base (una consulta)."""
    conteos = (
        precios_de_la_base(session, tipo_pieza_id, nivel_id, excluir_escuela_id=excluir_escuela_id)
        if tipo_pieza_id is not None
        else {}
    )
    return sugerir_desde(tallas, conteos, modelo=modelo, a_mano=a_mano, preferir=preferir)


def validar(precio: object) -> Decimal:
    """Rechaza vacío, negativo o $0 (lo mismo que `CatalogService`)."""
    from pos_uniformes.services.catalog_service import CatalogService

    return CatalogService.validar_precio_venta(precio)
