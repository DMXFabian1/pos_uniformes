"""Jornada de básicos por UNA prenda (no todo el tipo): columna `prenda`.

Revision ID: de4f5a6b7c8d
Revises: cd3e4f5a6b7c
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "de4f5a6b7c8d"
down_revision = "cd3e4f5a6b7c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conteo_jornada", sa.Column("prenda", sa.String(length=200), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("conteo_jornada", "prenda")
