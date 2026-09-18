"""Imprimir la hoja de conteo abre (o se pega a) la jornada: cuántas hojas se
imprimieron y cuándo la última, para que nadie imprima la misma escuela dos
veces sin saberlo.

Revision ID: f06b7c8d9e0f
Revises: ef5a6b7c8d9e
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f06b7c8d9e0f"
down_revision = "ef5a6b7c8d9e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conteo_jornada", sa.Column("hojas_impresas", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("conteo_jornada", sa.Column("impresa_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("conteo_jornada", "impresa_at")
    op.drop_column("conteo_jornada", "hojas_impresas")
