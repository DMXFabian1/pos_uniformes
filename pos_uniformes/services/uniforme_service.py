"""El uniforme de una escuela como entidad (catálogo, fase 2).

Una escuela tiene un `Uniforme`; sus `UniformePieza` señalan productos —los
propios de la escuela (con escudo, `producto.escuela_id`) o los generales del
estante (pants liso rojo, camisa de olan)— sin copiarlos: la prenda vive una
vez, con un stock y sus SKUs, y aparece en todos los uniformes que la señalen.

Transición: mientras el tarifario, el guiado y la hoja de conteo sigan leyendo
`catalog_school_product_link`, aquí se mantienen las ligas en espejo (agregar
una pieza general crea la liga; quitarla la borra). Ver Obsidian 38.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pos_uniformes.database.models import (
    CatalogSchoolProductLink,
    Escuela,
    Producto,
    Uniforme,
    UniformePieza,
)
from pos_uniformes.services.school_tariff_service import _PIEZA_ORDER

GRUPOS = ("Diario", "Deportivo", "Escolta", "Accesorio", "Otro")

# Tipo de prenda (minúsculas) → grupo de la pieza dentro del uniforme.
_GRUPO_POR_TIPO_PRENDA = {
    "deportivo": "Deportivo",
    "deportivo casual": "Deportivo",
    "oficial": "Diario",
    "básico": "Diario",
    "basico": "Diario",
    "escolta": "Escolta",
    "accesorio": "Accesorio",
}


# Un básico del estante que es pants/playera/short/chamarra va al grupo
# Deportivo aunque su tipo de prenda diga "Básico".
_PIEZAS_DEPORTIVAS = {"Pants 3pz", "Pants 2pz", "Pants Suelto", "Chamarra", "Playera", "Short"}


def grupo_para(producto: Producto) -> str:
    tipo = str(producto.tipo_prenda.nombre if producto.tipo_prenda is not None else "").strip().lower()
    pieza = str(producto.tipo_pieza.nombre if producto.tipo_pieza is not None else "").strip()
    grupo = _GRUPO_POR_TIPO_PRENDA.get(tipo, "Otro")
    if tipo in {"básico", "basico", ""} and pieza in _PIEZAS_DEPORTIVAS:
        return "Deportivo"
    return grupo


def _orden_pieza(producto: Producto) -> int:
    tipo = producto.tipo_pieza.nombre if producto.tipo_pieza is not None else ""
    return _PIEZA_ORDER.get(str(tipo or "").strip(), 50)


def _es_general(producto: Producto) -> bool:
    return producto.escuela_id is None


def _clave_propuesta(producto: Producto) -> tuple:
    return (_orden_pieza(producto), grupo_para(producto), str(producto.nombre))


def proponer(session, escuela_id: int) -> list[dict]:
    """Lo que hoy ya se sabe del uniforme de la escuela: sus productos activos
    más los generales ligados, en el orden del tarifario. No escribe nada."""
    propios = session.scalars(
        select(Producto)
        .options(joinedload(Producto.tipo_prenda), joinedload(Producto.tipo_pieza))
        .where(Producto.escuela_id == int(escuela_id), Producto.activo == True)  # noqa: E712
    ).unique().all()
    ligados = session.scalars(
        select(Producto)
        .join(CatalogSchoolProductLink, CatalogSchoolProductLink.producto_id == Producto.id)
        .options(joinedload(Producto.tipo_prenda), joinedload(Producto.tipo_pieza))
        .where(
            CatalogSchoolProductLink.escuela_id == int(escuela_id),
            CatalogSchoolProductLink.activo == True,  # noqa: E712
            Producto.activo == True,  # noqa: E712
        )
    ).unique().all()
    vistos: set[int] = set()
    filas: list[dict] = []
    for p in sorted(list(propios) + list(ligados), key=_clave_propuesta):
        if p.id in vistos:
            continue
        vistos.add(p.id)
        filas.append(_fila_producto(p))
    return filas


def _fila_producto(p: Producto, pieza: UniformePieza | None = None) -> dict:
    return {
        "pieza_id": int(pieza.id) if pieza is not None else None,
        "producto_id": int(p.id),
        "nombre": str(p.nombre),
        "tipo_pieza": p.tipo_pieza.nombre if p.tipo_pieza is not None else "",
        "tipo_prenda": p.tipo_prenda.nombre if p.tipo_prenda is not None else "",
        "origen": "General" if _es_general(p) else "Escuela",
        "grupo": pieza.grupo if pieza is not None else grupo_para(p),
        "orden": int(pieza.orden) if pieza is not None else _orden_pieza(p),
        "obligatoria": bool(pieza.obligatoria) if pieza is not None else True,
        "color": (pieza.color or "") if pieza is not None else "",
        "nota": (pieza.nota or "") if pieza is not None else "",
    }


def uniforme_de(session, escuela_id: int, *, crear: bool = False) -> Uniforme | None:
    uni = session.scalar(
        select(Uniforme).where(Uniforme.escuela_id == int(escuela_id), Uniforme.activo == True)  # noqa: E712
        .order_by(Uniforme.id)
    )
    if uni is None and crear:
        escuela = session.get(Escuela, int(escuela_id))
        if escuela is None:
            raise ValueError("No existe la escuela.")
        uni = Uniforme(escuela_id=escuela.id, nombre="Uniforme")
        session.add(uni)
        session.flush()
    return uni


def piezas_de(session, uniforme_id: int) -> list[dict]:
    piezas = session.scalars(
        select(UniformePieza)
        .options(
            joinedload(UniformePieza.producto).joinedload(Producto.tipo_pieza),
            joinedload(UniformePieza.producto).joinedload(Producto.tipo_prenda),
        )
        .where(UniformePieza.uniforme_id == int(uniforme_id), UniformePieza.activo == True)  # noqa: E712
        .order_by(UniformePieza.orden, UniformePieza.id)
    ).unique().all()
    return [_fila_producto(pz.producto, pz) for pz in piezas]


def _espejo_liga(session, uniforme: Uniforme, producto: Producto, *, poner: bool) -> None:
    """Mientras los consumidores lean ligas, una pieza general las mantiene."""
    if not _es_general(producto):
        return
    liga = session.scalar(
        select(CatalogSchoolProductLink).where(
            CatalogSchoolProductLink.escuela_id == uniforme.escuela_id,
            CatalogSchoolProductLink.producto_id == producto.id,
        )
    )
    if poner:
        if liga is None:
            session.add(CatalogSchoolProductLink(escuela_id=uniforme.escuela_id, producto_id=producto.id))
        elif not liga.activo:
            liga.activo = True
    elif liga is not None:
        session.delete(liga)
    session.flush()


def agregar_pieza(
    session,
    uniforme_id: int,
    producto_id: int,
    *,
    grupo: str | None = None,
    color: str | None = None,
    obligatoria: bool = True,
    orden: int | None = None,
) -> UniformePieza:
    uni = session.get(Uniforme, int(uniforme_id))
    producto = session.get(Producto, int(producto_id))
    if uni is None or producto is None:
        raise ValueError("No existe el uniforme o el producto.")
    if grupo is not None and grupo not in GRUPOS:
        raise ValueError(f"Grupo desconocido: {grupo}")
    pieza = session.scalar(
        select(UniformePieza).where(
            UniformePieza.uniforme_id == uni.id, UniformePieza.producto_id == producto.id
        )
    )
    if pieza is None:
        pieza = UniformePieza(uniforme_id=uni.id, producto_id=producto.id)
        session.add(pieza)
    pieza.activo = True
    pieza.grupo = grupo or grupo_para(producto)
    pieza.obligatoria = bool(obligatoria)
    if color is not None:
        pieza.color = color.strip() or None
    pieza.orden = int(orden) if orden is not None else _orden_pieza(producto)
    session.flush()
    _espejo_liga(session, uni, producto, poner=True)
    return pieza


def quitar_pieza(session, pieza_id: int) -> None:
    """La pieza queda inactiva (no se borra): así `armar` no la regresa si
    Daniel la quitó a propósito, y `agregar_pieza` la reactiva si se arrepiente."""
    pieza = session.get(UniformePieza, int(pieza_id))
    if pieza is None:
        return
    pieza.activo = False
    session.flush()
    _espejo_liga(session, pieza.uniforme, pieza.producto, poner=False)


_CAMPOS_EDITABLES = {"grupo", "obligatoria", "color", "nota", "orden"}


def actualizar_pieza(session, pieza_id: int, **campos) -> UniformePieza:
    pieza = session.get(UniformePieza, int(pieza_id))
    if pieza is None:
        raise ValueError("No existe la pieza.")
    raros = set(campos) - _CAMPOS_EDITABLES
    if raros:
        raise ValueError(f"Campos no editables: {sorted(raros)}")
    if "grupo" in campos and campos["grupo"] not in GRUPOS:
        raise ValueError(f"Grupo desconocido: {campos['grupo']}")
    for k, v in campos.items():
        if k in {"color", "nota"}:
            v = (str(v).strip() or None) if v is not None else None
        elif k == "obligatoria":
            v = bool(v)
        elif k == "orden":
            v = int(v)
        setattr(pieza, k, v)
    session.flush()
    return pieza


def mover_pieza(session, pieza_id: int, delta: int) -> None:
    """Sube (delta<0) o baja (delta>0) la pieza dentro de su uniforme. Deja los
    órdenes compactos (0..n-1) para que el siguiente movimiento sea predecible."""
    pieza = session.get(UniformePieza, int(pieza_id))
    if pieza is None or delta == 0:
        return
    hermanas = session.scalars(
        select(UniformePieza)
        .where(UniformePieza.uniforme_id == pieza.uniforme_id, UniformePieza.activo == True)  # noqa: E712
        .order_by(UniformePieza.orden, UniformePieza.id)
    ).all()
    ids = [h.id for h in hermanas]
    i = ids.index(pieza.id)
    j = max(0, min(len(hermanas) - 1, i + delta))
    hermanas.insert(j, hermanas.pop(i))
    for n, h in enumerate(hermanas):
        h.orden = n
    session.flush()


def armar(session, escuela_id: int) -> Uniforme:
    """Crea (o completa) el uniforme de la escuela con lo que ya se sabe.
    Idempotente: solo agrega las piezas que nunca estuvieron; no toca las que
    ya están ni regresa las que Daniel quitó (quedan inactivas)."""
    uni = uniforme_de(session, escuela_id, crear=True)
    existentes = {
        pz.producto_id
        for pz in session.scalars(select(UniformePieza).where(UniformePieza.uniforme_id == uni.id)).all()
    }
    for fila in proponer(session, escuela_id):
        if fila["producto_id"] in existentes:
            continue
        agregar_pieza(
            session, uni.id, fila["producto_id"], grupo=fila["grupo"], orden=fila["orden"]
        )
    return uni


def resumen(session) -> list[dict]:
    """Una fila por escuela activa: si tiene uniforme y cuántas piezas propias
    y generales tendría (propuesta) o tiene (armado)."""
    filas = []
    for esc in session.scalars(select(Escuela).where(Escuela.activo == True).order_by(Escuela.nombre)).all():  # noqa: E712
        uni = uniforme_de(session, esc.id)
        piezas = piezas_de(session, uni.id) if uni is not None else proponer(session, esc.id)
        filas.append({
            "escuela_id": int(esc.id),
            "escuela": str(esc.nombre),
            "armado": uni is not None,
            "propias": sum(1 for p in piezas if p["origen"] == "Escuela"),
            "generales": sum(1 for p in piezas if p["origen"] == "General"),
            "piezas": piezas,
        })
    return filas
