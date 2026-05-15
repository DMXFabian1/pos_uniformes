"""add employee attribution to apartado and apartado_abono

Revision ID: b3c4d5e6f7a8
Revises: e9f1a2b3c4d5
Create Date: 2026-05-15

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b3c4d5e6f7a8"
down_revision = "e9f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("apartado", sa.Column("seller_employee_code", sa.String(40), nullable=True))
    op.add_column("apartado", sa.Column("seller_employee_display_name", sa.String(120), nullable=True))
    op.add_column("apartado", sa.Column("delivery_employee_code", sa.String(40), nullable=True))
    op.add_column("apartado", sa.Column("delivery_employee_display_name", sa.String(120), nullable=True))
    op.create_index("ix_apartado_seller_employee_code", "apartado", ["seller_employee_code"])
    op.create_index("ix_apartado_delivery_employee_code", "apartado", ["delivery_employee_code"])

    op.add_column("apartado_abono", sa.Column("seller_employee_code", sa.String(40), nullable=True))
    op.add_column("apartado_abono", sa.Column("seller_employee_display_name", sa.String(120), nullable=True))
    op.create_index("ix_apartado_abono_seller_employee_code", "apartado_abono", ["seller_employee_code"])


def downgrade() -> None:
    op.drop_index("ix_apartado_abono_seller_employee_code", table_name="apartado_abono")
    op.drop_column("apartado_abono", "seller_employee_display_name")
    op.drop_column("apartado_abono", "seller_employee_code")

    op.drop_index("ix_apartado_delivery_employee_code", table_name="apartado")
    op.drop_index("ix_apartado_seller_employee_code", table_name="apartado")
    op.drop_column("apartado", "delivery_employee_display_name")
    op.drop_column("apartado", "delivery_employee_code")
    op.drop_column("apartado", "seller_employee_display_name")
    op.drop_column("apartado", "seller_employee_code")
