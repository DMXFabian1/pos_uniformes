"""Cada PC publica qué versión trae: `satelite.version`.

Para ver desde Administración (y desde el celular) qué kiosko ya tomó la
actualización y cuál se quedó atrás (Daniel, 2026-11-06). Va con el latido,
igual que `imprime`: «2026.11.06+6ba73b01», lo mismo que se publica para los
kioskos. Solo agrega una columna opcional.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("satelite", sa.Column("version", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("satelite", "version")
