"""Productos artificiales (catálogo, fase 3): Pants 3pz y Chamarra.

Daniel (2026-09-21): "un pants 3pz no es más que un 2pz y una playera, y la
chamarra es una que le quito a un pants 2pz". No tienen montón propio en el
estante: conservan su SKU, su precio y su etiqueta, pero

- **venderlos mueve sus piezas**: 3pz → −1 Pants 2pz, −1 Playera; Chamarra →
  −1 Pants 2pz, +1 Pants Suelto (el que quedó). Misma escuela, misma talla.
- **su stock se calcula**: 3pz = min(2pz, playera); Chamarra = 2pz. Se guarda
  en `variante.stock_actual` con un movimiento `derivado:` cada vez que una
  pieza se mueve, para que kiosko, celular y catálogo lo lean como siempre.

La receta vive en `conjunto_componente` (cantidad > 0 se consume, < 0 queda).
`InventarioService.registrar_movimiento` llama aquí: un movimiento sobre un
conjunto con receta se descompone; un movimiento sobre una pieza recalcula los
conjuntos que la usan. Ver Obsidian 38 §5b.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from pos_uniformes.database.models import (
    ConjuntoComponente,
    Producto,
    TipoMovimientoInventario,
    Variante,
)

logger = logging.getLogger(__name__)

TIPOS_CONJUNTO = {"Pants 3pz", "Chamarra"}
PREFIJO_DERIVADO = "derivado:"

# Qué piezas (tipo de pieza) arma cada conjunto y con qué signo.
RECETAS_POR_TIPO = {
    "Pants 3pz": (("Pants 2pz", 1), ("Playera", 1)),
    "Chamarra": (("Pants 2pz", 1), ("Pants Suelto", -1)),
}


def _tipo_pieza(p: Producto) -> str:
    return str(p.tipo_pieza.nombre if p.tipo_pieza is not None else "").strip()


def es_conjunto(producto: Producto) -> bool:
    return _tipo_pieza(producto) in TIPOS_CONJUNTO


def receta_de(session: Session, conjunto_id: int) -> list[ConjuntoComponente]:
    return list(
        session.scalars(
            select(ConjuntoComponente)
            .options(joinedload(ConjuntoComponente.componente))
            .where(ConjuntoComponente.conjunto_id == int(conjunto_id))
            .order_by(ConjuntoComponente.cantidad.desc(), ConjuntoComponente.id)
        ).all()
    )


def receta_texto(session: Session, conjunto_id: int) -> str:
    """'se arma de Pants 2pz X + Playera Y' / 'sale de Pants 2pz X, deja Pants Suelto Z'."""
    receta = receta_de(session, conjunto_id)
    if not receta:
        return ""
    consume = [c.componente.nombre for c in receta if c.cantidad > 0]
    deja = [c.componente.nombre for c in receta if c.cantidad < 0]
    partes = []
    if consume:
        partes.append(("sale de " if deja else "se arma de ") + " + ".join(consume))
    if deja:
        partes.append("deja " + " + ".join(deja))
    return ", ".join(partes)


def definir_receta(session: Session, conjunto_id: int, componentes: list[tuple[int, int]], *, creado_por: str = "SYSTEM") -> list[ConjuntoComponente]:
    """Reemplaza la receta del conjunto. `componentes` = [(producto_id, cantidad)]."""
    conjunto = session.get(Producto, int(conjunto_id))
    if conjunto is None:
        raise ValueError("No existe el conjunto.")
    if not es_conjunto(conjunto):
        raise ValueError(f"{conjunto.nombre} no es un conjunto (Pants 3pz o Chamarra).")
    for pid, cant in componentes:
        if int(pid) == conjunto.id:
            raise ValueError("Un conjunto no puede ser pieza de sí mismo.")
        if int(cant) == 0:
            raise ValueError("La cantidad de una pieza no puede ser cero.")
        comp = session.get(Producto, int(pid))
        if comp is None:
            raise ValueError("No existe alguna de las piezas.")
        if es_conjunto(comp):
            raise ValueError(f"{comp.nombre} es otro conjunto; las piezas deben ser prendas reales.")
    for viejo in receta_de(session, conjunto.id):
        session.delete(viejo)
    session.flush()
    nuevos = [ConjuntoComponente(conjunto_id=conjunto.id, componente_id=int(pid), cantidad=int(cant)) for pid, cant in componentes]
    session.add_all(nuevos)
    session.flush()
    sincronizar_conjunto(session, conjunto.id, creado_por=creado_por)
    return nuevos


def quitar_receta(session: Session, conjunto_id: int) -> None:
    for viejo in receta_de(session, conjunto_id):
        session.delete(viejo)
    session.flush()


# ------------------------------------------------------------------ propuesta

def _candidatas(session: Session, conjunto: Producto) -> list[Producto]:
    """Prendas entre las que se busca la receta: las piezas del uniforme de la
    escuela si lo tiene armado (ahí está la polo blanca general si aplica); si
    no, los productos activos de la escuela."""
    from pos_uniformes.database.models import Uniforme, UniformePieza

    if conjunto.escuela_id is None:
        # Un conjunto general ("Chamarra Liso Azul Marino") se arma de generales
        # con el mismo nombre sin el tipo de pieza ("Pants 2pz Liso Azul Marino").
        raiz = _raiz(conjunto.nombre)
        if not raiz:
            return []
        generales = session.scalars(
            select(Producto).options(joinedload(Producto.tipo_pieza))
            .where(Producto.escuela_id == None, Producto.activo == True)  # noqa: E711, E712
        ).unique().all()
        return [p for p in generales if _raiz(p.nombre) == raiz]
    uni = session.scalar(
        select(Uniforme).where(Uniforme.escuela_id == conjunto.escuela_id, Uniforme.activo == True)  # noqa: E712
        .order_by(Uniforme.id)
    )
    if uni is not None:
        return list(
            session.scalars(
                select(Producto)
                .join(UniformePieza, UniformePieza.producto_id == Producto.id)
                .options(joinedload(Producto.tipo_pieza))
                .where(UniformePieza.uniforme_id == uni.id, UniformePieza.activo == True, Producto.activo == True)  # noqa: E712
                .order_by(UniformePieza.orden)
            ).unique().all()
        )
    return list(
        session.scalars(
            select(Producto)
            .options(joinedload(Producto.tipo_pieza))
            .where(Producto.escuela_id == conjunto.escuela_id, Producto.activo == True)  # noqa: E712
            .order_by(Producto.nombre)
        ).unique().all()
    )


_PALABRAS_PIEZA = ("pants 3pz", "pants 2pz", "pants suelto", "chamarra", "playera")


def _raiz(nombre: str) -> str:
    """'Chamarra Liso Azul Marino' → 'liso azul marino' (sin la palabra de la pieza)."""
    n = " ".join(str(nombre or "").lower().split())
    for palabra in _PALABRAS_PIEZA:
        n = n.replace(palabra, "")
    return " ".join(n.split())


def _desempatar(tipo: str, del_tipo: list[Producto]) -> Producto | None:
    """Entre dos playeras de la escuela (Polo y Deportiva), la del 3pz es la
    deportiva. Cualquier otro empate lo decide Daniel."""
    if tipo == "Playera":
        deportivas = [p for p in del_tipo if "deportiv" in p.nombre.lower()]
        if len(deportivas) == 1:
            return deportivas[0]
    return None


def proponer_receta(session: Session, conjunto: Producto) -> dict:
    """{"componentes": [(producto_id, cantidad)], "faltan": [...tipos], "ambiguas": {tipo: [nombres]}}.
    Solo propone cuando hay exactamente UNA prenda de cada tipo que pide la receta."""
    plantilla = RECETAS_POR_TIPO.get(_tipo_pieza(conjunto))
    if plantilla is None:
        return {"componentes": [], "faltan": [], "ambiguas": {}}
    candidatas = [p for p in _candidatas(session, conjunto) if p.id != conjunto.id]
    componentes, faltan, ambiguas = [], [], {}
    for tipo, cantidad in plantilla:
        del_tipo = [p for p in candidatas if _tipo_pieza(p) == tipo]
        elegida = del_tipo[0] if len(del_tipo) == 1 else _desempatar(tipo, del_tipo)
        if not del_tipo:
            faltan.append(tipo)
        elif elegida is None:
            ambiguas[tipo] = [p.nombre for p in del_tipo]
        else:
            componentes.append((int(elegida.id), int(cantidad)))
    if faltan or ambiguas:
        componentes = []
    return {"componentes": componentes, "faltan": faltan, "ambiguas": ambiguas}


def conjuntos_activos(session: Session) -> list[Producto]:
    from pos_uniformes.database.models import TipoPieza

    return list(
        session.scalars(
            select(Producto)
            .join(TipoPieza, TipoPieza.id == Producto.tipo_pieza_id)
            .options(joinedload(Producto.tipo_pieza), joinedload(Producto.escuela))
            .where(TipoPieza.nombre.in_(TIPOS_CONJUNTO), Producto.activo == True)  # noqa: E712
            .order_by(Producto.escuela_id, Producto.nombre)
        ).unique().all()
    )


def resumen(session: Session) -> list[dict]:
    """Una fila por conjunto activo: su receta actual o la propuesta."""
    filas = []
    for c in conjuntos_activos(session):
        actual = receta_de(session, c.id)
        prop = proponer_receta(session, c) if not actual else None
        filas.append({
            "conjunto_id": int(c.id), "nombre": str(c.nombre), "tipo": _tipo_pieza(c),
            "escuela": str(c.escuela.nombre) if c.escuela is not None else "",
            "receta": receta_texto(session, c.id),
            "propuesta": prop,
            "tallas_sin_pieza": tallas_sin_pieza(session, c.id) if actual else [],
        })
    return filas


# --------------------------------------------------------------- stock derivado

def _norm_talla(t: str) -> str:
    return str(t or "").strip().upper()


def _variantes_por_talla(session: Session, producto_id: int) -> dict[str, Variante]:
    vs = session.scalars(
        select(Variante).where(Variante.producto_id == int(producto_id), Variante.activo == True)  # noqa: E712
        .order_by(Variante.id)
    ).all()
    out: dict[str, Variante] = {}
    for v in vs:
        out.setdefault(_norm_talla(v.talla), v)
    return out


def stock_derivado(session: Session, variante_conjunto: Variante, receta: list[ConjuntoComponente] | None = None) -> int | None:
    """min(stock de cada pieza que se consume // cantidad) en la misma talla;
    None si el conjunto no tiene receta o alguna pieza no tiene esa talla."""
    receta = receta if receta is not None else receta_de(session, variante_conjunto.producto_id)
    consumidos = [c for c in receta if c.cantidad > 0]
    if not consumidos:
        return None
    talla = _norm_talla(variante_conjunto.talla)
    posibles = []
    for c in consumidos:
        v = _variantes_por_talla(session, c.componente_id).get(talla)
        if v is None:
            return None
        posibles.append(int(v.stock_actual) // int(c.cantidad))
    return min(posibles)


def variantes_pieza_de(session: Session, variante_conjunto: Variante) -> list[Variante]:
    """Las tallas de las piezas que mueve esta talla del conjunto ([] si no es conjunto con receta)."""
    receta = receta_de(session, variante_conjunto.producto_id)
    if not receta:
        return []
    talla = _norm_talla(variante_conjunto.talla)
    out = []
    for c in receta:
        v = _variantes_por_talla(session, c.componente_id).get(talla)
        if v is not None:
            out.append(v)
    return out


def tallas_sin_pieza(session: Session, conjunto_id: int) -> list[str]:
    receta = receta_de(session, conjunto_id)
    if not receta:
        return []
    return [
        v.talla
        for v in session.scalars(select(Variante).where(Variante.producto_id == int(conjunto_id), Variante.activo == True)).all()  # noqa: E712
        if stock_derivado(session, v, receta) is None
    ]


def sincronizar_conjunto(session: Session, conjunto_id: int, *, tallas: set[str] | None = None, creado_por: str = "SYSTEM") -> int:
    """Pone el stock de cada talla del conjunto en su valor calculado (con un
    movimiento `derivado:` si cambia). Devuelve cuántas tallas cambiaron."""
    from pos_uniformes.services.inventario_service import InventarioService

    receta = receta_de(session, conjunto_id)
    if not receta:
        return 0
    cambios = 0
    for v in session.scalars(select(Variante).where(Variante.producto_id == int(conjunto_id), Variante.activo == True)).all():  # noqa: E712
        if tallas is not None and _norm_talla(v.talla) not in tallas:
            continue
        objetivo = stock_derivado(session, v, receta)
        if objetivo is None or objetivo == int(v.stock_actual):
            continue
        delta = objetivo - int(v.stock_actual)
        InventarioService.registrar_movimiento(
            session, v,
            TipoMovimientoInventario.AJUSTE_ENTRADA if delta > 0 else TipoMovimientoInventario.AJUSTE_SALIDA,
            delta, referencia=f"{PREFIJO_DERIVADO}{int(conjunto_id)}",
            observacion="Stock calculado de sus piezas", creado_por=creado_por, allow_negative_stock=True,
        )
        cambios += 1
    return cambios


def sincronizar_por_componente(session: Session, variante_pieza: Variante, *, creado_por: str = "SYSTEM") -> int:
    """Una pieza se movió: recalcula la misma talla de los conjuntos que la usan."""
    conjuntos = session.scalars(
        select(ConjuntoComponente.conjunto_id).where(ConjuntoComponente.componente_id == int(variante_pieza.producto_id))
    ).all()
    cambios = 0
    for cid in set(conjuntos):
        cambios += sincronizar_conjunto(session, cid, tallas={_norm_talla(variante_pieza.talla)}, creado_por=creado_por)
    return cambios


def sincronizar_todo(session: Session, *, creado_por: str = "SYSTEM") -> int:
    return sum(sincronizar_conjunto(session, c.id, creado_por=creado_por) for c in conjuntos_activos(session))


# ------------------------------------------------------------------- la venta

def descomponer(
    session: Session,
    variante_conjunto: Variante,
    tipo_movimiento: TipoMovimientoInventario,
    cantidad: int,
    *,
    receta: list[ConjuntoComponente],
    referencia: str | None,
    observacion: str | None,
    creado_por: str,
) -> list:
    """Aplica a las piezas el movimiento que se pidió sobre el conjunto:
    vender 1 Pants 3pz (cantidad −1) = −1 Pants 2pz y −1 Playera; vender 1
    Chamarra = −1 Pants 2pz y +1 Pants Suelto (la pieza que "queda" va con el
    signo contrario, como AJUSTE). Una pieza sin esa talla se anota en el log y
    se sigue: la venta vale más que el número. Al final el stock del conjunto
    se recalcula. Devuelve los movimientos de las piezas."""
    from pos_uniformes.services.inventario_service import InventarioService

    talla = _norm_talla(variante_conjunto.talla)
    nombre = variante_conjunto.producto.nombre if variante_conjunto.producto is not None else variante_conjunto.sku
    movimientos = []
    for c in receta:
        v = _variantes_por_talla(session, c.componente_id).get(talla)
        if v is None:
            logger.warning("Conjunto %s talla %s: la pieza %s no tiene esa talla; no se movió", nombre, variante_conjunto.talla, c.componente_id)
            continue
        delta = int(cantidad) * int(c.cantidad)
        if c.cantidad > 0:
            tipo = tipo_movimiento
        else:
            tipo = TipoMovimientoInventario.AJUSTE_ENTRADA if delta > 0 else TipoMovimientoInventario.AJUSTE_SALIDA
        nota = f"{observacion or ''} · por {nombre} {variante_conjunto.talla}".strip(" ·")
        movimientos.append(
            InventarioService.registrar_movimiento(
                session, v, tipo, delta, referencia=referencia, observacion=nota,
                creado_por=creado_por, allow_negative_stock=True,
            )
        )
    sincronizar_conjunto(session, variante_conjunto.producto_id, tallas={talla}, creado_por=creado_por)
    return movimientos
