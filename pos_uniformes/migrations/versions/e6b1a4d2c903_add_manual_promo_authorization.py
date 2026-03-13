"""add manual promo authorization

Revision ID: e6b1a4d2c903
Revises: 1e4d7b6c9f21, c4b8d91e7f10, 4d1b7e2a9c34, d91f3a7c2b44
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "e6b1a4d2c903"
down_revision = ("1e4d7b6c9f21", "c4b8d91e7f10", "4d1b7e2a9c34", "d91f3a7c2b44")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "configuracion_negocio",
        sa.Column("promo_authorization_code_hash", sa.String(length=255), nullable=True),
    )
    op.create_table(
        "autorizacion_promocion_manual",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venta_id", sa.Integer(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("rol_usuario", sa.String(length=20), nullable=True),
        sa.Column("folio_venta", sa.String(length=40), nullable=True),
        sa.Column("porcentaje_lealtad", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("porcentaje_promocion", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("porcentaje_aplicado", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("origen_aplicado", sa.String(length=40), nullable=False, server_default="SIN_DESCUENTO"),
        sa.Column("observacion", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cliente_id"], ["cliente.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["venta_id"], ["venta.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_autorizacion_promocion_manual_cliente_id"),
        "autorizacion_promocion_manual",
        ["cliente_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_autorizacion_promocion_manual_created_at"),
        "autorizacion_promocion_manual",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_autorizacion_promocion_manual_folio_venta"),
        "autorizacion_promocion_manual",
        ["folio_venta"],
        unique=False,
    )
    op.create_index(
        op.f("ix_autorizacion_promocion_manual_usuario_id"),
        "autorizacion_promocion_manual",
        ["usuario_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_autorizacion_promocion_manual_venta_id"),
        "autorizacion_promocion_manual",
        ["venta_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_autorizacion_promocion_manual_venta_id"), table_name="autorizacion_promocion_manual")
    op.drop_index(op.f("ix_autorizacion_promocion_manual_usuario_id"), table_name="autorizacion_promocion_manual")
    op.drop_index(op.f("ix_autorizacion_promocion_manual_folio_venta"), table_name="autorizacion_promocion_manual")
    op.drop_index(op.f("ix_autorizacion_promocion_manual_created_at"), table_name="autorizacion_promocion_manual")
    op.drop_index(op.f("ix_autorizacion_promocion_manual_cliente_id"), table_name="autorizacion_promocion_manual")
    op.drop_table("autorizacion_promocion_manual")
    op.drop_column("configuracion_negocio", "promo_authorization_code_hash")
