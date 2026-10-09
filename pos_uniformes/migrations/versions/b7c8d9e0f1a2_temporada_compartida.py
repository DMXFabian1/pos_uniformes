"""La temporada se elige una vez y vale para toda la tienda.

Daniel, 2026-10-09: «si pongo una temporada en una quiero que se replique en
las demás». Era un ajuste por máquina —cada pantalla con su archivo— y eso
significaba ponerlo tres veces y que se desincronizaran.

Vive en `configuracion_negocio` porque es de la TIENDA, igual que el nombre,
la dirección y el logo. El archivo local se queda como cache: el kiosko sin
red tiene que seguir sabiendo qué mes es.

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b7c8d9e0f1a2"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "configuracion_negocio",
        sa.Column("temporada_modo", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "configuracion_negocio",
        sa.Column("temporada_archivo", sa.String(length=40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("configuracion_negocio", "temporada_archivo")
    op.drop_column("configuracion_negocio", "temporada_modo")
