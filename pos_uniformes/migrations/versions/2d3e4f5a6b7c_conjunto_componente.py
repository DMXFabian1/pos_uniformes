"""Catálogo, fase 3: receta de los productos artificiales (Pants 3pz =
Pants 2pz + Playera; Chamarra = sale de un Pants 2pz y deja un Pants Suelto).
Daniel, 2026-09-21: "un pants 3pz no es más que un 2pz y una playera, y la
chamarra es una que le quito a un pants 2pz". Ver Obsidian 38 §5b.

Revision ID: 2d3e4f5a6b7c
Revises: 1c2d3e4f5a6b
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2d3e4f5a6b7c"
down_revision = "1c2d3e4f5a6b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conjunto_componente",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conjunto_id", sa.Integer(), sa.ForeignKey("producto.id", ondelete="CASCADE"), nullable=False),
        sa.Column("componente_id", sa.Integer(), sa.ForeignKey("producto.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("grupo", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("conjunto_id", "componente_id", name="uq_conjunto_componente"),
        sa.CheckConstraint("cantidad <> 0", name="conjunto_componente_cantidad_no_cero"),
    )
    op.create_index("ix_conjunto_componente_conjunto_id", "conjunto_componente", ["conjunto_id"])
    op.create_index("ix_conjunto_componente_componente_id", "conjunto_componente", ["componente_id"])


def downgrade() -> None:
    op.drop_table("conjunto_componente")
