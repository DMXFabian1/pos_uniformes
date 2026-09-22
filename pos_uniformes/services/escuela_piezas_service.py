"""Qué prendas tiene cada escuela, y cómo se llama cuando tiene dos niveles.

El panel armaba esta matriz con su propio SQL, y ese SQL se quedó en las
**ligas** de siempre (`catalog_school_product_link`). El POS ya no manda ahí:
desde la fase 2 del catálogo, si la escuela tiene su uniforme armado, sus
prendas generales son las piezas del uniforme — `catalog_school_link_service`
lo resuelve. Hoy las dos ramas coinciden porque las ligas se mantienen en
espejo; el día que se retiren, quien pregunte por su cuenta se queda ciego.

Por eso la pregunta "qué piezas tiene esta escuela" se contesta aquí, una vez.
Ver la nota `39 - Brújula`.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    Escuela,
    NivelEducativo,
    Producto,
    TipoPieza,
)
from pos_uniformes.services import catalog_school_link_service
from pos_uniformes.utils.text_normalization import normalize_text_unicode


def _niveles_por_escuela(session: Session) -> dict[int, list[tuple[int, str]]]:
    """Los niveles de cada escuela, tal como los dicen sus propias prendas.

    Una escuela "tiene" un nivel si tiene productos suyos de ese nivel; no hay
    catálogo de niveles por escuela aparte."""
    filas = session.execute(
        select(Producto.escuela_id, NivelEducativo.id, NivelEducativo.nombre)
        .join(Escuela, Escuela.id == Producto.escuela_id)
        .join(NivelEducativo, NivelEducativo.id == Producto.nivel_educativo_id)
        .where(Producto.activo.is_(True), Escuela.activo.is_(True))
        .distinct()
    ).all()
    por_escuela: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for escuela_id, nivel_id, nivel_nombre in filas:
        por_escuela[int(escuela_id)].append((int(nivel_id), str(nivel_nombre)))
    for niveles in por_escuela.values():
        niveles.sort(key=lambda n: orden_alfabetico(n[1]))
    return dict(por_escuela)


def orden_alfabetico(nombre: str) -> str:
    """Ordena como lo hace la base: "Álvaro" va entre "Alta" y "Amado", no al
    final. Sin esto, la lista de escuelas sale en un orden en el panel y en
    otro en el POS, y nadie sabe cuál es el bueno."""
    return normalize_text_unicode(nombre)


def escuelas_multinivel(session: Session) -> set[int]:
    """Las que atienden más de un nivel: su nombre solo no alcanza para decir
    de cuál se está hablando."""
    return {
        escuela_id
        for escuela_id, niveles in _niveles_por_escuela(session).items()
        if len(niveles) > 1
    }


def nombre_visible(escuela_nombre: str, nivel_nombre: str, *, multinivel: bool) -> str:
    """"Álvaro Obregón" cuando solo tiene un nivel; "Álvaro Obregón Primaria"
    cuando hay que distinguir."""
    return f"{escuela_nombre} {nivel_nombre}" if multinivel else escuela_nombre


def escuelas_con_niveles(session: Session) -> list[dict]:
    """Una entrada por escuela y nivel, ya con el nombre que se le enseña."""
    niveles = _niveles_por_escuela(session)
    nombres = dict(
        session.execute(
            select(Escuela.id, Escuela.nombre).where(Escuela.activo.is_(True))
        ).all()
    )
    multinivel = {eid for eid, ns in niveles.items() if len(ns) > 1}

    entradas = []
    for escuela_id, sus_niveles in niveles.items():
        escuela_nombre = str(nombres.get(escuela_id, ""))
        for nivel_id, nivel_nombre in sus_niveles:
            entradas.append(
                {
                    "escuela_id": escuela_id,
                    "escuela_nombre": escuela_nombre,
                    "nivel_id": nivel_id,
                    "nivel_nombre": nivel_nombre,
                    "display_name": nombre_visible(
                        escuela_nombre, nivel_nombre, multinivel=escuela_id in multinivel
                    ),
                }
            )
    entradas.sort(
        key=lambda e: (orden_alfabetico(e["nivel_nombre"]), orden_alfabetico(e["escuela_nombre"]))
    )
    return entradas


def matriz_de_piezas(session: Session) -> list[tuple[int, str, str, int]]:
    """Cuántas prendas distintas tiene cada escuela de cada tipo de pieza.

    Devuelve `(escuela_id, nivel_nombre, tipo_pieza_nombre, cuántas)`.

    Cuenta las prendas propias de la escuela y también las generales que le
    correspondan (uniforme armado, o ligas si todavía no lo está). Una prenda
    general vale para **todos** los niveles de la escuela: un pants liso sirve
    igual en primaria que en secundaria."""
    piezas_nombre = dict(session.execute(select(TipoPieza.id, TipoPieza.nombre)).all())
    niveles = _niveles_por_escuela(session)

    # (escuela_id, nivel_nombre, pieza_nombre) -> {producto_id}
    celdas: dict[tuple[int, str, str], set[int]] = defaultdict(set)

    # 1. Las prendas propias de cada escuela.
    propias = session.execute(
        select(
            Producto.escuela_id,
            NivelEducativo.nombre,
            Producto.tipo_pieza_id,
            Producto.id,
        )
        .join(Escuela, Escuela.id == Producto.escuela_id)
        .join(NivelEducativo, NivelEducativo.id == Producto.nivel_educativo_id)
        .where(Producto.activo.is_(True), Escuela.activo.is_(True))
    ).all()
    for escuela_id, nivel_nombre, pieza_id, producto_id in propias:
        pieza = piezas_nombre.get(pieza_id)
        if pieza is None:
            continue
        celdas[(int(escuela_id), str(nivel_nombre), str(pieza))].add(int(producto_id))

    # 2. Las generales que le tocan, según el POS (uniforme armado o ligas).
    generales = catalog_school_link_service.list_all_active_links(session)
    ids = {int(f["producto_id"]) for f in generales}
    piezas_de_producto = {}
    if ids:
        piezas_de_producto = dict(
            session.execute(
                select(Producto.id, Producto.tipo_pieza_id).where(
                    Producto.id.in_(ids), Producto.activo.is_(True)
                )
            ).all()
        )
    for fila in generales:
        escuela_id = int(fila["escuela_id"])
        producto_id = int(fila["producto_id"])
        pieza_id = piezas_de_producto.get(producto_id)
        pieza = piezas_nombre.get(pieza_id) if pieza_id is not None else None
        if pieza is None:
            continue  # prenda dada de baja, o sin tipo de pieza
        for _nivel_id, nivel_nombre in niveles.get(escuela_id, []):
            celdas[(escuela_id, nivel_nombre, str(pieza))].add(producto_id)

    return [
        (escuela_id, nivel_nombre, pieza, len(productos))
        for (escuela_id, nivel_nombre, pieza), productos in celdas.items()
    ]
