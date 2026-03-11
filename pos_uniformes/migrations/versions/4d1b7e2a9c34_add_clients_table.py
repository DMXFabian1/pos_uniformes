"""add clients table

Revision ID: 4d1b7e2a9c34
Revises: 8a7f2c1e4d90
Create Date: 2026-03-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4d1b7e2a9c34"
down_revision = "8a7f2c1e4d90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cliente",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("telefono", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=120), nullable=True),
        sa.Column("direccion", sa.Text(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cliente_nombre"), "cliente", ["nombre"], unique=False)
    op.create_index(op.f("ix_cliente_telefono"), "cliente", ["telefono"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cliente_telefono"), table_name="cliente")
    op.drop_index(op.f("ix_cliente_nombre"), table_name="cliente")
    op.drop_table("cliente")
