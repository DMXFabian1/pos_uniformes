"""Compras de empleadas a cuenta de su pago (Daniel, 2026-11-12).

`prestamo_empleada.cobrar_desde`: desde qué día se puede descontar. NULL =
en el siguiente pago (como todos los préstamos de antes); con fecha = se
salta los pagos anteriores a ese día (la empleada eligió «del pago
siguiente»).

Solo agrega.

Revision ID: f1c2d3e4a5b6
Revises: e8b4c1d7f2a9
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f1c2d3e4a5b6"
down_revision = "e8b4c1d7f2a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prestamo_empleada", sa.Column("cobrar_desde", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("prestamo_empleada", "cobrar_desde")
