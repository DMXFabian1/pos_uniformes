"""Arregla el catálogo de las dos Álvaro Obregón (una sola vez).

Salió reconciliando el stock negativo el 2026-09-22 (ver la nota 40 del vault).
Al partir la escuela por nivel el 20-sep quedaron tres cosas a medias:

1. **El Carretón (#52)**: su Pants 3pz tenía de receta una "Playera Deportiva"
   **unitalla**, así que ninguna de sus nueve tallas se podía armar. La escuela
   sí tiene su playera propia, con las mismas tallas exactas.
2. **Preescolar (#43)**: su Pants 3pz también apunta a esa playera unitalla,
   pero esa escuela **no vende playera**, así que un 3pz ahí no es un 3pz. Se le
   quita la receta; y si además nunca se vendió y no tiene existencia, se
   desactiva — un producto que no se puede armar ni se ha vendido solo estorba.
3. **Preescolar (#43)**: dos chamarras duplicadas, "Deportiva" y "Deportivo",
   mismas tallas y misma receta, las dos en el uniforme. Se funden.

Uso:
    # Solo enseña lo que haría:
    python -m pos_uniformes.scripts.arreglar_alvaro_obregon

    # Lo hace:
    python -m pos_uniformes.scripts.arreglar_alvaro_obregon --aplicar

Todo se resuelve **por nombre**, no por id: los ids de la Mac no tienen por qué
ser los de la tienda. Si algo no está como se espera, lo dice y no toca nada.
"""

from __future__ import annotations

import sys

from sqlalchemy import func, select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import (
    Escuela,
    MovimientoInventario,
    Producto,
    TipoMovimientoInventario,
    UniformePieza,
    Variante,
)
from pos_uniformes.scripts import fundir_productos
from pos_uniformes.services import conjunto_service

FIRMA = "arreglo_alvaro_obregon"

TRES_PZ_CARRETON = "Pants 3pz Álvaro Obregón El Carretón"
TRES_PZ_PREESCOLAR = "Pants 3pz Deportivo Álvaro Obregón"
CHAMARRA_QUE_SE_QUEDA = "Chamarra Deportiva Álvaro Obregón"
CHAMARRA_QUE_SE_VA = "Chamarra Deportivo Álvaro Obregón"


def _producto(session, nombre_base: str) -> Producto | None:
    return session.scalar(
        select(Producto).where(
            Producto.nombre_base == nombre_base, Producto.activo.is_(True)
        )
    )


def _ventas(session, producto: Producto) -> int:
    ids = [
        int(v)
        for v in session.scalars(
            select(Variante.id).where(Variante.producto_id == producto.id)
        ).all()
    ]
    if not ids:
        return 0
    return int(
        session.scalar(
            select(func.count(MovimientoInventario.id)).where(
                MovimientoInventario.variante_id.in_(ids),
                MovimientoInventario.tipo_movimiento
                == TipoMovimientoInventario.SALIDA_VENTA,
            )
        )
        or 0
    )


def _existencia(session, producto: Producto) -> int:
    return int(
        session.scalar(
            select(func.coalesce(func.sum(Variante.stock_actual), 0)).where(
                Variante.producto_id == producto.id, Variante.activo.is_(True)
            )
        )
        or 0
    )


def _nombres(session, componentes) -> list[str]:
    return [
        str(session.get(Producto, c.componente_id).nombre_base or "")
        for c in componentes
    ]


# ------------------------------------------------------------------ los pasos

def paso_carreton(session, *, aplicar: bool) -> list[str]:
    """La receta del 3pz de El Carretón, con la playera que sí empata."""
    tres = _producto(session, TRES_PZ_CARRETON)
    if tres is None:
        return [f"· {TRES_PZ_CARRETON}: no existe, nada que hacer."]

    antes = _nombres(session, conjunto_service.receta_de(session, tres.id))
    propuesta = conjunto_service.proponer_receta(session, tres)
    if not propuesta["componentes"]:
        return [
            f"· {TRES_PZ_CARRETON}: no hay propuesta "
            f"(faltan {propuesta['faltan']}, ambiguas {list(propuesta['ambiguas'])}). No se toca."
        ]
    piezas = [str(session.get(Producto, pid).nombre_base) for pid, _c, _g in propuesta["componentes"]]
    lineas = [f"· {TRES_PZ_CARRETON}", f"    antes:  {antes}", f"    queda:  {piezas}"]
    if aplicar:
        conjunto_service.definir_receta(
            session, tres.id, propuesta["componentes"], creado_por=FIRMA
        )
        cambios = conjunto_service.sincronizar_conjunto(session, tres.id, creado_por=FIRMA)
        lineas.append(f"    hecho: {cambios} tallas con su existencia ya calculada")
    return lineas


def paso_preescolar(session, *, aplicar: bool) -> list[str]:
    """El 3pz del preescolar: sin playera no hay 3pz."""
    tres = _producto(session, TRES_PZ_PREESCOLAR)
    if tres is None:
        return [f"· {TRES_PZ_PREESCOLAR}: no existe, nada que hacer."]

    antes = _nombres(session, conjunto_service.receta_de(session, tres.id))
    ventas, existencia = _ventas(session, tres), _existencia(session, tres)
    lineas = [
        f"· {TRES_PZ_PREESCOLAR}",
        f"    receta actual: {antes}",
        f"    ventas: {ventas}   existencia: {existencia}",
    ]
    # Desactivar solo si de verdad no se ha usado: la base de la tienda manda,
    # no lo que se vio en la Mac.
    se_desactiva = ventas == 0 and existencia == 0
    lineas.append(
        "    queda: sin receta y DESACTIVADO (nunca se vendió y no hay existencia)"
        if se_desactiva
        else "    queda: sin receta, pero ACTIVO (tiene historia o existencia; eso lo decides tú)"
    )
    if aplicar:
        conjunto_service.quitar_receta(session, tres.id)
        if se_desactiva:
            tres.activo = False
            tres.descripcion = (
                f"{(tres.descripcion or '').strip()} "
                "[desactivado: la escuela no vende playera, no se puede armar un 3pz]"
            ).strip()
            session.add(tres)
        session.flush()
        lineas.append("    hecho")
    return lineas


def paso_chamarras(session, *, aplicar: bool) -> list[str]:
    """Las dos chamarras duplicadas del preescolar."""
    queda = _producto(session, CHAMARRA_QUE_SE_QUEDA)
    se_va = _producto(session, CHAMARRA_QUE_SE_VA)
    if queda is None or se_va is None:
        return ["· Chamarras duplicadas: ya no están las dos, nada que fundir."]

    plan = fundir_productos.planear(session, de=se_va.id, en=queda.id)
    lineas = [
        f"· Chamarras duplicadas del preescolar",
        f"    se va:    #{se_va.id} {se_va.nombre_base} (existencia {_existencia(session, se_va)})",
        f"    se queda: #{queda.id} {queda.nombre_base} (existencia {_existencia(session, queda)})",
        f"    tallas que se mudan: {len(plan['mover'])}   tallas que se suman: {len(plan['sumar'])}",
    ]
    if plan["sumar"]:
        lineas.append(
            "    OJO: las existencias se SUMAN. Como pueden ser las mismas prendas "
            "contadas dos veces, esas tallas quedarán marcadas como nunca contadas "
            "y saldrán en rojo hasta que alguien las cuente."
        )
    if aplicar:
        tocadas = [existente.id for _v, existente in plan["sumar"]]
        fundir_productos.aplicar(session, plan, quien=FIRMA)
        # Sumar dos fichas duplicadas puede haber contado dos veces las mismas
        # prendas físicas. Nadie sabe cuál de los dos diez era el bueno, así que
        # esas tallas quedan como **nunca contadas**: salen en rojo y el kiosko
        # las pide a contar, en vez de arrastrar un número inventado.
        for vid in tocadas:
            v = session.get(Variante, vid)
            if v is not None:
                v.ultimo_conteo_at = None
                session.add(v)
        # El uniforme se queda apuntando a un producto muerto si no se limpia.
        huerfanas = session.scalars(
            select(UniformePieza).where(
                UniformePieza.producto_id == se_va.id, UniformePieza.activo.is_(True)
            )
        ).all()
        for pieza in huerfanas:
            pieza.activo = False
            session.add(pieza)
        session.flush()
        lineas.append(
            f"    hecho ({len(huerfanas)} pieza(s) del uniforme apagadas; "
            f"{len(tocadas)} tallas quedan como nunca contadas, para que se cuenten)"
        )
    return lineas


def main() -> int:
    aplicar = "--aplicar" in sys.argv
    with get_session() as session:
        escuelas = [
            e.nombre
            for e in session.scalars(
                select(Escuela).where(Escuela.nombre.like("Álvaro Obregón%"))
            ).all()
        ]
        print(f"Escuelas encontradas: {escuelas or 'ninguna'}\n")

        for paso in (paso_carreton, paso_preescolar, paso_chamarras):
            for linea in paso(session, aplicar=aplicar):
                print(linea)
            print()

        if aplicar:
            session.commit()
            print("Aplicado. Todo dejó movimiento o nota, así que se puede auditar.")
        else:
            print("Solo reporte. Para hacerlo: --aplicar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
