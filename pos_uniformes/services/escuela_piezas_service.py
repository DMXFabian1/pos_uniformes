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


def productos_por_escuela(session: Session) -> list[tuple[int, int, int, str]]:
    """Qué productos le tocan a cada escuela, nivel por nivel.

    Devuelve `(escuela_id, producto_id, nivel_id, nivel_nombre)`. Son las
    prendas propias de la escuela, más las generales que le correspondan según
    el POS. Una general vale para **todos** los niveles de la escuela: un pants
    liso sirve igual en primaria que en secundaria.

    Es el reparto del que cuelgan la matriz de Piezas, los tarifarios y la
    disponibilidad: si cada uno lo armara por su cuenta, mostrarían catálogos
    distintos de la misma escuela.

    Límite heredado: los niveles de una escuela salen de sus **propias**
    prendas, así que una escuela que solo llevara generales no tendría de dónde
    colgarlas. En la tienda no pasa (toda escuela tiene lo suyo), pero si algún
    día pasa, hay que darle nivel a la escuela en vez de deducirlo."""
    niveles = _niveles_por_escuela(session)
    filas: list[tuple[int, int, int, str]] = []

    propias = session.execute(
        select(Producto.escuela_id, Producto.id, Producto.nivel_educativo_id, NivelEducativo.nombre)
        .join(Escuela, Escuela.id == Producto.escuela_id)
        .join(NivelEducativo, NivelEducativo.id == Producto.nivel_educativo_id)
        .where(Producto.activo.is_(True), Escuela.activo.is_(True))
    ).all()
    for escuela_id, producto_id, nivel_id, nivel_nombre in propias:
        filas.append((int(escuela_id), int(producto_id), int(nivel_id), str(nivel_nombre)))

    generales = catalog_school_link_service.list_all_active_links(session)
    ids = {int(f["producto_id"]) for f in generales}
    vivos = set()
    if ids:
        vivos = {
            int(pid)
            for pid in session.scalars(
                select(Producto.id).where(Producto.id.in_(ids), Producto.activo.is_(True))
            ).all()
        }
    vistos = {(e, p, n) for e, p, n, _ in filas}
    for fila in generales:
        escuela_id = int(fila["escuela_id"])
        producto_id = int(fila["producto_id"])
        if producto_id not in vivos:
            continue  # prenda dada de baja o fundida en otra
        for nivel_id, nivel_nombre in niveles.get(escuela_id, []):
            if (escuela_id, producto_id, nivel_id) in vistos:
                continue
            vistos.add((escuela_id, producto_id, nivel_id))
            filas.append((escuela_id, producto_id, nivel_id, nivel_nombre))

    return filas


def matriz_de_piezas(session: Session) -> list[tuple[int, str, str, int]]:
    """Cuántas prendas distintas tiene cada escuela de cada tipo de pieza.

    Devuelve `(escuela_id, nivel_nombre, tipo_pieza_nombre, cuántas)`.

    Cuenta las prendas propias de la escuela y también las generales que le
    correspondan (uniforme armado, o ligas si todavía no lo está). Una prenda
    general vale para **todos** los niveles de la escuela: un pants liso sirve
    igual en primaria que en secundaria."""
    piezas_nombre = dict(session.execute(select(TipoPieza.id, TipoPieza.nombre)).all())
    pieza_de_producto = dict(
        session.execute(select(Producto.id, Producto.tipo_pieza_id)).all()
    )

    # (escuela_id, nivel_nombre, pieza_nombre) -> {producto_id}
    celdas: dict[tuple[int, str, str], set[int]] = defaultdict(set)
    for escuela_id, producto_id, _nivel_id, nivel_nombre in productos_por_escuela(session):
        pieza = piezas_nombre.get(pieza_de_producto.get(producto_id))
        if pieza is None:
            continue  # prenda sin tipo de pieza
        celdas[(escuela_id, nivel_nombre, str(pieza))].add(producto_id)

    return [
        (escuela_id, nivel_nombre, pieza, len(productos))
        for (escuela_id, nivel_nombre, pieza), productos in celdas.items()
    ]


#: Las columnas del catálogo por escuela, en el orden en que salen.
CATALOGO_COLUMNAS = [
    "escuela_id", "escuela", "nivel", "tipo_pieza",
    "producto_id", "nombre_base",
    "variante_id", "sku", "talla", "color",
    "precio_venta", "stock_actual", "v_activo",
    "stock_bodega", "stock_piso", "stock_minimo",
    "producto_escuela_id", "disp_oculta",
]


def catalogo_por_escuela(session: Session) -> list[tuple]:
    """Cada talla de cada prenda que le toca a cada escuela.

    Es la materia prima de los tarifarios y de la disponibilidad: una fila por
    talla, con su precio, su existencia y cuánto de esa existencia está
    guardada en piso o en cajas. Las prendas sin tallas también salen, con la
    parte de la talla vacía, para que se note que existen y no tienen.

    Las columnas van en `CATALOGO_COLUMNAS`."""
    from pos_uniformes.database.models import Variante
    from pos_uniformes.services import inventario_totales_service

    reparto = productos_por_escuela(session)
    if not reparto:
        return []

    escuelas = dict(session.execute(select(Escuela.id, Escuela.nombre)).all())
    piezas = dict(session.execute(select(TipoPieza.id, TipoPieza.nombre)).all())
    productos = {
        int(pid): (nombre_base, nombre, tipo_pieza_id, escuela_id)
        for pid, nombre_base, nombre, tipo_pieza_id, escuela_id in session.execute(
            select(
                Producto.id,
                Producto.nombre_base,
                Producto.nombre,
                Producto.tipo_pieza_id,
                Producto.escuela_id,
            )
        ).all()
    }

    # Las tallas, con lo guardado en piso y en cajas — la misma cuenta que usan
    # los totales, no una copia.
    bodega_sq = inventario_totales_service.subconsulta_bodega()
    por_producto: dict[int, list] = defaultdict(list)
    for fila in session.execute(
        select(
            Variante.producto_id,
            Variante.id,
            Variante.sku,
            Variante.talla,
            Variante.color,
            Variante.precio_venta,
            Variante.stock_actual,
            Variante.activo,
            bodega_sq.c.bodega,
            bodega_sq.c.piso,
            Variante.stock_minimo,
            Variante.disponibilidad_oculta,
        ).outerjoin(bodega_sq, bodega_sq.c.variante_id == Variante.id)
    ).all():
        por_producto[int(fila[0])].append(fila[1:])

    filas = []
    for escuela_id, producto_id, _nivel_id, nivel_nombre in reparto:
        producto = productos.get(producto_id)
        if producto is None:
            continue
        nombre_base, nombre, tipo_pieza_id, producto_escuela_id = producto
        pieza = piezas.get(tipo_pieza_id)
        if pieza is None:
            continue
        escuela_nombre = str(escuelas.get(escuela_id, ""))
        cabeza = (
            escuela_id, escuela_nombre, str(nivel_nombre), str(pieza),
            producto_id, nombre_base if nombre_base is not None else nombre,
        )
        cola = (
            producto_escuela_id,
        )
        tallas = por_producto.get(producto_id)
        if not tallas:
            filas.append(cabeza + (None, None, None, None, None, None, None, 0, 0, None) + cola + (False,))
            continue
        for (vid, sku, talla, color, precio, stock, activo,
             bodega, piso, minimo, oculta) in tallas:
            filas.append(
                cabeza
                + (
                    int(vid), sku, talla, color, precio, int(stock), bool(activo),
                    int(bodega or 0), int(piso or 0),
                    int(minimo) if minimo is not None else None,
                )
                + cola
                + (bool(oculta),)
            )

    def orden(fila):
        # Como lo ordena la base: por escuela, nivel, pieza, prenda, talla y
        # color, con los acentos donde el castellano los pone y las prendas sin
        # talla al final.
        _eid, escuela, nivel, pieza, _pid, nombre_base = fila[:6]
        talla, color = fila[8], fila[9]
        return (
            orden_alfabetico(escuela),
            orden_alfabetico(nivel),
            orden_alfabetico(pieza),
            orden_alfabetico(nombre_base or ""),
            talla is None,
            orden_alfabetico(talla or ""),
            color is None,
            orden_alfabetico(color or ""),
        )

    filas.sort(key=orden)
    return filas


def escuelas_por_nivel(session: Session) -> dict[str, int]:
    """Cuántas escuelas atiende cada nivel educativo."""
    cuenta: dict[str, int] = defaultdict(set)
    for escuela_id, niveles in _niveles_por_escuela(session).items():
        for _nivel_id, nivel_nombre in niveles:
            cuenta[nivel_nombre].add(escuela_id)
    return {nivel: len(escuelas) for nivel, escuelas in cuenta.items()}
