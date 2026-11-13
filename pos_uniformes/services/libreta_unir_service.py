"""Unir dos ventas de la Libreta en UNA operación (Daniel, 2026-11-13).

«a veces mis empleadas venden e imprimen el ticket, pero esa misma persona se
decide y se lleva otra cosa, haciendo que sean dos operaciones y solo
debería ser una». La clienta se lleva las dos cosas: las dos ventas siguen
valiendo. Unirlas NO anula, no borra, no devuelve existencia y no toca el
dinero, el Monedero, las piezas ni las comisiones. Lo único que cambia es
que donde se cuentan operaciones (corte, Libreta, ranking, Telegram,
Analítica, gafete…) el grupo cuenta como 1 (`libreta_service.clave_operacion`).

Cómo se guarda: cada venta del grupo lleva en `operacion_grupo_id` el id de
la primera (la más vieja); NULL = sola. `operacion_unida_por` y
`operacion_unida_en` dicen quién y cuándo, y cada unión o separación deja
renglón en la bitácora (`auditoria_ausencias`, operación «unir_operacion» /
«separar_operacion»).

Reglas (si una falla, no se une):
- solo el dueño (el mismo permiso que borrar en MOVIMIENTOS del kiosko);
- solo ventas: ni apartados (tienen su propio folio y sus abonos: son otra
  cuenta), ni abonos, ni cambios, ni la compra de una empleada con precio
  especial (esa no es operación de nadie);
- de la misma empleada y del mismo día (hora local);
- una venta está en un solo grupo: si la anterior ya está unida, la nueva
  se suma a ese grupo (A+B, luego C → A+B+C, una sola operación); si la que
  se une ya está en otro grupo, se rechaza («ya está unida»: sepárala antes).

Nada aquí hace commit: lo hace quien llama.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select

from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.services.libreta_service import esta_unida  # noqa: F401 — se usa desde la pantalla

#: Solo las ventas se unen (ver el docstring del módulo).
TIPOS_QUE_SE_UNEN = ("venta",)


class NoSePuedeUnir(ValueError):
    """La unión (o la separación) no procede; el texto se le enseña al dueño."""


class SoloElDuenoUne(PermissionError):
    pass


@dataclass(frozen=True)
class ResultadoUnion:
    grupo_id: int
    ids: tuple[int, ...]

    @property
    def cuantas(self) -> int:
        return len(self.ids)


def _es_dueno(actor: str | None) -> bool:
    from pos_uniformes.services.nomina_service import OWNER_CODE

    return str(actor or "").strip().upper() == OWNER_CODE


def _fecha_local(momento: datetime) -> date:
    return momento.astimezone().date() if momento.tzinfo is not None else momento.date()


def motivo_para_no_unir(row) -> str | None:
    """Por qué esta fila no se puede unir con otra (None = sí se puede). Puro."""
    if getattr(row, "id", None) is None:
        return "Esa venta todavía no sube al servidor; actualiza en un momento."
    tipo = str(getattr(row, "tipo", None) or "venta")
    if tipo not in TIPOS_QUE_SE_UNEN:
        return f"Solo se unen ventas; esto es un {tipo}."
    if bool(getattr(row, "descuento_empleada", False)):
        return "La compra de una empleada no es operación: no se une."
    return None


def puede_ofrecerse(row) -> bool:
    """¿Tiene sentido enseñar «Unir con la anterior» para esta fila? Puro."""
    return motivo_para_no_unir(row) is None and getattr(row, "operacion_grupo_id", None) is None


def miembros(session, grupo_id: int) -> list[LibretaVenta]:
    return list(session.scalars(
        select(LibretaVenta)
        .where(LibretaVenta.operacion_grupo_id == int(grupo_id))
        .order_by(LibretaVenta.created_at, LibretaVenta.id)
    ).all())


def anterior_para_unir(session, venta_id: int) -> LibretaVenta | None:
    """La venta inmediata anterior de la misma empleada ese mismo día (la que
    «Unir con la anterior» uniría). Se saltan los abonos, apartados, cambios
    y compras de empleada: no se unen. Si la anterior ya es del mismo grupo,
    no hay nada que unir (None)."""
    venta = session.get(LibretaVenta, int(venta_id))
    if venta is None or venta.created_at is None:
        return None
    dia = _fecha_local(venta.created_at)
    candidatas = session.scalars(
        select(LibretaVenta)
        .where(
            LibretaVenta.employee_code == venta.employee_code,
            LibretaVenta.id != venta.id,
            LibretaVenta.tipo.in_(TIPOS_QUE_SE_UNEN),
            LibretaVenta.descuento_empleada.is_(False),
            LibretaVenta.created_at <= venta.created_at,
        )
        .order_by(LibretaVenta.created_at.desc(), LibretaVenta.id.desc())
        .limit(5)
    ).all()
    for c in candidatas:
        # Misma hora exacta: la de id menor es la anterior.
        if c.created_at == venta.created_at and c.id > venta.id:
            continue
        if _fecha_local(c.created_at) != dia:
            return None
        if venta.operacion_grupo_id is not None and c.operacion_grupo_id == venta.operacion_grupo_id:
            return None
        return c
    return None


def unir(session, venta_a_id: int, venta_b_id: int, *, actor: str, ahora: datetime | None = None) -> ResultadoUnion:
    """Une la venta B al grupo de la venta A (o forma uno nuevo A+B).

    B es la que se une: no puede estar ya en otro grupo. A puede estar sola o
    ya unida (el grupo crece). El grupo se queda con el id de su venta más
    vieja. No toca dinero, piezas, comisiones, existencia ni Monedero."""
    if not _es_dueno(actor):
        raise SoloElDuenoUne("Solo el dueño puede unir ventas.")
    if int(venta_a_id) == int(venta_b_id):
        raise NoSePuedeUnir("Es la misma venta.")
    a = session.get(LibretaVenta, int(venta_a_id))
    b = session.get(LibretaVenta, int(venta_b_id))
    if a is None or b is None:
        raise NoSePuedeUnir("Esa venta ya no existe; actualiza la Libreta.")
    for row in (a, b):
        motivo = motivo_para_no_unir(row)
        if motivo:
            raise NoSePuedeUnir(f"#{row.id}: {motivo}")
    if str(a.employee_code or "").upper() != str(b.employee_code or "").upper():
        raise NoSePuedeUnir("Son de empleadas distintas: solo se unen ventas de la misma.")
    if _fecha_local(a.created_at) != _fecha_local(b.created_at):
        raise NoSePuedeUnir("Son de días distintos: solo se unen ventas del mismo día.")
    if a.operacion_grupo_id is not None and a.operacion_grupo_id == b.operacion_grupo_id:
        raise NoSePuedeUnir("Esas dos ventas ya cuentan como 1 operación.")
    if b.operacion_grupo_id is not None:
        raise NoSePuedeUnir(f"#{b.id} ya está unida con otra venta. Sepárala primero.")

    grupo_antes = a.operacion_grupo_id
    grupo = miembros(session, grupo_antes) if grupo_antes is not None else [a]
    todas = sorted({r.id: r for r in [*grupo, b]}.values(), key=lambda r: (r.created_at, r.id))
    ancla = todas[0].id
    momento = ahora or datetime.now().astimezone()
    quien = str(actor).strip().upper()
    for row in todas:
        if row.operacion_grupo_id is None:
            row.operacion_unida_por = quien
            row.operacion_unida_en = momento
        row.operacion_grupo_id = ancla
    session.flush()
    _bitacora(session, quien, "unir_operacion", b, {"grupo": grupo_antes}, {"grupo": ancla, "con": a.id})
    return ResultadoUnion(grupo_id=ancla, ids=tuple(r.id for r in todas))


def separar(session, venta_id: int, *, actor: str) -> ResultadoUnion | None:
    """Saca la venta de su grupo: vuelve a contar como su propia operación.
    Si en el grupo queda una sola, esa también queda sola. Si sale la
    primera, el grupo pasa a la siguiente más vieja. Devuelve lo que quedó
    del grupo (None si ya no queda grupo)."""
    if not _es_dueno(actor):
        raise SoloElDuenoUne("Solo el dueño puede separar ventas.")
    venta = session.get(LibretaVenta, int(venta_id))
    if venta is None:
        raise NoSePuedeUnir("Esa venta ya no existe; actualiza la Libreta.")
    if venta.operacion_grupo_id is None:
        raise NoSePuedeUnir("Esa venta no está unida con otra.")
    grupo_antes = int(venta.operacion_grupo_id)
    resto = _soltar(session, venta)
    _bitacora(session, str(actor).strip().upper(), "separar_operacion", venta, {"grupo": grupo_antes}, {"grupo": None})
    return resto


def soltar_sin_permiso(session, venta: LibretaVenta) -> None:
    """Para quien ya tiene su propio permiso (borrar o reasignar la venta):
    la saca de su grupo antes, para que el grupo no se quede apuntando a una
    venta borrada ni junte a dos empleadas."""
    if getattr(venta, "operacion_grupo_id", None) is not None:
        _soltar(session, venta)


def _soltar(session, venta: LibretaVenta) -> ResultadoUnion | None:
    grupo_id = int(venta.operacion_grupo_id)
    resto = [r for r in miembros(session, grupo_id) if r.id != venta.id]
    venta.operacion_grupo_id = None
    venta.operacion_unida_por = None
    venta.operacion_unida_en = None
    if len(resto) <= 1:
        for r in resto:
            r.operacion_grupo_id = None
            r.operacion_unida_por = None
            r.operacion_unida_en = None
        session.flush()
        return None
    ancla = min(resto, key=lambda r: (r.created_at, r.id)).id
    for r in resto:
        r.operacion_grupo_id = ancla
    session.flush()
    return ResultadoUnion(grupo_id=ancla, ids=tuple(r.id for r in sorted(resto, key=lambda r: (r.created_at, r.id))))


def _bitacora(session, actor: str, operacion: str, venta: LibretaVenta, antes: dict, despues: dict) -> None:
    from pos_uniformes.services import auditoria_ausencias_service

    auditoria_ausencias_service.registrar(
        session,
        actor=actor,
        origen="kiosko",
        operacion=operacion,
        entidad="libreta_venta",
        entidad_id=int(venta.id),
        employee_code=venta.employee_code,
        antes=antes,
        despues=despues,
    )


# ─── Textos para la pantalla (puros) ─────────────────────────────────────


def texto_confirmar_union(ids: list[int] | tuple[int, ...], empleada: str) -> str:
    """«#1639 y #1640 de VEND-4 cuentan como 1 operación. El dinero, las
    piezas y las comisiones no cambian.»"""
    ids = sorted(int(i) for i in ids)
    numeros = [f"#{i}" for i in ids]
    lista = numeros[0] if len(numeros) == 1 else ", ".join(numeros[:-1]) + f" y {numeros[-1]}"
    return (
        f"{lista} de {empleada} cuentan como 1 operación. "
        "El dinero, las piezas y las comisiones no cambian."
    )


def texto_confirmar_separar(venta_id: int) -> str:
    return (
        f"#{int(venta_id)} vuelve a contar como su propia operación. "
        "El dinero, las piezas y las comisiones no cambian."
    )


def marca_de_grupo(row, posicion: int | None = None, total: int | None = None) -> str:
    """La marca que lleva en MOVIMIENTOS una venta unida: «🔗 misma clienta»
    (con «1/2» si se sabe su lugar en el grupo); "" si va sola."""
    if getattr(row, "operacion_grupo_id", None) is None:
        return ""
    if posicion and total and total > 1:
        return f"🔗 misma clienta {posicion}/{total}"
    return "🔗 misma clienta"


def posiciones_en_grupo(rows) -> dict[int, tuple[int, int]]:
    """{id: (lugar, de_cuántas)} de las filas unidas que se ven, en orden de
    hora (la primera es 1). Puro."""
    grupos: dict[int, list] = {}
    for r in rows or ():
        g = getattr(r, "operacion_grupo_id", None)
        if g is not None and getattr(r, "id", None) is not None:
            grupos.setdefault(int(g), []).append(r)
    salida: dict[int, tuple[int, int]] = {}
    for filas in grupos.values():
        filas.sort(key=lambda r: (r.created_at, r.id))
        for n, r in enumerate(filas, start=1):
            salida[int(r.id)] = (n, len(filas))
    return salida
