"""add sale discount fields

Revision ID: d91f3a7c2b44
Revises: c4b8d91e7f10
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d91f3a7c2b44"
down_revision = "7c2a4b9d6e11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "venta",
        sa.Column("descuento_porcentaje", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
    )
    op.add_column(
        "venta",
        sa.Column("descuento_monto", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
    )


def downgrade() -> None:
    op.drop_column("venta", "descuento_monto")
    op.drop_column("venta", "descuento_porcentaje")
