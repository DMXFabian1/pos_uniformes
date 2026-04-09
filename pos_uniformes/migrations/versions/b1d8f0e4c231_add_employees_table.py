"""add employees table

Revision ID: b1d8f0e4c231
Revises: aa21c6e9f410
Create Date: 2026-04-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b1d8f0e4c231"
down_revision = "aa21c6e9f410"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "empleada",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=40), nullable=False),
        sa.Column("nombre_completo", sa.String(length=150), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )
    op.create_index(op.f("ix_empleada_codigo"), "empleada", ["codigo"], unique=False)
    op.create_index(op.f("ix_empleada_nombre_completo"), "empleada", ["nombre_completo"], unique=False)
    op.alter_column("empleada", "activo", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_empleada_nombre_completo"), table_name="empleada")
    op.drop_index(op.f("ix_empleada_codigo"), table_name="empleada")
    op.drop_table("empleada")
