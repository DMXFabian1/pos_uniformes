"""link clients to layaways

Revision ID: b6d2e91c4a10
Revises: a1c8d4e7b233
Create Date: 2026-03-11 19:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b6d2e91c4a10"
down_revision = "a1c8d4e7b233"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("apartado", sa.Column("cliente_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_apartado_cliente_id"), "apartado", ["cliente_id"], unique=False)
    op.create_foreign_key(
        "fk_apartado_cliente_id_cliente",
        "apartado",
        "cliente",
        ["cliente_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_apartado_cliente_id_cliente", "apartado", type_="foreignkey")
    op.drop_index(op.f("ix_apartado_cliente_id"), table_name="apartado")
    op.drop_column("apartado", "cliente_id")
