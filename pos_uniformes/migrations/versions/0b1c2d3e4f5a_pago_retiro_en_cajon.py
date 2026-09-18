"""Un pago o retiro que NO salió del cajón en el periodo del corte (se pagó
con otro dinero, o ya se había contado en el corte anterior) no se resta de
lo que debe haber. Daniel, 2026-09-18: "el pago a Evelyn lo hice ayer".

Revision ID: 0b1c2d3e4f5a
Revises: f06b7c8d9e0f
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0b1c2d3e4f5a"
down_revision = "f06b7c8d9e0f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("empleada_pago", sa.Column("en_cajon", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("caja_retiro", sa.Column("en_cajon", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("caja_retiro", "en_cajon")
    op.drop_column("empleada_pago", "en_cajon")
