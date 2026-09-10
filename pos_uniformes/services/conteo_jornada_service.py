"""Jornadas de conteo: abrir, retomar, ver el avance, terminar y revisar.

Una jornada es el folio que le faltaba al conteo: quién cuenta, qué (una
escuela, o una prenda de los básicos) y cuándo empezó. Con eso:

- se puede **dejar a medias** y seguir mañana (la jornada queda abierta);
- se ve el **avance**: cuántas tallas de cuántas, cuántas prendas completas;
- Daniel **revisa por bloque**: las diferencias de una jornada terminada,
  y las aplica de un golpe con `confirmar_ajustes_lote`.

Reglas:
- Una jornada la retoma **solo quien la abrió**. Si otra empleada la toma,
  las mezclas de criterio se vuelven imposibles de auditar.
- Terminar no aplica nada al inventario. Revisar sí, y lo hace el dueño.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import ConteoInventario, ConteoJornada, Escuela

DUENO_CODE = "VEND-1"


class JornadaAjena(Exception):
    """Alguien intentó seguir una jornada que abrió otra persona."""


@dataclass(frozen=True)
class JornadaRef:
    """Foto plana de una jornada, para pasarla a la UI sin arrastrar la sesión.

    Un objeto ORM fuera de su sesión revienta al tocarle un atributo; la UI
    abre y cierra sesiones a cada rato. Esto no.
    """

    id: int
    titulo: str
    escuela_id: int | None
    tipo_pieza: str
    empleada_code: str
    empleada_nombre: str
    total_tallas: int
    iniciada_at: datetime | None
    terminada_at: datetime | None = None

    @property
    def quien(self) -> str:
        return self.empleada_nombre or self.empleada_code


def ref(jornada: ConteoJornada) -> JornadaRef:
    return JornadaRef(
        id=int(jornada.id),
        titulo=str(jornada.titulo or ""),
        escuela_id=jornada.escuela_id,
        tipo_pieza=str(jornada.tipo_pieza or ""),
        empleada_code=str(jornada.empleada_code or ""),
        empleada_nombre=str(jornada.empleada_nombre or ""),
        total_tallas=int(jornada.total_tallas or 0),
        iniciada_at=jornada.iniciada_at,
        terminada_at=jornada.terminada_at,
    )


def _variantes_del_alcance(session: Session, escuela_id: int | None, tipo_pieza: str) -> list[dict]:
    """Los grupos producto→tallas que abarca la jornada (mismo orden que la captura)."""
    from pos_uniformes.services.conteo_service import (
        obtener_variantes_agrupadas_por_producto,
        obtener_variantes_basicos_agrupadas,
    )

    if escuela_id is None:
        grupos = obtener_variantes_basicos_agrupadas(session, tipo_pieza=tipo_pieza or None)
    else:
        grupos = obtener_variantes_agrupadas_por_producto(session, escuela_id)
    return [g for g in grupos if not g.get("virtual")]


def abrir_jornada(
    session: Session,
    *,
    escuela_id: int | None,
    tipo_pieza: str = "",
    empleada_code: str,
    empleada_nombre: str = "",
) -> ConteoJornada:
    """Abre una jornada nueva y deja anotado cuántas tallas abarca."""
    if not empleada_code or not empleada_code.strip():
        raise ValueError("Una jornada necesita el gafete de quien cuenta.")
    grupos = _variantes_del_alcance(session, escuela_id, tipo_pieza)
    total = sum(len(g["variantes"]) for g in grupos)
    if escuela_id is None:
        titulo = f"Básicos · {tipo_pieza}" if tipo_pieza else "Básicos"
    else:
        escuela = session.get(Escuela, escuela_id)
        titulo = escuela.nombre if escuela is not None else f"Escuela {escuela_id}"
    jornada = ConteoJornada(
        escuela_id=escuela_id,
        tipo_pieza=(tipo_pieza or "").strip(),
        titulo=titulo,
        empleada_code=empleada_code.strip().upper(),
        empleada_nombre=(empleada_nombre or "").strip(),
        total_tallas=total,
    )
    session.add(jornada)
    session.flush()
    return jornada


def jornadas_abiertas(session: Session) -> list[ConteoJornada]:
    """Las que nadie ha terminado, la más reciente primero."""
    return list(
        session.scalars(
            select(ConteoJornada)
            .where(ConteoJornada.terminada_at.is_(None))
            .order_by(ConteoJornada.iniciada_at.desc())
        ).all()
    )


def jornadas_por_revisar(session: Session) -> list[ConteoJornada]:
    """Terminadas y todavía no aplicadas al inventario."""
    return list(
        session.scalars(
            select(ConteoJornada)
            .where(ConteoJornada.terminada_at.is_not(None), ConteoJornada.revisada_at.is_(None))
            .order_by(ConteoJornada.terminada_at.desc())
        ).all()
    )


def puede_seguirla(jornada: ConteoJornada, empleada_code: str) -> bool:
    """Solo quien la abrió, o el dueño."""
    code = (empleada_code or "").strip().upper()
    return code == jornada.empleada_code or code == DUENO_CODE


def capturado_en_jornada(session: Session, jornada_id: int) -> dict[int, int]:
    """{variante_id: stock_fisico} de lo que ya se capturó en la jornada.

    Si una talla se capturó dos veces (raro, pero posible al retomar), manda
    la última.
    """
    filas = session.execute(
        select(ConteoInventario.variante_id, ConteoInventario.stock_fisico)
        .where(ConteoInventario.jornada_id == jornada_id)
        .order_by(ConteoInventario.contado_at.asc(), ConteoInventario.id.asc())
    ).all()
    return {int(vid): int(fisico) for vid, fisico in filas}


@dataclass(frozen=True)
class Avance:
    tallas_hechas: int
    tallas_total: int
    prendas_hechas: int
    prendas_total: int

    @property
    def completa(self) -> bool:
        return self.tallas_total > 0 and self.tallas_hechas >= self.tallas_total

    @property
    def porcentaje(self) -> int:
        return int(round(100 * self.tallas_hechas / self.tallas_total)) if self.tallas_total else 0


def avance(session: Session, jornada: ConteoJornada) -> Avance:
    """Cuántas tallas y cuántas prendas van (puro sobre la consulta)."""
    hechas = capturado_en_jornada(session, jornada.id)
    grupos = _variantes_del_alcance(session, jornada.escuela_id, jornada.tipo_pieza)
    prendas_total = len(grupos)
    prendas_hechas = sum(
        1 for g in grupos
        if g["variantes"] and all(v.variante_id in hechas for v in g["variantes"])
    )
    total = sum(len(g["variantes"]) for g in grupos) or jornada.total_tallas
    return Avance(
        tallas_hechas=len(hechas),
        tallas_total=total,
        prendas_hechas=prendas_hechas,
        prendas_total=prendas_total,
    )


def terminar_jornada(session: Session, jornada: ConteoJornada, *, empleada_code: str) -> ConteoJornada:
    """La cierra. No aplica nada al inventario: eso lo hace la revisión."""
    if not puede_seguirla(jornada, empleada_code):
        raise JornadaAjena(f"La jornada la abrió {jornada.empleada_nombre or jornada.empleada_code}.")
    jornada.terminada_at = func.now()
    session.add(jornada)
    session.flush()
    return jornada


@dataclass(frozen=True)
class LineaRevision:
    producto: str
    talla: str
    sistema: int
    fisico: int
    diferencia: int


@dataclass(frozen=True)
class ResumenRevision:
    jornada_id: int
    titulo: str
    quien: str
    lineas: list[LineaRevision]

    @property
    def con_diferencia(self) -> list[LineaRevision]:
        return [l for l in self.lineas if l.diferencia != 0]

    @property
    def piezas_de_menos(self) -> int:
        return -sum(l.diferencia for l in self.lineas if l.diferencia < 0)

    @property
    def piezas_de_mas(self) -> int:
        return sum(l.diferencia for l in self.lineas if l.diferencia > 0)


def resumen_para_revisar(session: Session, jornada: ConteoJornada) -> ResumenRevision:
    """Lo que Daniel ve antes de aplicar: cada talla contada y su diferencia."""
    from pos_uniformes.database.models import Producto, Variante

    filas = session.execute(
        select(
            Producto.nombre, Variante.talla,
            ConteoInventario.stock_sistema, ConteoInventario.stock_fisico, ConteoInventario.diferencia,
        )
        .join(Variante, Variante.id == ConteoInventario.variante_id)
        .join(Producto, Producto.id == Variante.producto_id)
        .where(ConteoInventario.jornada_id == jornada.id, ConteoInventario.ajustado.is_(False))
        .order_by(Producto.nombre, ConteoInventario.id)
    ).all()
    lineas = [LineaRevision(str(p), str(t or ""), int(s), int(f), int(d)) for p, t, s, f, d in filas]
    return ResumenRevision(
        jornada_id=jornada.id,
        titulo=jornada.titulo,
        quien=jornada.empleada_nombre or jornada.empleada_code,
        lineas=lineas,
    )


def aplicar_jornada(session: Session, jornada: ConteoJornada, *, revisada_por: str) -> tuple[int, int]:
    """Aplica al inventario TODAS las diferencias de la jornada. Solo el dueño.

    Devuelve (ajustados, omitidos) igual que `confirmar_ajustes_lote`.
    """
    from pos_uniformes.services.conteo_service import confirmar_ajustes_lote

    if (revisada_por or "").strip().upper() != DUENO_CODE:
        raise PermissionError("Solo el dueño aplica un conteo al inventario.")
    ids = list(
        session.scalars(
            select(ConteoInventario.id).where(
                ConteoInventario.jornada_id == jornada.id,
                ConteoInventario.ajustado.is_(False),
                ConteoInventario.diferencia != 0,
            )
        ).all()
    )
    ajustados, omitidos = confirmar_ajustes_lote(session, ids, revisada_por) if ids else (0, 0)
    jornada.revisada_at = func.now()
    jornada.revisada_por = revisada_por.strip().upper()
    session.add(jornada)
    session.flush()
    return ajustados, omitidos


def descartar_jornada(session: Session, jornada: ConteoJornada, *, revisada_por: str) -> None:
    """La marca revisada sin aplicar nada. Los renglones quedan como historia."""
    if (revisada_por or "").strip().upper() != DUENO_CODE:
        raise PermissionError("Solo el dueño descarta un conteo.")
    jornada.revisada_at = func.now()
    jornada.revisada_por = revisada_por.strip().upper()
    if jornada.terminada_at is None:
        jornada.terminada_at = func.now()
    session.add(jornada)
    session.flush()


def cuando(momento: datetime | None) -> str:
    """'hoy 10:20' / 'ayer 16:05' / '08/09 12:40' para las tarjetas."""
    if momento is None:
        return ""
    local = momento.astimezone() if momento.tzinfo else momento
    hoy = datetime.now().date()
    dias = (hoy - local.date()).days
    hora = local.strftime("%H:%M")
    if dias == 0:
        return f"hoy {hora}"
    if dias == 1:
        return f"ayer {hora}"
    return local.strftime("%d/%m ") + hora
