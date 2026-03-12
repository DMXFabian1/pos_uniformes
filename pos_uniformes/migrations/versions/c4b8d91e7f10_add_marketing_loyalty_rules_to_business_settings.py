"""add marketing loyalty rules to business settings

Revision ID: c4b8d91e7f10
Revises: be7f9c2a41aa
Create Date: 2026-03-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4b8d91e7f10"
down_revision = "be7f9c2a41aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "configuracion_negocio",
        sa.Column("loyalty_review_window_days", sa.Integer(), nullable=False, server_default="365"),
    )
    op.add_column(
        "configuracion_negocio",
        sa.Column("leal_spend_threshold", sa.Numeric(12, 2), nullable=False, server_default="3000.00"),
    )
    op.add_column(
        "configuracion_negocio",
        sa.Column("leal_purchase_count_threshold", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "configuracion_negocio",
        sa.Column("leal_purchase_sum_threshold", sa.Numeric(12, 2), nullable=False, server_default="2000.00"),
    )
    op.add_column(
        "configuracion_negocio",
        sa.Column("discount_basico", sa.Numeric(5, 2), nullable=False, server_default="5.00"),
    )
    op.add_column(
        "configuracion_negocio",
        sa.Column("discount_leal", sa.Numeric(5, 2), nullable=False, server_default="10.00"),
    )
    op.add_column(
        "configuracion_negocio",
        sa.Column("discount_profesor", sa.Numeric(5, 2), nullable=False, server_default="15.00"),
    )
    op.add_column(
        "configuracion_negocio",
        sa.Column("discount_mayorista", sa.Numeric(5, 2), nullable=False, server_default="20.00"),
    )


def downgrade() -> None:
    op.drop_column("configuracion_negocio", "discount_mayorista")
    op.drop_column("configuracion_negocio", "discount_profesor")
    op.drop_column("configuracion_negocio", "discount_leal")
    op.drop_column("configuracion_negocio", "discount_basico")
    op.drop_column("configuracion_negocio", "leal_purchase_sum_threshold")
    op.drop_column("configuracion_negocio", "leal_purchase_count_threshold")
    op.drop_column("configuracion_negocio", "leal_spend_threshold")
    op.drop_column("configuracion_negocio", "loyalty_review_window_days")
