"""Buzón entre las PCs: mensajes de texto que cualquier pantalla puede leer.

Para mandar comandos y respuestas entre la Mac, la PC principal y los kioskos
sin pasar por WhatsApp (Daniel, 2026-10-15: «se está trabando»). Va por la base
y no por una carpeta compartida porque todas las PCs ya hablan con ella, y
porque así Claude puede dejar un mensaje desde la Mac y leer la respuesta.

- `para` vacío = a todas las PCs.
- Solo crea una tabla; no toca datos existentes.

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "buzon_mensaje",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("de", sa.String(60), nullable=False),
        sa.Column("para", sa.String(60), nullable=True, index=True),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("buzon_mensaje")
