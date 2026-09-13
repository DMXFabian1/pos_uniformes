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
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import ConteoInventario, ConteoJornada, Escuela

DUENO_CODE = "VEND-1"
# Marca en `notas` de una jornada que el dueño descartó (sin aplicar).
DESCARTADA = "descartada"


class JornadaAjena(Exception):
    """Ya no se lanza (2026-09-13): la jornada es de la escuela, no de quien la
    abrió. Se conserva por si algún código viejo la captura."""


class JornadaEnProceso(Exception):
    """Esa escuela (o prenda de básicos) ya tiene una jornada abierta. Trae la
    jornada para que la pantalla ofrezca seguirla en vez de abrir otra."""

    def __init__(self, jornada: "ConteoJornada") -> None:
        self.jornada = jornada
        super().__init__(f"{jornada.titulo} ya la está contando {jornada.empleada_nombre or jornada.empleada_code}.")


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
    revisada_at: datetime | None = None
    aplicada: bool = True   # False = el dueño la descartó

    @property
    def quien(self) -> str:
        return self.empleada_nombre or self.empleada_code

    @property
    def estado(self) -> str:
        return estado_de(self)


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
        revisada_at=jornada.revisada_at,
        aplicada=(jornada.notas or "") != DESCARTADA,
    )


def alcance(session: Session, escuela_id: int | None, tipo_pieza: str = "") -> list[dict]:
    """Los grupos producto→tallas de una escuela (o prenda básica), en el
    orden que comparten la pantalla de captura y la hoja de papel.

    Es UNA sola función a propósito: si la hoja dice "7. Suéter Cuello V" y la
    pantalla dice "7. Suéter Cuello V", es porque las dos preguntaron aquí.
    """
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
    """Abre una jornada nueva y deja anotado cuántas tallas abarca.

    Una sola abierta por escuela (o prenda de básicos): si ya hay una, lanza
    `JornadaEnProceso` con ella, para que quien llega la siga y no se pisen.
    """
    if not empleada_code or not empleada_code.strip():
        raise ValueError("Una jornada necesita el gafete de quien cuenta.")
    abierta = jornada_abierta_de(session, escuela_id, tipo_pieza)
    if abierta is not None:
        raise JornadaEnProceso(abierta)
    grupos = alcance(session, escuela_id, tipo_pieza)
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


def jornada_abierta_de(session: Session, escuela_id: int | None, tipo_pieza: str = "") -> ConteoJornada | None:
    """La jornada sin terminar de esa escuela (o prenda de básicos), si hay."""
    q = select(ConteoJornada).where(ConteoJornada.terminada_at.is_(None))
    if escuela_id is None:
        q = q.where(ConteoJornada.escuela_id.is_(None), ConteoJornada.tipo_pieza == (tipo_pieza or "").strip())
    else:
        q = q.where(ConteoJornada.escuela_id == escuela_id)
    return session.scalars(q.order_by(ConteoJornada.iniciada_at.desc())).first()


def abiertas_por_alcance(session: Session) -> dict:
    """{escuela_id | ("basicos", tipo_pieza): jornada abierta} para marcar
    "en proceso" en los selectores."""
    out: dict = {}
    for j in jornadas_abiertas(session):
        clave = ("basicos", j.tipo_pieza) if j.escuela_id is None else j.escuela_id
        out.setdefault(clave, j)
    return out


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


def jornadas_recientes(session: Session, *, limite: int = 8) -> list[ConteoJornada]:
    """Las últimas terminadas (aplicadas, descartadas o por revisar), para el historial."""
    return list(
        session.scalars(
            select(ConteoJornada)
            .where(ConteoJornada.terminada_at.is_not(None))
            .order_by(ConteoJornada.terminada_at.desc())
            .limit(limite)
        ).all()
    )


def estado_de(jornada) -> str:
    """'Por revisar' / 'Aplicada' / 'Descartada' / 'A medias'. Vale con JornadaRef."""
    terminada = getattr(jornada, "terminada_at", None)
    revisada = getattr(jornada, "revisada_at", None)
    if terminada is None:
        return "A medias"
    if revisada is None:
        return "Por revisar"
    return "Aplicada" if getattr(jornada, "aplicada", True) else "Descartada"


def puede_seguirla(jornada: ConteoJornada, empleada_code: str) -> bool:
    """Cualquiera con gafete. La jornada es de la escuela, no de quien la
    abrió: da igual con qué sesión se imprimió la hoja, cada talla guarda
    quién la contó (`contado_por`)."""
    return bool((empleada_code or "").strip())


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


def guardar_tallas(
    session: Session,
    jornada: ConteoJornada,
    items: list[dict],
    *,
    contado_por: str,
) -> int:
    """Guarda tallas de una jornada como se llena una hoja: se puede corregir.

    `items`: [{"variante_id": int, "fisico": int | None, "pedido": int | None}].
    - fisico None o vacío = "no la conté": si había renglón, se borra; si no, nada.
    - Si la talla ya tenía renglón en ESTA jornada, se actualiza (no se
      duplica: la revisión de Daniel vería dos veces la misma talla).
    - `pedido` (cuántas pedir) va en `notas` como "Pedido: N".
    Devuelve cuántas tallas quedaron guardadas.
    """
    from pos_uniformes.database.models import Variante
    from pos_uniformes.services.conteo_service import registrar_conteo

    guardadas = 0
    for item in items:
        vid = int(item.get("variante_id"))
        fisico = item.get("fisico")
        pedido = item.get("pedido")
        nota = f"Pedido: {int(pedido)}" if pedido not in (None, "") else None
        existente = session.scalar(
            select(ConteoInventario).where(
                ConteoInventario.jornada_id == jornada.id, ConteoInventario.variante_id == vid
            )
        )
        if fisico in (None, ""):
            if existente is not None and not existente.ajustado:
                session.delete(existente)
            continue
        fisico = int(fisico)
        if existente is None:
            registrar_conteo(session, vid, fisico, contado_por, notas=nota, jornada_id=jornada.id)
        elif not existente.ajustado:
            existente.stock_fisico = fisico
            existente.diferencia = fisico - int(existente.stock_sistema)
            existente.notas = nota
            existente.contado_at = func.now()
            existente.contado_por = contado_por
            session.add(existente)
        guardadas += 1
    session.flush()
    return guardadas


def hoja_de_jornada(session: Session, jornada: ConteoJornada) -> dict:
    """La hoja tal como se dibuja: prendas numeradas, cada una con sus tallas
    y lo ya capturado. Es lo que consume el celular."""
    filas = session.execute(
        select(ConteoInventario.variante_id, ConteoInventario.stock_fisico, ConteoInventario.notas)
        .where(ConteoInventario.jornada_id == jornada.id)
    ).all()
    capturado = {}
    for vid, fisico, notas in filas:
        pedido = None
        if notas and str(notas).startswith("Pedido:"):
            try:
                pedido = int(str(notas).split(":", 1)[1])
            except ValueError:
                pedido = None
        capturado[int(vid)] = (int(fisico), pedido)
    grupos = alcance(session, jornada.escuela_id, jornada.tipo_pieza)
    prendas = []
    for numero, g in enumerate(grupos, 1):
        tallas = []
        for v in g["variantes"]:
            fisico, pedido = capturado.get(v.variante_id, (None, None))
            tallas.append({
                "variante_id": v.variante_id, "talla": str(v.talla or "U"),
                "color": str(getattr(v, "color", "") or ""), "fisico": fisico, "pedido": pedido,
            })
        prendas.append({
            "numero": numero, "total": len(grupos),
            "nombre": str(g["producto_nombre"]).split(" | ")[0].strip(),
            "tipo_pieza": str(g.get("tipo_pieza") or ""),
            "tallas": tallas,
            "completa": bool(tallas) and all(t["fisico"] is not None for t in tallas),
        })
    a = avance(session, jornada)
    return {
        "jornada": _dict_ref(ref(jornada)),
        "avance": {"tallas_hechas": a.tallas_hechas, "tallas_total": a.tallas_total,
                   "prendas_hechas": a.prendas_hechas, "prendas_total": a.prendas_total},
        "prendas": prendas,
    }


def _dict_ref(r: "JornadaRef") -> dict:
    return {
        "id": r.id, "titulo": r.titulo, "escuela_id": r.escuela_id, "tipo_pieza": r.tipo_pieza,
        "empleada_code": r.empleada_code, "empleada_nombre": r.empleada_nombre,
        "iniciada_at": r.iniciada_at.isoformat() if r.iniciada_at else None,
        "terminada_at": r.terminada_at.isoformat() if r.terminada_at else None,
        "estado": r.estado, "cuando": cuando(r.terminada_at or r.iniciada_at),
    }


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
    grupos = alcance(session, jornada.escuela_id, jornada.tipo_pieza)
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
        raise ValueError("Para terminar una jornada hace falta el gafete.")
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
    jornada.notas = DESCARTADA
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


# ─── ¿Cuándo se contó por última vez? ───────────────────────────────────
@dataclass(frozen=True)
class UltimoConteo:
    fecha: datetime | None      # None = nunca
    quien: str = ""             # nombre de quien terminó la última jornada (si la hubo)

    def texto(self, hoy: date | None = None) -> str:
        """'hoy', 'ayer', 'hace 3 días', 'hace 2 meses' o 'nunca'."""
        if self.fecha is None:
            return "nunca"
        hoy = hoy or date.today()
        f = self.fecha.astimezone().date() if self.fecha.tzinfo else self.fecha.date()
        dias = (hoy - f).days
        if dias <= 0:
            base = "hoy"
        elif dias == 1:
            base = "ayer"
        elif dias < 30:
            base = f"hace {dias} días"
        elif dias < 365:
            m = dias // 30
            base = "hace 1 mes" if m == 1 else f"hace {m} meses"
        else:
            base = f"hace más de {dias // 365} año" + ("s" if dias // 365 > 1 else "")
        return f"{base} ({self.quien.split()[0]})" if self.quien else base


def ultimos_conteos(session: Session) -> dict:
    """Cuándo se contó cada escuela (y cada prenda básica) por última vez.

    Claves: `escuela_id` (int) para escuelas y `("basicos", tipo_pieza)` para
    básicos. Primero manda la última **jornada terminada** (trae quién);
    si una escuela nunca tuvo jornada, se cae a la fecha de conteo más
    reciente de sus tallas (los conteos de antes de las jornadas).
    """
    from pos_uniformes.database.models import Producto, Variante

    salida: dict = {}
    # 1. Jornadas terminadas: la más reciente por escuela / prenda básica.
    filas = session.execute(
        select(ConteoJornada.escuela_id, ConteoJornada.tipo_pieza, ConteoJornada.empleada_nombre,
               ConteoJornada.empleada_code, ConteoJornada.terminada_at)
        .where(ConteoJornada.terminada_at.is_not(None))
        .order_by(ConteoJornada.terminada_at.desc())
    ).all()
    for escuela_id, tipo_pieza, nombre, code, terminada in filas:
        clave = int(escuela_id) if escuela_id is not None else ("basicos", str(tipo_pieza or ""))
        if clave not in salida:
            salida[clave] = UltimoConteo(terminada, nombre or code or "")
    # 2. Conteos viejos (sin jornada): la talla contada más recientemente.
    viejos = session.execute(
        select(Producto.escuela_id, func.max(Variante.ultimo_conteo_at))
        .join(Variante, Variante.producto_id == Producto.id)
        .where(Producto.escuela_id.is_not(None), Variante.ultimo_conteo_at.is_not(None))
        .group_by(Producto.escuela_id)
    ).all()
    for escuela_id, fecha in viejos:
        clave = int(escuela_id)
        if clave not in salida and fecha is not None:
            salida[clave] = UltimoConteo(fecha, "")
    return salida


def ultimo_conteo_de(ultimos: dict, escuela_id: int | None, tipo_pieza: str = "") -> UltimoConteo:
    clave = int(escuela_id) if escuela_id is not None else ("basicos", tipo_pieza or "")
    return ultimos.get(clave, UltimoConteo(None))
