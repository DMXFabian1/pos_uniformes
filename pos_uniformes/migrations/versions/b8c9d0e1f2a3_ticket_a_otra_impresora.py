"""Mandar un ticket a la impresora de OTRA PC: `satelite.imprime` y `trabajo.destino`.

Si la térmica de un kiosko falla, la venta no se debe quedar sin ticket: desde
la ventana de imprimir se elige otra PC (Daniel, 2026-11-05). Para eso cada PC
publica qué sabe imprimir (`satelite.imprime`, junto con su latido) y un
trabajo puede ir dirigido a una PC concreta (`trabajo.destino`; vacío = lo
imprime quien lo tome, como siempre). Solo agrega dos columnas opcionales.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("satelite", sa.Column("imprime", sa.String(120), nullable=True))
    op.add_column("trabajo", sa.Column("destino", sa.String(40), nullable=True))
    op.create_index("ix_trabajo_destino", "trabajo", ["destino"])


def downgrade() -> None:
    op.drop_index("ix_trabajo_destino", table_name="trabajo")
    op.drop_column("trabajo", "destino")
    op.drop_column("satelite", "imprime")
