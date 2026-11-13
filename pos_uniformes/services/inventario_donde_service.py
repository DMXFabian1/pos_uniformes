"""«Dónde» está lo que hay de una talla, en palabras de la tienda (tanda 2, 2026-11-13).

Junta en una sola columna lo que antes eran «Piso» y «Almacén».

De dónde sale cada número (`inventory_snapshot_service`):

- **Bodega**: lo guardado en cajas de Bodega en cualquier rack que no sea PISO.
- **Piso**: lo guardado en cajas del rack PISO.
- **Tienda**: el resto del total (total − bodega − piso), lo que está a la
  venta sin caja asignada. Es el lugar «de siempre», por eso la columna no lo
  repite.

Criterio de la columna (corta, para que quepa a 1366 px):

- Con algo en cajas, solo lo de cajas: «Bodega 6 · Piso 2», «Bodega 6», «Piso 2».
- Sin nada en cajas y con existencia: «Tienda».
- Sin nada (cero o negativo) o un conjunto armado de piezas: «—».

El reparto completo («Tienda 4 · Bodega 6 · Piso 2») va en el texto largo,
para el aviso al pasar el mouse y la ficha. Si en cajas hay más de lo que dice
el total (se vendió sin sacarlo de la caja), el texto largo lo avisa.
"""

from __future__ import annotations

from dataclasses import dataclass

SEPARADOR = " · "
VACIO = "—"
TIENDA = "Tienda"


@dataclass(frozen=True)
class Reparto:
    tienda: int
    bodega: int
    piso: int
    descuadre: int  # cuánto hay en cajas de más contra el total (0 si cuadra)


def repartir(total: int, bodega: int = 0, piso: int = 0) -> Reparto:
    total = int(total or 0)
    bodega = max(int(bodega or 0), 0)
    piso = max(int(piso or 0), 0)
    en_cajas = bodega + piso
    return Reparto(
        tienda=max(total - en_cajas, 0),
        bodega=bodega,
        piso=piso,
        descuadre=max(en_cajas - max(total, 0), 0),
    )


def texto_donde(total: int, bodega: int = 0, piso: int = 0, *, conjunto: bool = False) -> str:
    """Texto corto de la columna «Dónde»."""
    if conjunto:
        return VACIO
    reparto = repartir(total, bodega, piso)
    partes = _partes(("Bodega", reparto.bodega), ("Piso", reparto.piso))
    if partes:
        return SEPARADOR.join(partes)
    return TIENDA if int(total or 0) > 0 else VACIO


def texto_donde_completo(total: int, bodega: int = 0, piso: int = 0, *, conjunto: bool = False) -> str:
    """Reparto completo para el aviso y la ficha: «Tienda 4 · Bodega 6 · Piso 2»."""
    if conjunto:
        return "Se arma con sus piezas: no se guarda aparte."
    reparto = repartir(total, bodega, piso)
    partes = _partes((TIENDA, reparto.tienda), ("Bodega", reparto.bodega), ("Piso", reparto.piso))
    texto = SEPARADOR.join(partes) if partes else "No hay"
    if reparto.descuadre:
        texto += f". Ojo: en cajas hay {reparto.bodega + reparto.piso} y el total dice {int(total or 0)}"
    return texto


def _partes(*lugares: tuple[str, int]) -> list[str]:
    return [f"{nombre} {cantidad}" for nombre, cantidad in lugares if cantidad > 0]
