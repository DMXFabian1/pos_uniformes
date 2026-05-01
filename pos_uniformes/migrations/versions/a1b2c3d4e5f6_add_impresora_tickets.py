"""add impresora_tickets to business_settings

Revision ID: e9f1a2b3c4d5
Revises: b2c3d4e5f6a7
Create Date: 2026-05-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "e9f1a2b3c4d5"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "configuracion_negocio",
        sa.Column("impresora_tickets", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("configuracion_negocio", "impresora_tickets")
