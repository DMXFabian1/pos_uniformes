"""Demanda no atendida: lo que pidieron y no se pudo vender.

Revision ID: z9b0c1d2e3f4
Revises: y8a9b0c1d2e3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "z9b0c1d2e3f4"
down_revision = "y8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demanda_no_atendida",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.String(length=24), nullable=False),
        sa.Column("texto", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("sku", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("producto", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("talla", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("piezas", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("employee_code", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("origen", sa.String(length=60), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_demanda_no_atendida_tipo", "demanda_no_atendida", ["tipo"])
    op.create_index("ix_demanda_no_atendida_sku", "demanda_no_atendida", ["sku"])
    op.create_index("ix_demanda_no_atendida_created_at", "demanda_no_atendida", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_demanda_no_atendida_created_at", table_name="demanda_no_atendida")
    op.drop_index("ix_demanda_no_atendida_sku", table_name="demanda_no_atendida")
    op.drop_index("ix_demanda_no_atendida_tipo", table_name="demanda_no_atendida")
    op.drop_table("demanda_no_atendida")
