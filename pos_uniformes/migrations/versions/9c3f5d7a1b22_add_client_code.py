"""add client code

Revision ID: 9c3f5d7a1b22
Revises: 7f2c4a1d9b55
Create Date: 2026-03-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c3f5d7a1b22"
down_revision = "7f2c4a1d9b55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cliente", sa.Column("codigo_cliente", sa.String(length=30), nullable=True))
    op.execute("UPDATE cliente SET codigo_cliente = 'CLI-' || LPAD(id::text, 6, '0') WHERE codigo_cliente IS NULL")
    op.alter_column("cliente", "codigo_cliente", nullable=False)
    op.create_index(op.f("ix_cliente_codigo_cliente"), "cliente", ["codigo_cliente"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_cliente_codigo_cliente"), table_name="cliente")
    op.drop_column("cliente", "codigo_cliente")
