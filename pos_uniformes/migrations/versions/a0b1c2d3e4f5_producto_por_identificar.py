"""Ropa normal que entra sin nombre: `producto.por_identificar`.

La mercancía llega con el código del proveedor y Daniel la va nombrando
conforme la saca (2026-10-20). Con esta marca el sistema sabe qué le falta
nombre: la bandeja «Por nombrar» del POS y del celular la lista, y al nombrarla
se apaga. Solo agrega una columna; lo existente queda en falso.

Revision ID: a0b1c2d3e4f5
Revises: f1a2b3c4d5e6
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a0b1c2d3e4f5"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "producto",
        sa.Column("por_identificar", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_producto_por_identificar", "producto", ["por_identificar"])


def downgrade() -> None:
    op.drop_index("ix_producto_por_identificar", table_name="producto")
    op.drop_column("producto", "por_identificar")
