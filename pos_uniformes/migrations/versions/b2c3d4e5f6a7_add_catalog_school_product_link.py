"""add catalog_school_product_link

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6, a3c7e9f1b204
Create Date: 2026-04-29 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = ("a1b2c3d4e5f6", "a3c7e9f1b204")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_school_product_link",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escuela_id", sa.Integer(), sa.ForeignKey("escuela.id", ondelete="CASCADE"), nullable=False),
        sa.Column("producto_id", sa.Integer(), sa.ForeignKey("producto.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("escuela_id", "producto_id", name="uq_school_product_link"),
    )
    op.create_index("ix_catalog_school_product_link_escuela_id", "catalog_school_product_link", ["escuela_id"])


def downgrade() -> None:
    op.drop_index("ix_catalog_school_product_link_escuela_id", table_name="catalog_school_product_link")
    op.drop_table("catalog_school_product_link")
