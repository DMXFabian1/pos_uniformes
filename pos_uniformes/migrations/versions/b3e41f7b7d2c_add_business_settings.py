"""add business settings

Revision ID: b3e41f7b7d2c
Revises: 0c8caec32b78
Create Date: 2026-03-10 16:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3e41f7b7d2c"
down_revision = "0c8caec32b78"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "configuracion_negocio",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre_negocio", sa.String(length=160), nullable=False),
        sa.Column("telefono", sa.String(length=40), nullable=True),
        sa.Column("direccion", sa.Text(), nullable=True),
        sa.Column("pie_ticket", sa.Text(), nullable=True),
        sa.Column("impresora_preferida", sa.String(length=200), nullable=True),
        sa.Column("copias_ticket", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_configuracion_negocio")),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO configuracion_negocio (
                id,
                nombre_negocio,
                pie_ticket,
                copias_ticket
            )
            VALUES (
                1,
                'POS Uniformes',
                'Gracias por tu compra.',
                1
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_table("configuracion_negocio")
