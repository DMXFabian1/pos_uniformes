"""Un aviso puede traer sonido: el nombre de un archivo de assets/sonidos.

No se guarda el audio en la base a propósito. Los sonidos viajan dentro de la
app del satélite (como los dibujos de temporada), así que el kiosko ya los
trae: no hay que mandar un archivo por la red cada vez que suena un aviso, ni
engordar cada fila con los mismos bytes.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("anuncio", sa.Column("sonido", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("anuncio", "sonido")
