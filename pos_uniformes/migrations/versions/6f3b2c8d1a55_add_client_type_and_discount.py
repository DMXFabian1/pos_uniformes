"""add client type and discount

Revision ID: 6f3b2c8d1a55
Revises: 5e2c1a7b9d44
Create Date: 2026-03-11 19:05:00.000000
"""

from __future__ import annotations

from decimal import Decimal

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "6f3b2c8d1a55"
down_revision = "5e2c1a7b9d44"
branch_labels = None
depends_on = None


tipo_cliente_enum = postgresql.ENUM(
    "GENERAL",
    "PROFESOR",
    "MAYORISTA",
    name="tipo_cliente",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("GENERAL", "PROFESOR", "MAYORISTA", name="tipo_cliente").create(bind, checkfirst=True)

    op.add_column(
        "cliente",
        sa.Column(
            "tipo_cliente",
            tipo_cliente_enum,
            nullable=False,
            server_default="GENERAL",
        ),
    )
    op.add_column(
        "cliente",
        sa.Column(
            "descuento_preferente",
            sa.Numeric(5, 2),
            nullable=False,
            server_default=sa.text(str(Decimal("0.00"))),
        ),
    )
    op.create_index(op.f("ix_cliente_tipo_cliente"), "cliente", ["tipo_cliente"], unique=False)

    op.execute(
        """
        UPDATE cliente
        SET descuento_preferente = 0.00
        WHERE descuento_preferente IS NULL
        """
    )
    op.alter_column("cliente", "tipo_cliente", server_default=None)
    op.alter_column("cliente", "descuento_preferente", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_cliente_tipo_cliente"), table_name="cliente")
    op.drop_column("cliente", "descuento_preferente")
    op.drop_column("cliente", "tipo_cliente")
    bind = op.get_bind()
    postgresql.ENUM("GENERAL", "PROFESOR", "MAYORISTA", name="tipo_cliente").drop(bind, checkfirst=True)
