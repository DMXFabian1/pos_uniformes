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
    tipo_pieza: str
    talla: str
    color: str
    stock_actual: int
    stock_bodega: int
    stock_piso: int
    stock_tienda: int
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

    stock_sistema = variante.stock_tienda
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
        .options(joinedload(Variante.producto).joinedload(Producto.tipo_pieza))
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
    ).unique().all()

    ahora = datetime.now(timezone.utc)
    resultado: list[VarianteParaConteo] = []

    for v in variantes:
        if v.ultimo_conteo_at is not None:
            dias = (ahora - v.ultimo_conteo_at).days
            requiere = dias >= dias_vigencia
        else:
            dias = None
            requiere = True

        tipo_nombre = v.producto.tipo_pieza.nombre if v.producto.tipo_pieza else ""

        resultado.append(VarianteParaConteo(
            variante_id=v.id,
            sku=v.sku,
            producto_nombre=v.producto.nombre,
            tipo_pieza=tipo_nombre,
            talla=v.talla,
            color=v.color,
            stock_actual=v.stock_actual,
            stock_bodega=v.stock_bodega,
            stock_piso=v.stock_piso,
            stock_tienda=v.stock_tienda,
            ultimo_conteo_at=v.ultimo_conteo_at,
            dias_desde_conteo=dias,
            requiere_conteo=requiere,
        ))

    return resultado


_PIEZA_ORDER = {
    "Pants 3pz": 1, "Pants 2pz": 2, "Pants Suelto": 3, "Chamarra": 4,
    "Playera": 5, "Suéter": 6, "Camisa": 7, "Chaleco": 8, "Falda": 9,
    "Jumper": 10, "Blusa": 11, "Short": 12, "Pantalón": 13, "Malla": 14,
    "Calceta": 15, "Corbata": 16, "Corbatín": 17, "Moño": 18,
    "Mascada": 19, "Boina": 20, "Guante": 21, "Bata": 22, "Jeans": 23,
}

_TIPOS_VIRTUALES = {"Pants 3pz", "Chamarra"}


def obtener_variantes_agrupadas_por_producto(
    session: Session,
    escuela_id: int,
) -> list[dict]:
    """Variantes agrupadas por producto, ordenadas según PIEZA_ORDER."""
    variantes = obtener_variantes_para_conteo(session, escuela_id)
    grupos: dict[str, dict] = {}
    for v in variantes:
        key = v.producto_nombre
        if key not in grupos:
            grupos[key] = {
                "producto_nombre": key,
                "tipo_pieza": v.tipo_pieza,
                "virtual": v.tipo_pieza in _TIPOS_VIRTUALES,
                "variantes": [],
            }
        grupos[key]["variantes"].append(v)

    def _talla_sort_key(v: VarianteParaConteo):
        """Ordena tallas: numéricas (4,6,8...) luego letra (CH,MD,GD,EXG)."""
        t = v.talla.strip().upper()
        # Tallas numéricas con sufijo (4CH, 6CH, etc.)
        if len(t) > 2 and t[:-2].isdigit():
            return (0, int(t[:-2]), t)
        # Tallas numéricas puras
        try:
            return (1, int(t), "")
        except ValueError:
            pass
        # Tallas con letra: CH, MD, GD, EXG, XS, S, M, L, XL, XXL
        letra_order = {
            "CH": 0, "MD": 1, "GD": 2, "EXG": 3,
            "XXS": 4, "XS": 5, "S": 6, "M": 7, "L": 8, "XL": 9, "XXL": 10,
        }
        return (2, letra_order.get(t, 99), t)

    # Ordenar variantes por talla dentro de cada grupo
    for g in grupos.values():
        g["variantes"].sort(key=_talla_sort_key)

    # Ordenar grupos por PIEZA_ORDER, luego por nombre de producto
    resultado = sorted(
        grupos.values(),
        key=lambda g: (_PIEZA_ORDER.get(g["tipo_pieza"], 99), g["producto_nombre"]),
    )
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
