"""Catálogo, fase 2: el uniforme como entidad. `uniforme` (uno por escuela)
y `uniforme_pieza` (qué producto, grupo Diario/Deportivo, orden, obligatoria,
color). Los productos y SKUs no cambian; la pieza solo los señala.
Daniel, 2026-09-21. Ver Obsidian 38.

Revision ID: 1c2d3e4f5a6b
Revises: 0b1c2d3e4f5a
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "1c2d3e4f5a6b"
down_revision = "0b1c2d3e4f5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "uniforme",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escuela_id", sa.Integer(), sa.ForeignKey("escuela.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("nivel_educativo_id", sa.Integer(), sa.ForeignKey("nivel_educativo.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("nombre", sa.String(length=80), nullable=False, server_default="Uniforme"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("escuela_id", "nombre", name="uq_uniforme_escuela_nombre"),
    )
    op.create_index("ix_uniforme_escuela_id", "uniforme", ["escuela_id"])
    op.create_index("ix_uniforme_nivel_educativo_id", "uniforme", ["nivel_educativo_id"])

    op.create_table(
        "uniforme_pieza",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uniforme_id", sa.Integer(), sa.ForeignKey("uniforme.id", ondelete="CASCADE"), nullable=False),
        sa.Column("producto_id", sa.Integer(), sa.ForeignKey("producto.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("grupo", sa.String(length=30), nullable=False, server_default="Diario"),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("obligatoria", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("color", sa.String(length=50), nullable=True),
        sa.Column("nota", sa.String(length=200), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("uniforme_id", "producto_id", name="uq_uniforme_pieza_producto"),
    )
    op.create_index("ix_uniforme_pieza_uniforme_id", "uniforme_pieza", ["uniforme_id"])
    op.create_index("ix_uniforme_pieza_producto_id", "uniforme_pieza", ["producto_id"])


def downgrade() -> None:
    op.drop_table("uniforme_pieza")
    op.drop_table("uniforme")
