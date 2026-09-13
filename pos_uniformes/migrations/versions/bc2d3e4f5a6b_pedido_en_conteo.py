"""Lo que Daniel decide pedir al revisar un conteo, junto a lo que se le sugirió.

Revision ID: bc2d3e4f5a6b
Revises: ab1c2d3e4f5a
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "bc2d3e4f5a6b"
down_revision = "ab1c2d3e4f5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conteo_inventario", sa.Column("pedido_sugerido", sa.Integer(), nullable=True))
    op.add_column("conteo_inventario", sa.Column("pedido", sa.Integer(), nullable=True))
    op.add_column("conteo_inventario", sa.Column("pedido_decidido_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("conteo_inventario", "pedido_decidido_at")
    op.drop_column("conteo_inventario", "pedido")
    op.drop_column("conteo_inventario", "pedido_sugerido")
