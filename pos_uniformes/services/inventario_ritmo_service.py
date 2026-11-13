"""Ritmo de venta de cada talla para la pestaña Inventario (tanda 5).

La pregunta «¿se va a acabar?» ya la contesta Analítica con lo que se vendió
en la Libreta (`analitica_tablero_service.por_acabarse`). Aquí se usa la
MISMA regla, talla por talla, para la lista de Inventario:

- Ritmo = piezas vendidas en los últimos `DIAS_DE_RITMO` (30) días.
- Con menos de `VENDIDAS_MINIMAS` (2) piezas no hay ritmo que creerle.
- «Se va a acabar»: con ese ritmo, lo que hay alcanza para menos de
  `DIAS_PARA_ACABARSE` días (14 = las `SEMANAS_DE_ALERTA` de Analítica).
- «Se acabó y se vende»: hay 0 o menos y sí se vendió en esos días.

Conjuntos (Pants 3pz, chamarra armada): la Libreta anota la venta con el
SKU del conjunto, pero las existencias que bajan son las de sus piezas
(`conjunto_service.descomponer`). `repartir_conjuntos` le pasa a cada pieza
lo vendido como conjunto (cantidad × piezas de la receta, en la misma talla)
para que su ritmo sea el real. De un grupo de alternativas cuenta la que más
hay en esa talla, la misma que mueve la venta. La pieza que «queda» (cantidad
negativa, el pants suelto de la chamarra) no se cuenta: entra, no sale.

Lo puro (`Ritmo`, `ritmo_de_fila`, `poner_datos_de_venta`,
`repartir_conjuntos`) no sabe de base.
`CacheVentas` guarda lo leído unos minutos: la pestaña se refresca seguido y
la Libreta se lee **una vez cada `MINUTOS_CACHE` minutos como máximo**. Si
leerla falla, la pantalla sigue sin ese dato: nunca truena.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, MutableMapping

from pos_uniformes.services.analitica_tablero_service import DIAS_DE_RITMO, SEMANAS_DE_ALERTA, VENDIDAS_MINIMAS
from pos_uniformes.services.inventario_existencia_service import es_fila_virtual

logger = logging.getLogger(__name__)

#: Alcanza para menos de estos días → «Se va a acabar». El mismo umbral que
#: Analítica (2 semanas): da tiempo de pedir antes de quedarse en cero.
DIAS_PARA_ACABARSE = int(SEMANAS_DE_ALERTA * 7)

#: Cuánto se guarda lo leído de la Libreta antes de volver a leerlo.
MINUTOS_CACHE = 5

#: Llaves que se le ponen a cada fila del snapshot (las lee la ficha y las tarjetas).
LLAVE_VENDIDAS = "vendidas_ritmo"
LLAVE_PEDIDAS = "pedidas_demanda"

SE_VA_A_ACABAR = "se_va_a_acabar"
SE_ACABO_Y_SE_VENDE = "se_acabo_y_se_vende"


def _entero(valor: object) -> int:
    try:
        return int(valor or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class Ritmo:
    vendidas: int  # piezas en los últimos `dias` días
    existencia: int
    dias: int = DIAS_DE_RITMO

    @property
    def por_dia(self) -> float:
        return self.vendidas / self.dias if self.dias > 0 else 0.0

    @property
    def por_semana(self) -> float:
        return self.por_dia * 7

    @property
    def se_vende(self) -> bool:
        return self.vendidas >= VENDIDAS_MINIMAS

    @property
    def dias_alcanza(self) -> float | None:
        """Días que alcanza lo que hay; 0 si ya no hay; None si no se vende."""
        if self.existencia <= 0:
            return 0.0
        if self.por_dia <= 0:
            return None
        return self.existencia / self.por_dia

    @property
    def estado(self) -> str | None:
        if not self.se_vende:
            return None
        if self.existencia <= 0:
            return SE_ACABO_Y_SE_VENDE
        alcanza = self.dias_alcanza
        if alcanza is not None and alcanza < DIAS_PARA_ACABARSE:
            return SE_VA_A_ACABAR
        return None

    def texto_venta(self) -> str:
        """«Se vende ~3 por semana», «Se vendieron 2 en 30 días», «Sin ventas en 30 días»."""
        if self.vendidas <= 0:
            return f"Sin ventas en {self.dias} días"
        if self.por_semana >= 1 and self.se_vende:
            return f"Se vende ~{round(self.por_semana)} por semana"
        if self.vendidas == 1:
            return f"Se vendió 1 en {self.dias} días"
        return f"Se vendieron {self.vendidas} en {self.dias} días"

    def texto_alcanza(self) -> str:
        """«ya no hay», «alcanza para 5 días», «alcanza para ~3 semanas»; vacío si no se vende."""
        if self.existencia <= 0:
            return "ya no hay" if self.vendidas > 0 else ""
        alcanza = self.dias_alcanza
        if alcanza is None or not self.se_vende:
            return ""
        if alcanza < 1:
            return "alcanza para menos de un día"
        if alcanza < DIAS_PARA_ACABARSE:
            dias = int(alcanza)
            return f"alcanza para {dias} día" if dias == 1 else f"alcanza para {dias} días"
        if alcanza > 90:
            return "alcanza para más de 3 meses"
        return f"alcanza para ~{round(alcanza / 7)} semanas"

    def texto(self) -> str:
        """La línea de la ficha: «Se vende ~3 por semana · alcanza para 5 días»."""
        alcanza = self.texto_alcanza()
        return f"{self.texto_venta()} · {alcanza}" if alcanza else self.texto_venta()


def ritmo_de_fila(fila: Mapping[str, object]) -> Ritmo | None:
    """El ritmo de una talla; None si no hay dato de ventas o es un conjunto."""
    if LLAVE_VENDIDAS not in fila or es_fila_virtual(fila):
        return None
    return Ritmo(_entero(fila.get(LLAVE_VENDIDAS)), _entero(fila.get("stock_actual")))


def estado_de_fila(fila: Mapping[str, object]) -> str | None:
    """SE_VA_A_ACABAR, SE_ACABO_Y_SE_VENDE o None. Las desactivadas no cuentan."""
    if not bool(fila.get("variante_activa", True)):
        return None
    ritmo = ritmo_de_fila(fila)
    return ritmo.estado if ritmo else None


def pedidas_de_fila(fila: Mapping[str, object]) -> int:
    return _entero(fila.get(LLAVE_PEDIDAS))


def poner_datos_de_venta(
    filas: Iterable[MutableMapping[str, object]],
    vendidas: Mapping[str, int] | None,
    pedidas: Mapping[str, int] | None,
) -> None:
    """Escribe en cada fila sus vendidas (30 días) y cuántas veces la pidieron.

    Sin dato de ventas (la Libreta no respondió) la llave se quita: así la
    ficha no dice «Sin ventas» cuando en realidad no se sabe.
    """
    for fila in filas:
        sku = str(fila.get("sku") or "")
        if vendidas is None:
            fila.pop(LLAVE_VENDIDAS, None)
        else:
            fila[LLAVE_VENDIDAS] = _entero(vendidas.get(sku))
        if pedidas:
            fila[LLAVE_PEDIDAS] = _entero(pedidas.get(sku))
        else:
            fila.pop(LLAVE_PEDIDAS, None)


class CacheVentas:
    """Guarda lo leído `segundos`; si leer falla, sigue con lo último (o nada).

    `cargar` es la consulta (una sola). Un fallo también cuenta como lectura:
    no se reintenta en cada refresco y la pantalla no se alenta.
    """

    def __init__(
        self,
        cargar: Callable[[], Mapping[str, int]],
        *,
        segundos: float = MINUTOS_CACHE * 60,
        reloj: Callable[[], float] = time.monotonic,
        nombre: str = "ventas",
    ) -> None:
        self.cargar = cargar
        self.segundos = segundos
        self.reloj = reloj
        self.nombre = nombre
        self._datos: dict[str, int] | None = None
        self._momento: float | None = None
        self.lecturas = 0

    def obtener(self) -> dict[str, int] | None:
        """Lo vigente; None si nunca se pudo leer."""
        ahora = self.reloj()
        if self._momento is not None and ahora - self._momento < self.segundos:
            return self._datos
        self._momento = ahora
        self.lecturas += 1
        try:
            self._datos = {str(k): _entero(v) for k, v in dict(self.cargar() or {}).items()}
        except Exception:  # noqa: BLE001 — sin el dato, la pantalla sigue
            logger.warning("Inventario: no se pudo leer %s; sigue sin ese dato.", self.nombre, exc_info=True)
        return self._datos

    def invalidar(self) -> None:
        self._momento = None


def repartir_conjuntos(
    vendidas: Mapping[str, int], recetas: Mapping[str, Iterable[tuple[str, int]]]
) -> dict[str, int]:
    """A cada pieza, además de lo suyo, lo vendido como conjunto (cantidad × piezas).

    `recetas` = {sku del conjunto (una talla): [(sku de la pieza, piezas que lleva)]}.
    El SKU del conjunto se queda con lo suyo (su fila es virtual y no se mide).
    """
    salida = {str(sku): _entero(n) for sku, n in vendidas.items()}
    for sku_conjunto, piezas in recetas.items():
        vendidas_conjunto = _entero(vendidas.get(sku_conjunto))
        if vendidas_conjunto <= 0:
            continue
        for sku_pieza, cantidad in piezas:
            if _entero(cantidad) <= 0 or not sku_pieza:
                continue
            salida[sku_pieza] = salida.get(sku_pieza, 0) + vendidas_conjunto * _entero(cantidad)
    return salida


def cargar_recetas_por_sku(session) -> dict[str, list[tuple[str, int]]]:
    """{SKU de cada talla de conjunto: [(SKU de la pieza en esa talla, cantidad)]} en dos consultas."""
    from sqlalchemy import select

    from pos_uniformes.database.models import ConjuntoComponente, Variante
    from pos_uniformes.services.conjunto_service import _norm_talla, por_grupos

    componentes = list(session.scalars(select(ConjuntoComponente)).all())
    if not componentes:
        return {}
    productos = {int(c.conjunto_id) for c in componentes} | {int(c.componente_id) for c in componentes}
    # Por producto y talla, la primera variante activa (como `_variantes_por_talla`).
    por_talla: dict[int, dict[str, tuple[str, int]]] = {}
    filas = session.execute(
        select(Variante.producto_id, Variante.talla, Variante.sku, Variante.stock_actual)
        .where(Variante.producto_id.in_(sorted(productos)), Variante.activo == True)  # noqa: E712
        .order_by(Variante.id)
    ).all()
    for producto_id, talla, sku, stock in filas:
        por_talla.setdefault(int(producto_id), {}).setdefault(_norm_talla(talla), (str(sku), _entero(stock)))
    recetas: dict[int, list] = {}
    for c in componentes:
        recetas.setdefault(int(c.conjunto_id), []).append(c)
    salida: dict[str, list[tuple[str, int]]] = {}
    for conjunto_id, receta in recetas.items():
        for talla, (sku_conjunto, _stock) in por_talla.get(conjunto_id, {}).items():
            piezas: list[tuple[str, int]] = []
            for grupo in por_grupos(receta):
                if grupo[0].cantidad <= 0:
                    continue
                candidatas = [
                    (por_talla[int(c.componente_id)][talla], int(c.cantidad))
                    for c in grupo
                    if talla in por_talla.get(int(c.componente_id), {})
                ]
                if candidatas:
                    (sku_pieza, _), cantidad = max(candidatas, key=lambda par: par[0][1])
                    piezas.append((sku_pieza, cantidad))
            if piezas:
                salida[sku_conjunto] = piezas
    return salida


def cargar_vendidas() -> dict[str, int]:
    """Lo vendido por SKU en la Libreta en los últimos `DIAS_DE_RITMO` días, con los conjuntos repartidos.

    Una consulta a la Libreta y dos a las recetas, cada `MINUTOS_CACHE` minutos
    como máximo (la llama `CacheVentas`). Si las recetas fallan, se usa lo
    vendido tal cual.
    """
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.analitica_tablero_service import vendidas_por_sku

    with get_session() as session:
        vendidas = vendidas_por_sku(session)
        if not vendidas:
            return vendidas
        try:
            recetas = cargar_recetas_por_sku(session)
        except Exception:  # noqa: BLE001 — sin recetas, el ritmo sale sin conjuntos
            logger.warning("Inventario: no se pudieron leer las recetas de conjuntos.", exc_info=True)
            return vendidas
        return repartir_conjuntos(vendidas, recetas)
