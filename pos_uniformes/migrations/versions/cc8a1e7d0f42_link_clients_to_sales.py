"""link clients to sales

Revision ID: cc8a1e7d0f42
Revises: b6d2e91c4a10
Create Date: 2026-03-11 20:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "cc8a1e7d0f42"
down_revision = "b6d2e91c4a10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("venta", sa.Column("cliente_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_venta_cliente_id"), "venta", ["cliente_id"], unique=False)
    op.create_foreign_key(
        "fk_venta_cliente_id_cliente",
        "venta",
        "cliente",
        ["cliente_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_venta_cliente_id_cliente", "venta", type_="foreignkey")
    op.drop_index(op.f("ix_venta_cliente_id"), table_name="venta")
    op.drop_column("venta", "cliente_id")
