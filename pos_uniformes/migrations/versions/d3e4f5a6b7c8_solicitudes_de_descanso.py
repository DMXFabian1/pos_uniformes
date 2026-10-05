"""Solicitudes de descanso: la empleada pide un día, Daniel lo aprueba desde el
celular viendo cómo queda la semana.

Tabla aparte y NO un evento del calendario a propósito: un descanso pedido no
es un descanso. Si se escribiera en `empleada_evento` desde que se pide, el
calendario lo pintaría como día libre, la nómina dejaría de contar ese día y
el detector de posibles faltas se callaría — todo eso antes de que nadie
autorice nada. El evento se escribe al aprobar.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solicitud_descanso",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_code", sa.String(length=40), nullable=False, index=True),
        sa.Column("employee_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("fecha", sa.Date(), nullable=False, index=True),
        sa.Column("motivo", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="pedido", index=True),
        sa.Column("resuelto_por", sa.String(length=40), nullable=True),
        sa.Column("resuelto_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("respuesta", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "estado IN ('pedido', 'aprobado', 'rechazado', 'cancelado')",
            name="solicitud_descanso_estado_valido",
        ),
    )
    # Dos solicitudes vivas para el mismo día de la misma persona no significan
    # nada: es la misma petición mandada dos veces.
    op.create_index(
        "ix_solicitud_descanso_una_viva",
        "solicitud_descanso",
        ["employee_code", "fecha"],
        unique=True,
        postgresql_where=sa.text("estado = 'pedido'"),
        sqlite_where=sa.text("estado = 'pedido'"),
    )


def downgrade() -> None:
    op.drop_index("ix_solicitud_descanso_una_viva", table_name="solicitud_descanso")
    op.drop_table("solicitud_descanso")
