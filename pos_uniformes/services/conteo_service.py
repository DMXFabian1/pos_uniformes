"""Servicios para el módulo de conteo físico de inventario.

Permite registrar conteos por variante, comparar contra stock del sistema,
y confirmar ajustes con auditoría completa vía InventarioService.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from pos_uniformes.database.models import (
    AjusteInventarioLote,
    AjusteInventarioLoteDetalle,
    ConfigConteoEscuela,
    ConteoInventario,
    Escuela,
    MovimientoInventario,
    Producto,
    TipoMovimientoInventario,
    Variante,
)

DIAS_VIGENCIA_DEFAULT = 90


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConteoInput:
    variante_id: int
    stock_fisico: int
    notas: str | None = None


@dataclass(frozen=True)
class VarianteParaConteo:
    variante_id: int
    sku: str
    producto_nombre: str
    talla: str
    color: str
    stock_actual: int
    ultimo_conteo_at: datetime | None
    dias_desde_conteo: int | None
    requiere_conteo: bool


@dataclass(frozen=True)
class EstadoConteoEscuela:
    escuela_id: int
    escuela_nombre: str
    dias_vigencia: int
    total_variantes: int
    contadas_vigentes: int
    pendientes_conteo: int
    ultimo_conteo: datetime | None
    pct_vigente: int


@dataclass(frozen=True)
class ConteoResultado:
    total_contados: int
    con_diferencia: int
    sin_diferencia: int


# ---------------------------------------------------------------------------
# Registrar conteos
# ---------------------------------------------------------------------------

def registrar_conteo(
    session: Session,
    variante_id: int,
    stock_fisico: int,
    contado_por: str,
    notas: str | None = None,
) -> ConteoInventario:
    """Registra un conteo físico para una variante. NO ajusta stock."""
    variante = session.scalar(
        select(Variante)
        .options(joinedload(Variante.producto))
        .where(Variante.id == variante_id)
        .with_for_update()
    )
    if variante is None:
        raise ValueError(f"Variante id={variante_id} no encontrada.")

    stock_sistema = variante.stock_actual
    diferencia = stock_fisico - stock_sistema

    conteo = ConteoInventario(
        variante_id=variante_id,
        escuela_id=variante.producto.escuela_id,
        stock_sistema=stock_sistema,
        stock_fisico=stock_fisico,
        diferencia=diferencia,
        ajustado=False,
        contado_por=contado_por.strip(),
        notas=notas.strip() if notas else None,
    )
    session.add(conteo)

    # Actualizar timestamp de último conteo en la variante
    variante.ultimo_conteo_at = func.now()
    session.add(variante)

    return conteo


def registrar_conteos_lote(
    session: Session,
    conteos: list[ConteoInput],
    contado_por: str,
) -> ConteoResultado:
    """Registra conteos para múltiples variantes en una transacción."""
    if not conteos:
        raise ValueError("No hay conteos para registrar.")
    if not contado_por or not contado_por.strip():
        raise ValueError("Debe indicar quién realizó el conteo.")

    con_diferencia = 0
    sin_diferencia = 0

    for ci in conteos:
        conteo = registrar_conteo(
            session,
            variante_id=ci.variante_id,
            stock_fisico=ci.stock_fisico,
            contado_por=contado_por,
            notas=ci.notas,
        )
        if conteo.diferencia != 0:
            con_diferencia += 1
        else:
            sin_diferencia += 1

    return ConteoResultado(
        total_contados=len(conteos),
        con_diferencia=con_diferencia,
        sin_diferencia=sin_diferencia,
    )


# ---------------------------------------------------------------------------
# Confirmar ajustes
# ---------------------------------------------------------------------------

def confirmar_ajustes_lote(
    session: Session,
    conteo_ids: list[int],
    usuario_nombre: str,
) -> tuple[int, int]:
    """Aplica diferencias de conteos pendientes al stock.

    Crea un MovimientoInventario por cada ajuste para auditoría completa.
    Retorna (ajustados, omitidos).
    """
    if not conteo_ids:
        raise ValueError("No hay conteos seleccionados.")

    conteos = session.scalars(
        select(ConteoInventario)
        .options(joinedload(ConteoInventario.variante))
        .where(
            ConteoInventario.id.in_(conteo_ids),
            ConteoInventario.ajustado.is_(False),
        )
    ).all()

    ajustados = 0
    omitidos = 0

    for conteo in conteos:
        if conteo.diferencia == 0:
            conteo.ajustado = True
            omitidos += 1
            continue

        variante = session.scalar(
            select(Variante).where(Variante.id == conteo.variante_id).with_for_update()
        )
        if variante is None:
            omitidos += 1
            continue

        stock_anterior = variante.stock_actual
        cantidad = conteo.diferencia  # positivo=faltaba, negativo=sobraba

        tipo = (
            TipoMovimientoInventario.AJUSTE_ENTRADA
            if cantidad > 0
            else TipoMovimientoInventario.AJUSTE_SALIDA
        )

        variante.stock_actual = stock_anterior + cantidad
        movimiento = MovimientoInventario(
            variante=variante,
            tipo_movimiento=tipo,
            cantidad=cantidad,
            stock_anterior=stock_anterior,
            stock_posterior=variante.stock_actual,
            referencia=f"CONTEO-{conteo.id}",
            observacion=f"Ajuste por conteo físico (contó: {conteo.contado_por})",
            creado_por=usuario_nombre,
        )
        session.add(movimiento)
        session.add(variante)

        conteo.ajustado = True
        ajustados += 1

    return ajustados, omitidos


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def obtener_variantes_para_conteo(
    session: Session,
    escuela_id: int,
) -> list[VarianteParaConteo]:
    """Variantes activas de una escuela, ordenadas por urgencia de conteo."""
    config = session.scalar(
        select(ConfigConteoEscuela).where(ConfigConteoEscuela.escuela_id == escuela_id)
    )
    dias_vigencia = config.dias_vigencia if config else DIAS_VIGENCIA_DEFAULT

    variantes = session.scalars(
        select(Variante)
        .join(Variante.producto)
        .where(
            Producto.escuela_id == escuela_id,
            Producto.activo.is_(True),
            Variante.activo.is_(True),
        )
        .order_by(
            Variante.ultimo_conteo_at.asc().nulls_first(),
            Producto.nombre,
            Variante.talla,
        )
    ).all()

    ahora = datetime.now(timezone.utc)
    resultado: list[VarianteParaConteo] = []

    for v in variantes:
        if v.ultimo_conteo_at is not None:
            dias = (ahora - v.ultimo_conteo_at).days
            requiere = dias >= dias_vigencia
        else:
            dias = None
            requiere = True

        resultado.append(VarianteParaConteo(
            variante_id=v.id,
            sku=v.sku,
            producto_nombre=v.producto.nombre,
            talla=v.talla,
            color=v.color,
            stock_actual=v.stock_actual,
            ultimo_conteo_at=v.ultimo_conteo_at,
            dias_desde_conteo=dias,
            requiere_conteo=requiere,
        ))

    return resultado


def obtener_conteos_pendientes(
    session: Session,
    escuela_id: int | None = None,
) -> list[ConteoInventario]:
    """Conteos con diferencia != 0 que aún no se han ajustado."""
    stmt = (
        select(ConteoInventario)
        .options(joinedload(ConteoInventario.variante).joinedload(Variante.producto))
        .where(
            ConteoInventario.ajustado.is_(False),
            ConteoInventario.diferencia != 0,
        )
        .order_by(ConteoInventario.contado_at.desc())
    )
    if escuela_id is not None:
        stmt = stmt.where(ConteoInventario.escuela_id == escuela_id)

    return list(session.scalars(stmt).all())


def obtener_historial_conteos(
    session: Session,
    escuela_id: int,
    limite: int = 50,
) -> list[ConteoInventario]:
    """Últimos conteos de una escuela."""
    return list(session.scalars(
        select(ConteoInventario)
        .options(joinedload(ConteoInventario.variante))
        .where(ConteoInventario.escuela_id == escuela_id)
        .order_by(ConteoInventario.contado_at.desc())
        .limit(limite)
    ).all())


def obtener_estado_conteo_escuela(
    session: Session,
    escuela_id: int,
) -> EstadoConteoEscuela:
    """Resumen del estado de conteo para una escuela."""
    escuela = session.scalar(select(Escuela).where(Escuela.id == escuela_id))
    if escuela is None:
        raise ValueError(f"Escuela id={escuela_id} no encontrada.")

    config = session.scalar(
        select(ConfigConteoEscuela).where(ConfigConteoEscuela.escuela_id == escuela_id)
    )
    dias_vigencia = config.dias_vigencia if config else DIAS_VIGENCIA_DEFAULT

    # Total variantes activas
    total = session.scalar(
        select(func.count(Variante.id))
        .join(Variante.producto)
        .where(
            Producto.escuela_id == escuela_id,
            Producto.activo.is_(True),
            Variante.activo.is_(True),
        )
    ) or 0

    # Contadas dentro de vigencia
    limite_fecha = datetime.now(timezone.utc) - timedelta(days=dias_vigencia)
    contadas_vigentes = session.scalar(
        select(func.count(Variante.id))
        .join(Variante.producto)
        .where(
            Producto.escuela_id == escuela_id,
            Producto.activo.is_(True),
            Variante.activo.is_(True),
            Variante.ultimo_conteo_at.isnot(None),
            Variante.ultimo_conteo_at >= limite_fecha,
        )
    ) or 0

    # Último conteo
    ultimo = session.scalar(
        select(func.max(ConteoInventario.contado_at))
        .where(ConteoInventario.escuela_id == escuela_id)
    )

    pendientes = total - contadas_vigentes
    pct = round(contadas_vigentes / total * 100) if total > 0 else 0

    return EstadoConteoEscuela(
        escuela_id=escuela_id,
        escuela_nombre=escuela.nombre,
        dias_vigencia=dias_vigencia,
        total_variantes=total,
        contadas_vigentes=contadas_vigentes,
        pendientes_conteo=pendientes,
        ultimo_conteo=ultimo,
        pct_vigente=pct,
    )


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

def guardar_config_conteo(
    session: Session,
    escuela_id: int,
    dias_vigencia: int,
) -> ConfigConteoEscuela:
    """Crea o actualiza la configuración de conteo de una escuela."""
    if dias_vigencia < 1:
        raise ValueError("Los días de vigencia deben ser al menos 1.")

    config = session.scalar(
        select(ConfigConteoEscuela).where(ConfigConteoEscuela.escuela_id == escuela_id)
    )
    if config is None:
        config = ConfigConteoEscuela(escuela_id=escuela_id, dias_vigencia=dias_vigencia)
        session.add(config)
    else:
        config.dias_vigencia = dias_vigencia

    return config
