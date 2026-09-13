"""Bodega desde el celular de Daniel: llegó mercancía / pasar al piso.

Dos gestos, nada más:

- **Llegó mercancía** (del maquilador): entra al inventario (`ENTRADA_COMPRA`,
  sube `stock_actual`). Llega al piso; lo que Daniel decida guardar va a una
  caja (`BodegaContenido`), talla por talla. Es el dato que le faltaba a
  Revisar para aprender: qué se pidió y qué llegó.
- **Pasar al piso**: sale de la caja al rack. El total no cambia (ya era
  inventario), solo deja de estar guardado.

Todo lo pesado ya existe (`InventarioService`, `BodegaService`); aquí se
encadena en una sola transacción y se prepara lo que el celular enseña.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    BodegaCaja,
    BodegaContenido,
    BodegaUbicacion,
    CategoriaCaja,
    ConteoInventario,
    Escuela,
    EstadoCaja,
    Producto,
    Variante,
)
from pos_uniformes.services.bodega_service import BodegaService
from pos_uniformes.services.inventario_service import InventarioService

DUENO_CODE = "VEND-1"
DIAS_PEDIDO_VIGENTE = 60   # un pedido decidido hace más de esto ya no se ofrece como "llegó lo que pediste"


class SoloElDueno(PermissionError):
    pass


def _exigir_dueno(quien_code: str) -> None:
    if (quien_code or "").strip().upper() != DUENO_CODE:
        raise SoloElDueno("Solo Daniel mueve la bodega.")


# --- lecturas ------------------------------------------------------------------------

def cajas_activas(session: Session) -> list[dict]:
    """Las cajas con las que se puede trabajar, con cuántas piezas traen."""
    filas = session.execute(
        select(
            BodegaCaja.id, BodegaCaja.codigo, BodegaUbicacion.codigo,
            func.coalesce(func.sum(BodegaContenido.cantidad), 0),
            func.count(BodegaContenido.id),
        )
        .outerjoin(BodegaUbicacion, BodegaUbicacion.id == BodegaCaja.ubicacion_id)
        .outerjoin(BodegaContenido, BodegaContenido.caja_id == BodegaCaja.id)
        .where(BodegaCaja.estado == EstadoCaja.ACTIVA.value)
        .group_by(BodegaCaja.id, BodegaCaja.codigo, BodegaUbicacion.codigo)
        .order_by(BodegaCaja.codigo)
    ).all()
    return [
        {"id": int(i), "codigo": str(c), "ubicacion": str(u or ""), "piezas": int(p), "tallas": int(t)}
        for i, c, u, p, t in filas
    ]


def contenido_de_caja(session: Session, caja_id: int) -> list[dict]:
    filas = session.execute(
        select(BodegaContenido.variante_id, Producto.nombre, Variante.talla, Variante.color, BodegaContenido.cantidad)
        .join(Variante, Variante.id == BodegaContenido.variante_id)
        .join(Producto, Producto.id == Variante.producto_id)
        .where(BodegaContenido.caja_id == caja_id, BodegaContenido.cantidad > 0)
        .order_by(Producto.nombre, BodegaContenido.id)
    ).all()
    return [
        {"variante_id": int(v), "producto": str(p), "talla": str(t or ""), "color": str(c or ""), "cantidad": int(n)}
        for v, p, t, c, n in filas
    ]


def _pedidos_vigentes(session: Session, variante_ids: list[int], hoy: date | None = None) -> dict[int, tuple[int, date]]:
    """{variante_id: (pedido, fecha)} de la última decisión de Daniel (últimos 60 días)."""
    if not variante_ids:
        return {}
    hoy = hoy or date.today()
    desde = hoy - timedelta(days=DIAS_PEDIDO_VIGENTE)
    filas = session.execute(
        select(ConteoInventario.variante_id, ConteoInventario.pedido, ConteoInventario.pedido_decidido_at)
        .where(
            ConteoInventario.variante_id.in_(variante_ids),
            ConteoInventario.pedido.is_not(None),
            ConteoInventario.pedido > 0,
        )
        .order_by(ConteoInventario.pedido_decidido_at.desc(), ConteoInventario.id.desc())
    ).all()
    out: dict[int, tuple[int, date]] = {}
    for vid, pedido, cuando in filas:
        if vid in out or cuando is None:
            continue
        f = cuando.astimezone().date() if cuando.tzinfo else cuando.date()
        if f >= desde:
            out[int(vid)] = (int(pedido), f)
    return out


def buscar_prendas(session: Session, texto: str, *, limite: int = 12) -> list[dict]:
    """Prendas por nombre (y escuela), con sus tallas y lo que hay de cada una."""
    q = (texto or "").strip()
    if len(q) < 2:
        return []
    palabras = [p for p in q.split() if p]
    stmt = select(Producto).where(Producto.activo.is_(True))
    for p in palabras:
        stmt = stmt.where(Producto.nombre.ilike(f"%{p}%"))
    productos = list(session.scalars(stmt.order_by(Producto.nombre).limit(limite)).all())
    if not productos:
        return []
    ids = [p.id for p in productos]
    variantes = list(session.scalars(
        select(Variante).where(Variante.producto_id.in_(ids), Variante.activo.is_(True)).order_by(Variante.producto_id, Variante.id)
    ).all())
    en_cajas: dict[int, int] = {
        int(vid): int(n)
        for vid, n in session.execute(
            select(BodegaContenido.variante_id, func.sum(BodegaContenido.cantidad))
            .where(BodegaContenido.variante_id.in_([v.id for v in variantes]))
            .group_by(BodegaContenido.variante_id)
        ).all()
    }
    pedidos = _pedidos_vigentes(session, [v.id for v in variantes])
    escuelas = {e.id: e.nombre for e in session.scalars(select(Escuela).where(Escuela.id.in_([p.escuela_id for p in productos if p.escuela_id]))).all()}
    por_producto: dict[int, list[dict]] = {}
    for v in variantes:
        guardadas = en_cajas.get(v.id, 0)
        ped = pedidos.get(v.id)
        por_producto.setdefault(v.producto_id, []).append({
            "variante_id": v.id,
            "talla": str(v.talla or ""),
            "color": str(v.color or ""),
            "a_la_mano": max(0, int(v.stock_actual) - guardadas),
            "en_cajas": guardadas,
            "pedido": ped[0] if ped else None,
            "pedido_fecha": ped[1].isoformat() if ped else None,
        })
    return [
        {
            "producto_id": p.id,
            "nombre": str(p.nombre),
            "escuela": escuelas.get(p.escuela_id, "") if p.escuela_id else "Básicos",
            "tallas": por_producto.get(p.id, []),
        }
        for p in productos
        if por_producto.get(p.id)
    ]


# --- los dos gestos ----------------------------------------------------------------

def _ubicacion_almacen(session: Session) -> int | None:
    u = session.scalars(
        select(BodegaUbicacion).where(BodegaUbicacion.activo.is_(True), BodegaUbicacion.rack != "PISO").order_by(BodegaUbicacion.id)
    ).first()
    return u.id if u else None


def llego_mercancia(
    session: Session,
    *,
    items: list[dict],
    quien_code: str,
    quien: str = "",
    caja_id: int | None = None,
    caja_nueva: bool = False,
    referencia: str = "",
) -> dict:
    """`items`: [{variante_id, cantidad, a_caja}]. `cantidad` entra al
    inventario (llega al piso); `a_caja` (≤ cantidad, opcional) es lo que se
    guarda. Solo si algo va a caja se usa `caja_id` o se abre una nueva
    (`caja_nueva`) en el almacén."""
    _exigir_dueno(quien_code)
    limpios: list[tuple[int, int, int]] = []
    for i in items:
        n = int(i.get("cantidad") or 0)
        a_caja = int(i.get("a_caja") or 0)
        if n <= 0:
            continue
        if a_caja < 0 or a_caja > n:
            raise ValueError("No se puede guardar en caja más de lo que llegó.")
        limpios.append((int(i["variante_id"]), n, a_caja))
    if not limpios:
        raise ValueError("No hay piezas que registrar.")
    firma = f"{quien} ({quien_code})" if quien else quien_code
    guardadas = sum(a for _, _, a in limpios)
    caja = None
    if guardadas > 0:
        if caja_nueva or caja_id is None:
            caja = BodegaService.crear_caja(session, CategoriaCaja.A, ubicacion_id=_ubicacion_almacen(session), creado_por=firma, notas=referencia or None)
        else:
            caja = session.get(BodegaCaja, caja_id)
            if caja is None:
                raise ValueError("Esa caja no existe.")
    piezas = 0
    for vid, n, a_caja in limpios:
        variante = session.get(Variante, vid)
        if variante is None:
            raise ValueError(f"No existe la talla {vid}.")
        donde = f"{n - a_caja} al piso" + (f", {a_caja} en {caja.codigo}" if a_caja and caja else "")
        InventarioService.registrar_ingreso_compra(
            session, variante, n, referencia=referencia or "maquilador", observacion=f"Llegó: {donde}", creado_por=firma,
        )
        session.flush()
        if a_caja and caja is not None:
            BodegaService.ingresar_producto(session, caja.id, vid, a_caja, creado_por=firma, observacion=referencia or None)
        piezas += n
    session.flush()
    return {
        "caja_id": caja.id if caja else None,
        "caja_codigo": caja.codigo if caja else "",
        "piezas": piezas,
        "al_piso": piezas - guardadas,
        "en_caja": guardadas,
        "tallas": len(limpios),
    }


def pasar_al_piso(session: Session, *, caja_id: int, items: list[dict], quien_code: str, quien: str = "") -> dict:
    """`items`: [{variante_id, cantidad}] que salen de la caja al rack."""
    _exigir_dueno(quien_code)
    caja = session.get(BodegaCaja, caja_id)
    if caja is None:
        raise ValueError("Esa caja no existe.")
    firma = f"{quien} ({quien_code})" if quien else quien_code
    piezas = 0
    tallas = 0
    for i in items:
        n = int(i.get("cantidad") or 0)
        if n <= 0:
            continue
        BodegaService.retirar_producto(session, caja.id, int(i["variante_id"]), n, creado_por=firma, observacion="Pasó al piso")
        piezas += n
        tallas += 1
    if not tallas:
        raise ValueError("No hay piezas que pasar.")
    quedan = int(session.scalar(select(func.coalesce(func.sum(BodegaContenido.cantidad), 0)).where(BodegaContenido.caja_id == caja.id)))
    if quedan == 0:
        BodegaService.cambiar_estado_caja(session, caja.id, EstadoCaja.VACIA)
    session.flush()
    return {"caja_codigo": caja.codigo, "piezas": piezas, "tallas": tallas, "quedan": quedan}
