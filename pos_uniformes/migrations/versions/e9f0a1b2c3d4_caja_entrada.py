"""Entradas al cajón que no son venta: tabla `caja_entrada`.

El papá de Daniel deja un fondo para cubrir la nómina (2026-10-20: $1,750
un domingo). Los pagos siguen saliendo del cajón; esto entra y el corte lo
suma al esperado. Solo crea la tabla.

Revision ID: e9f0a1b2c3d4
Revises: f7e8d9c0b1a2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e9f0a1b2c3d4"
down_revision = "f7e8d9c0b1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "caja_entrada",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.String(120), nullable=False, server_default=""),
        sa.Column("creado_por", sa.String(40), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_caja_entrada_created_at", "caja_entrada", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_caja_entrada_created_at", table_name="caja_entrada")
    op.drop_table("caja_entrada")
