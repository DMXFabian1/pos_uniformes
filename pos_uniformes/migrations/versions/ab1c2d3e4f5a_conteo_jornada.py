"""Jornada de conteo: quién, qué y cuándo; conteos ligados a su jornada.

Revision ID: ab1c2d3e4f5a
Revises: z9b0c1d2e3f4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ab1c2d3e4f5a"
down_revision = "z9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conteo_jornada",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "escuela_id",
            sa.Integer(),
            sa.ForeignKey("escuela.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("tipo_pieza", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("titulo", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("empleada_code", sa.String(length=40), nullable=False),
        sa.Column("empleada_nombre", sa.String(length=120), nullable=False, server_default=""),
        sa.Column(
            "iniciada_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("terminada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revisada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revisada_por", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("total_tallas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notas", sa.Text(), nullable=True),
    )
    op.create_index("ix_conteo_jornada_escuela_id", "conteo_jornada", ["escuela_id"])
    op.create_index("ix_conteo_jornada_empleada_code", "conteo_jornada", ["empleada_code"])
    op.create_index("ix_conteo_jornada_iniciada_at", "conteo_jornada", ["iniciada_at"])
    op.create_index("ix_conteo_jornada_terminada_at", "conteo_jornada", ["terminada_at"])

    op.add_column(
        "conteo_inventario",
        sa.Column(
            "jornada_id",
            sa.Integer(),
            sa.ForeignKey("conteo_jornada.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_conteo_inventario_jornada_id", "conteo_inventario", ["jornada_id"])


def downgrade() -> None:
    op.drop_index("ix_conteo_inventario_jornada_id", table_name="conteo_inventario")
    op.drop_column("conteo_inventario", "jornada_id")
    for nombre in ("terminada_at", "iniciada_at", "empleada_code", "escuela_id"):
        op.drop_index(f"ix_conteo_jornada_{nombre}", table_name="conteo_jornada")
    op.drop_table("conteo_jornada")
