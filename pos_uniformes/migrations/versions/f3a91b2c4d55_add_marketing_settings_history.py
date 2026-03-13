"""add marketing settings history

Revision ID: f3a91b2c4d55
Revises: e6b1a4d2c903
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "f3a91b2c4d55"
down_revision = "e6b1a4d2c903"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cambio_marketing_configuracion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("rol_usuario", sa.String(length=20), nullable=True),
        sa.Column("seccion", sa.String(length=30), nullable=False),
        sa.Column("campo", sa.String(length=80), nullable=False),
        sa.Column("etiqueta_campo", sa.String(length=120), nullable=False),
        sa.Column("valor_anterior", sa.Text(), nullable=True),
        sa.Column("valor_nuevo", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cambio_marketing_configuracion_usuario_id"),
        "cambio_marketing_configuracion",
        ["usuario_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cambio_marketing_configuracion_seccion"),
        "cambio_marketing_configuracion",
        ["seccion"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cambio_marketing_configuracion_campo"),
        "cambio_marketing_configuracion",
        ["campo"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cambio_marketing_configuracion_created_at"),
        "cambio_marketing_configuracion",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cambio_marketing_configuracion_created_at"), table_name="cambio_marketing_configuracion")
    op.drop_index(op.f("ix_cambio_marketing_configuracion_campo"), table_name="cambio_marketing_configuracion")
    op.drop_index(op.f("ix_cambio_marketing_configuracion_seccion"), table_name="cambio_marketing_configuracion")
    op.drop_index(op.f("ix_cambio_marketing_configuracion_usuario_id"), table_name="cambio_marketing_configuracion")
    op.drop_table("cambio_marketing_configuracion")
