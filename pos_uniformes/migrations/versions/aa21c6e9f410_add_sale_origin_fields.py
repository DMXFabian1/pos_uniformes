"""add sale origin fields

Revision ID: aa21c6e9f410
Revises: f3a91b2c4d55
Create Date: 2026-04-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "aa21c6e9f410"
down_revision = "f3a91b2c4d55"
branch_labels = None
depends_on = None


credit_mode_enum = sa.Enum(
    "UNASSIGNED",
    "EMPLOYEE",
    "OPERATOR_DIRECT",
    name="credit_mode_venta",
)


def upgrade() -> None:
    bind = op.get_bind()
    credit_mode_enum.create(bind, checkfirst=True)
    op.add_column(
        "venta",
        sa.Column(
            "credit_mode",
            credit_mode_enum,
            nullable=False,
            server_default="UNASSIGNED",
        ),
    )
    op.add_column("venta", sa.Column("seller_employee_code", sa.String(length=40), nullable=True))
    op.add_column("venta", sa.Column("seller_employee_display_name", sa.String(length=120), nullable=True))
    op.create_index(op.f("ix_venta_credit_mode"), "venta", ["credit_mode"], unique=False)
    op.create_index(op.f("ix_venta_seller_employee_code"), "venta", ["seller_employee_code"], unique=False)
    op.alter_column("venta", "credit_mode", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_venta_seller_employee_code"), table_name="venta")
    op.drop_index(op.f("ix_venta_credit_mode"), table_name="venta")
    op.drop_column("venta", "seller_employee_display_name")
    op.drop_column("venta", "seller_employee_code")
    op.drop_column("venta", "credit_mode")
    bind = op.get_bind()
    credit_mode_enum.drop(bind, checkfirst=True)
