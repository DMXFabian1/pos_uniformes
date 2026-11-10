"""E4-A: programas y membresías (solo agrega).

- `programa` con Maximoda Club (lo inscribe la empleada), Maximoda
  Profesional y Maximoda Mayorista (los aprueba el dueño), ACTIVOS desde el
  inicio (P-E4-1) y sin vencimiento (P-E4-3).
- `membresia`: como máximo una activa y una pendiente por cliente (D1
  ajustada), garantizado por dos índices únicos parciales.
- `membresia_evento`: historial inmutable.

Una membresía no da descuento ni cambia precios (eso es E5). Ninguna tabla
existente cambia.

El `downgrade` se detiene si ya hay membresías, salvo
`POS_E4A_DOWNGRADE_ACEPTO_PERDIDA=1`.

Revision ID: 7741ff4c020d
Revises: 15f0e6fd053a
"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "7741ff4c020d"
down_revision = "15f0e6fd053a"
branch_labels = None
depends_on = None

ENV_ACEPTO_PERDIDA = "POS_E4A_DOWNGRADE_ACEPTO_PERDIDA"

PROGRAMAS_INICIALES = (
    {
        "clave": "CLUB",
        "nombre": "Maximoda Club",
        "descripcion": "Programa de entrada. Lo inscribe la empleada desde Venta Rápida.",
        "estado": "activo",
        "ingreso_modo": "directo_empleada",
        "tipo_sugerido_clave": None,
        "orden": 1,
    },
    {
        "clave": "PROFESIONAL",
        "nombre": "Maximoda Profesional",
        "descripcion": "Para docentes. Lo propone la empleada y lo aprueba el dueño.",
        "estado": "activo",
        "ingreso_modo": "aprobacion_dueno",
        "tipo_sugerido_clave": "DOCENTE",
        "orden": 2,
    },
    {
        "clave": "MAYORISTA",
        "nombre": "Maximoda Mayorista",
        "descripcion": "Para compras al mayoreo. Lo propone la empleada y lo aprueba el dueño.",
        "estado": "activo",
        "ingreso_modo": "aprobacion_dueno",
        "tipo_sugerido_clave": "MAYORISTA",
        "orden": 3,
    },
)


def _json():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    programa = op.create_table(
        "programa",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clave", sa.String(length=30), nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("ingreso_modo", sa.String(length=30), nullable=False),
        sa.Column("tipo_sugerido_clave", sa.String(length=30), nullable=True),
        sa.Column("vigencia_dias", sa.Integer(), nullable=True),
        sa.Column("orden", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("creado_por_usuario_id", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("clave", name="uq_programa_clave"),
        sa.CheckConstraint("estado IN ('borrador', 'activo', 'pausado', 'cerrado')", name="programa_estado_valido"),
        sa.CheckConstraint(
            "ingreso_modo IN ('directo_empleada', 'aprobacion_dueno')", name="programa_ingreso_modo_valido"
        ),
    )
    op.bulk_insert(programa, list(PROGRAMAS_INICIALES))

    op.create_table(
        "membresia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("cliente.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("programa_id", sa.Integer(), sa.ForeignKey("programa.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("desde", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hasta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("propuesta_por_employee_code", sa.String(length=40), nullable=True),
        sa.Column("motivo_propuesta", sa.String(length=255), nullable=True),
        sa.Column("alta_por_usuario_id", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("resuelta_por", sa.String(length=80), nullable=True),
        sa.Column("resuelta_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_resolucion", sa.String(length=255), nullable=True),
        sa.Column("recordatorios", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("ultimo_recordatorio_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("avisada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'activa', 'rechazada', 'expirada', 'cancelada', 'vencida', 'reemplazada')",
            name="membresia_estado_valido",
        ),
    )
    op.create_index("ix_membresia_cliente_id", "membresia", ["cliente_id"])
    op.create_index("ix_membresia_programa_id", "membresia", ["programa_id"])
    op.create_index("ix_membresia_estado", "membresia", ["estado"])
    op.create_index(
        "ux_membresia_una_activa_por_cliente",
        "membresia",
        ["cliente_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'activa'"),
        sqlite_where=sa.text("estado = 'activa'"),
    )
    op.create_index(
        "ux_membresia_una_pendiente_por_cliente",
        "membresia",
        ["cliente_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'pendiente'"),
        sqlite_where=sa.text("estado = 'pendiente'"),
    )

    op.create_table(
        "membresia_evento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("membresia_id", sa.Integer(), sa.ForeignKey("membresia.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("antes", sa.String(length=20), nullable=True),
        sa.Column("despues", sa.String(length=20), nullable=True),
        sa.Column("motivo", sa.String(length=255), nullable=True),
        sa.Column("detalle", _json(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("employee_code", sa.String(length=40), nullable=True),
        sa.Column("quien", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_membresia_evento_membresia_id", "membresia_evento", ["membresia_id"])
    op.create_index("ix_membresia_evento_created_at", "membresia_evento", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    membresias = bind.execute(sa.text("SELECT count(*) FROM membresia")).scalar_one()
    if membresias and os.environ.get(ENV_ACEPTO_PERDIDA) != "1":
        raise RuntimeError(
            f"Downgrade E4-A detenido: se perderían {membresias} membresía(s) y su historial. "
            f"Exporta esas tablas y, si aceptas la pérdida, repite con {ENV_ACEPTO_PERDIDA}=1."
        )
    op.drop_index("ix_membresia_evento_created_at", table_name="membresia_evento")
    op.drop_index("ix_membresia_evento_membresia_id", table_name="membresia_evento")
    op.drop_table("membresia_evento")
    op.drop_index("ux_membresia_una_pendiente_por_cliente", table_name="membresia")
    op.drop_index("ux_membresia_una_activa_por_cliente", table_name="membresia")
    op.drop_index("ix_membresia_estado", table_name="membresia")
    op.drop_index("ix_membresia_programa_id", table_name="membresia")
    op.drop_index("ix_membresia_cliente_id", table_name="membresia")
    op.drop_table("membresia")
    op.drop_table("programa")
