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


def por_grupos(receta: list[ConjuntoComponente]) -> list[list[ConjuntoComponente]]:
    """Las piezas agrupadas: las que comparten `grupo` son alternativas (vale
    cualquiera). Cada grupo se lleva (o deja) una vez."""
    grupos: dict[tuple[int, bool], list[ConjuntoComponente]] = {}
    for c in receta:
        grupos.setdefault((int(c.grupo), c.cantidad > 0), []).append(c)
    return list(grupos.values())


def receta_texto(session: Session, conjunto_id: int) -> str:
    """'se arma de Pants 2pz X + Playera Y' / 'sale de Pants 2pz X, deja Pants
    Suelto Z'; las alternativas van con 'o' ('Playera H o Playera M')."""
    receta = receta_de(session, conjunto_id)
    if not receta:
        return ""
    grupos = por_grupos(receta)
    consume = [" o ".join(c.componente.nombre for c in g) for g in grupos if g[0].cantidad > 0]
    deja = [" o ".join(c.componente.nombre for c in g) for g in grupos if g[0].cantidad < 0]
    partes = []
    if consume:
        partes.append(("sale de " if deja else "se arma de ") + " + ".join(consume))
    if deja:
        partes.append("deja " + " + ".join(deja))
    return ", ".join(partes)


def definir_receta(session: Session, conjunto_id: int, componentes: list, *, creado_por: str = "SYSTEM") -> list[ConjuntoComponente]:
    """Reemplaza la receta del conjunto. `componentes` = [(producto_id, cantidad)]
    o [(producto_id, cantidad, grupo)]; dos piezas con el mismo grupo son
    alternativas (vale cualquiera de las dos)."""
    componentes = [(c if len(c) == 3 else (c[0], c[1], i)) for i, c in enumerate(componentes)]
    conjunto = session.get(Producto, int(conjunto_id))
    if conjunto is None:
        raise ValueError("No existe el conjunto.")
    if not es_conjunto(conjunto):
        raise ValueError(f"{conjunto.nombre} no es un conjunto (Pants 3pz o Chamarra).")
    for pid, cant, _g in componentes:
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
    nuevos = [
        ConjuntoComponente(conjunto_id=conjunto.id, componente_id=int(pid), cantidad=int(cant), grupo=int(g))
        for pid, cant, g in componentes
    ]
    session.add_all(nuevos)
    session.flush()
    sincronizar_conjunto(session, conjunto.id, creado_por=creado_por)
    return nuevos


def reagrupar_por_tipo_de_pieza(session: Session) -> int:
    """Recalcula el `grupo` de todas las recetas: piezas de distinto tipo van
    en grupos distintos (se llevan todas) y las del mismo tipo quedan juntas
    (alternativas). Lo mismo que hace la migración 4f5a6b7c8d9e, para las
    recetas que se guardaron antes de que existiera la columna."""
    filas = session.scalars(
        select(ConjuntoComponente).options(joinedload(ConjuntoComponente.componente))
        .order_by(ConjuntoComponente.conjunto_id, ConjuntoComponente.id)
    ).unique().all()
    por_conjunto: dict[int, dict[tuple, int]] = {}
    cambios = 0
    for c in filas:
        clave = (int(c.cantidad) > 0, c.componente.tipo_pieza_id)
        vistos = por_conjunto.setdefault(int(c.conjunto_id), {})
        grupo = vistos.setdefault(clave, len(vistos))
        if int(c.grupo) != grupo:
            c.grupo = grupo
            cambios += 1
    session.flush()
    return cambios


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
    propias = list(
        session.scalars(
            select(Producto)
            .options(joinedload(Producto.tipo_pieza))
            .where(Producto.escuela_id == conjunto.escuela_id, Producto.activo == True)  # noqa: E712
            .order_by(Producto.nombre)
        ).unique().all()
    )
    if uni is None:
        return propias
    # Las piezas del uniforme (ahí están las generales que usa la escuela) más
    # sus propias prendas: una recién dada de alta todavía no es pieza.
    del_uniforme = list(
        session.scalars(
            select(Producto)
            .join(UniformePieza, UniformePieza.producto_id == Producto.id)
            .options(joinedload(Producto.tipo_pieza))
            .where(UniformePieza.uniforme_id == uni.id, UniformePieza.activo == True, Producto.activo == True)  # noqa: E712
            .order_by(UniformePieza.orden)
        ).unique().all()
    )
    vistos = {p.id for p in del_uniforme}
    return del_uniforme + [p for p in propias if p.id not in vistos]


_PALABRAS_PIEZA = ("pants 3pz", "pants 2pz", "pants suelto", "chamarra", "playera")


def _raiz(nombre: str) -> str:
    """'Chamarra Liso Azul Marino' → 'liso azul marino' (sin la palabra de la
    pieza). El color va en masculino para que "Chamarra Liso Blanca" y
    "Pants 2pz Liso Blanco" se reconozcan como la misma familia."""
    n = " ".join(str(nombre or "").lower().split())
    for palabra in _PALABRAS_PIEZA:
        n = n.replace(palabra, "")
    palabras = [w[:-1] + "o" if len(w) > 3 and w.endswith("a") and w[:-1] + "o" in _COLORES_MASCULINO else w for w in n.split()]
    return " ".join(palabras)


# Colores que cambian de género según la prenda (chamarra blanca / pants blanco).
_COLORES_MASCULINO = {"blanco", "rojo", "negro", "amarillo", "morado", "gris"}


_SUFIJOS_GENERO = (" h", " m", " hombre", " mujer", " niño", " niña")


def _alternativas(tipo: str, del_tipo: list[Producto]) -> list[Producto]:
    """Dos prendas iguales que solo se distinguen por el género (Playera
    Deportiva **H** / **M** de SABES): valen las dos. Daniel, 2026-09-22:
    "el SABES puede llevar de hombre o de mujer playera deportiva"."""
    if tipo != "Playera" or len(del_tipo) < 2:
        return []
    def raiz(p: Producto) -> str:
        n = " ".join(str(p.nombre or "").lower().split())
        for suf in _SUFIJOS_GENERO:
            n = n.replace(suf + " ", " ")
        return " ".join(n.split())
    deportivas = [p for p in del_tipo if "deportiv" in p.nombre.lower()]
    if len(deportivas) < 2 or len({raiz(p) for p in deportivas}) != 1:
        return []
    if len({str(p.genero or "").strip().lower() for p in deportivas}) != len(deportivas):
        return []  # mismo género: no son la misma prenda en dos versiones
    return sorted(deportivas, key=lambda p: p.nombre)


def _precio_medio(session: Session, producto_id: int) -> float | None:
    from sqlalchemy import func as sqlfunc

    p = session.scalar(
        select(sqlfunc.avg(Variante.precio_venta)).where(Variante.producto_id == int(producto_id), Variante.activo == True)  # noqa: E712
    )
    return float(p) if p is not None else None


def _desempatar(session: Session, conjunto: Producto, tipo: str, del_tipo: list[Producto], elegidas: list[Producto]) -> Producto | None:
    """Empates que la regla de precios de Daniel resuelve sola:

    - **Playera** del 3pz: entre Polo y Deportiva, la deportiva.
    - **Pants Suelto** que deja la chamarra: "todo vale más por separado", así
      que chamarra + suelto tiene que costar **más** que el 2pz del que salen
      (por eso el suelto de punto, no el liso, cuando el 2pz de la escuela es
      de punto). De los que cumplen, el más barato.
    """
    if tipo == "Playera":
        deportivas = [p for p in del_tipo if "deportiv" in p.nombre.lower()]
        if len(deportivas) == 1:
            return deportivas[0]
        return None  # varias deportivas (H y M): son alternativas, se resuelve arriba
    if tipo == "Pants Suelto":
        p2 = next((p for p in elegidas if _tipo_pieza(p) == "Pants 2pz"), None)
        precio_2pz = _precio_medio(session, p2.id) if p2 is not None else None
        precio_conjunto = _precio_medio(session, conjunto.id)
        if precio_2pz is None or precio_conjunto is None:
            return None
        cumplen = [
            (precio, p) for p, precio in ((p, _precio_medio(session, p.id)) for p in del_tipo)
            if precio is not None and precio_conjunto + precio >= precio_2pz
        ]
        return min(cumplen)[1] if cumplen else None
    return None


def _tallas_de(session: Session, producto_id: int) -> set[str]:
    return {
        _norm_talla(t)
        for t in session.scalars(
            select(Variante.talla).where(
                Variante.producto_id == int(producto_id), Variante.activo == True  # noqa: E712
            )
        ).all()
    }


def empata_en_tallas(session: Session, conjunto: Producto, pieza: Producto) -> bool:
    """¿Esta pieza sirve para armar este conjunto, aunque sea en una talla?

    Una pieza que no comparte **ninguna** talla con el conjunto no lo arma en
    ninguna: la receta nace muerta y `stock_derivado` devuelve None para todo.
    Pasó el 2026-09-22 con los dos Pants 3pz de Álvaro Obregón, a los que se
    les asignó una "Playera Deportiva" **unitalla** siendo pants por número:
    las nueve tallas quedaron imposibles de armar y nadie se enteró hasta que
    una se fue a negativo. Ver la nota 40 del vault."""
    del_conjunto = _tallas_de(session, conjunto.id)
    if not del_conjunto:
        return True   # sin tallas propias no hay con qué comparar
    return bool(del_conjunto & _tallas_de(session, pieza.id))


def proponer_receta(session: Session, conjunto: Producto) -> dict:
    """{"componentes": [(producto_id, cantidad)], "faltan": [...tipos], "ambiguas": {tipo: [nombres]}}.
    Solo propone cuando hay exactamente UNA prenda de cada tipo que pide la receta.

    Una pieza que no comparte ninguna talla con el conjunto **no cuenta como
    candidata**: armar con ella deja una receta que no se puede usar en ninguna
    talla. Si por eso no queda ninguna de un tipo, sale en `faltan` — que es lo
    que se quiere ver, en vez de una receta muerta."""
    plantilla = RECETAS_POR_TIPO.get(_tipo_pieza(conjunto))
    if plantilla is None:
        return {"componentes": [], "faltan": [], "ambiguas": {}}
    candidatas = [
        p
        for p in _candidatas(session, conjunto)
        if p.id != conjunto.id and empata_en_tallas(session, conjunto, p)
    ]
    componentes, faltan, ambiguas, elegidas = [], [], {}, []
    grupo = 0
    for tipo, cantidad in plantilla:
        del_tipo = [p for p in candidatas if _tipo_pieza(p) == tipo]
        alternativas = _alternativas(tipo, del_tipo)
        elegida = del_tipo[0] if len(del_tipo) == 1 else _desempatar(session, conjunto, tipo, del_tipo, elegidas)
        if elegida is not None:
            elegidas.append(elegida)
        if not del_tipo:
            faltan.append(tipo)
        elif elegida is not None:
            componentes.append((int(elegida.id), int(cantidad), grupo))
        elif alternativas:
            # Hombre y mujer de la misma prenda: vale cualquiera (mismo grupo)
            elegidas.extend(alternativas)
            componentes.extend((int(p.id), int(cantidad), grupo) for p in alternativas)
        else:
            ambiguas[tipo] = [p.nombre for p in del_tipo]
        grupo += 1
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
    """Lo que alcanza: min por grupo de piezas que se llevan (sumando las
    alternativas del grupo), en la misma talla. None si el conjunto no tiene
    receta o ninguna pieza de un grupo tiene esa talla."""
    receta = receta if receta is not None else receta_de(session, variante_conjunto.producto_id)
    grupos = [g for g in por_grupos(receta) if g[0].cantidad > 0]
    if not grupos:
        return None
    talla = _norm_talla(variante_conjunto.talla)
    posibles = []
    for grupo in grupos:
        hay = [
            (int(v.stock_actual), int(c.cantidad))
            for c in grupo
            for v in [_variantes_por_talla(session, c.componente_id).get(talla)]
            if v is not None
        ]
        if not hay:
            return None
        posibles.append(sum(stock for stock, _c in hay) // hay[0][1])
    return min(posibles)


def _pieza_del_grupo(session: Session, grupo: list[ConjuntoComponente], talla: str):
    """De un grupo de alternativas, la que se mueve: la que más existencia tiene
    en esa talla (lo que la empleada toma del estante). Sin alternativas, la única."""
    candidatas = [
        (c, v) for c in grupo
        for v in [_variantes_por_talla(session, c.componente_id).get(talla)]
        if v is not None
    ]
    if not candidatas:
        return grupo[0], None
    return max(candidatas, key=lambda cv: int(cv[1].stock_actual))


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


# ------------------------------------------------------- totales del inventario

def filtro_sin_conjuntos():
    """Para no contar dos veces: un Pants 3pz con receta **es** el pants 2pz y
    la playera que ya están en el estante, así que su existencia no se suma a
    los totales (piezas en tienda, valor del inventario, stock bajo). El stock
    por talla del conjunto sigue siendo el bueno para vender y para el kiosko;
    lo que no se hace es sumarlo aparte."""
    from pos_uniformes.database.models import Producto as _P

    return ~_P.id.in_(select(ConjuntoComponente.conjunto_id))


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
    for grupo in por_grupos(receta):
        c, v = _pieza_del_grupo(session, grupo, talla)
        if v is None:
            logger.warning("Conjunto %s talla %s: ninguna pieza del grupo tiene esa talla; no se movió", nombre, variante_conjunto.talla)
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
