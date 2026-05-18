"""add bodega_caja categoria column

Revision ID: c2d4e6f8a0b1
Revises: a1b3c5d7e9f0
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "c2d4e6f8a0b1"
down_revision = "a1b3c5d7e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bodega_caja",
        sa.Column("categoria", sa.String(1), nullable=False, server_default="A"),
    )
    op.create_index("ix_bodega_caja_categoria", "bodega_caja", ["categoria"])
    op.create_check_constraint(
        "bodega_caja_categoria_valida",
        "bodega_caja",
        "categoria IN ('A', 'B', 'C', 'D')",
    )


def downgrade() -> None:
    op.drop_constraint("bodega_caja_categoria_valida", "bodega_caja", type_="check")
    op.drop_index("ix_bodega_caja_categoria", table_name="bodega_caja")
    op.drop_column("bodega_caja", "categoria")
