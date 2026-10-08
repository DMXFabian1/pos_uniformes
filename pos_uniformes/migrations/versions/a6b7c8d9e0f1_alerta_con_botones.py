"""Las alertas del bot pueden traer botones.

Un aviso que no se puede atender donde llega obliga a ir a la PC. Daniel, el
2026-10-08: «el bot solo me avisa que no hay respaldo, en vez de darme un
botón para hacerlo».

El teclado viaja en la fila de la cola y no se arma al mandarla: quien encola
—el vigilante, un kiosko, una tarea— es el único que sabe qué se puede hacer
con ese aviso. Deducirlo del texto al enviarlo sería adivinar.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alerta_telegram",
        sa.Column("botones", sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alerta_telegram", "botones")
