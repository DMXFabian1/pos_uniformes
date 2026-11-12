"""M2: la fotografía del cálculo de cada venta (T2).

`libreta_venta.calculo` (JSONB): la entrada y el resultado del motor de
beneficios con que se cobró la venta, más lo que recalculó el servidor (T3).
`libreta_venta.version_reglas`: la versión de las reglas que se aplicaron.
Las ventas de antes quedan con NULL y se leen como hoy.

Solo agrega.

Revision ID: e8b4c1d7f2a9
Revises: d7a3f9c2e8b1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e8b4c1d7f2a9"
down_revision = "d7a3f9c2e8b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "libreta_venta",
        sa.Column("calculo", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
    )
    op.add_column("libreta_venta", sa.Column("version_reglas", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("libreta_venta", "version_reglas")
    op.drop_column("libreta_venta", "calculo")
