"""Una foto por modelo: `producto_foto`.

Para la Ropa del kiosko en cuadrícula con fotos, estilo Nike, y para que los
uniformes también puedan traer la suya (Daniel, 2026-10-20). Va en la base y
no en una carpeta compartida porque la base es el único canal que ya tienen
todas las PCs, kioskos sin red incluidos: cada kiosko copia las miniaturas a
su disco en segundo plano y la cuadrícula las lee de ahí.

Dos tamaños ya recortados al subir: miniatura (~400 px, ~25 KB) para la
cuadrícula y mediana (~1000 px) para la ficha. Nunca el original. El catálogo
que viaja a los kioskos solo lleva el `hash`, nunca los bytes.

Revision ID: f7e8d9c0b1a2
Revises: a0b1c2d3e4f5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f7e8d9c0b1a2"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "producto_foto",
        sa.Column("producto_id", sa.Integer(), sa.ForeignKey("producto.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("hash", sa.String(32), nullable=False, index=True),
        sa.Column("miniatura", sa.LargeBinary(), nullable=False),
        sa.Column("mediana", sa.LargeBinary(), nullable=False),
        sa.Column("ancho", sa.Integer(), nullable=False),
        sa.Column("alto", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("producto_foto")
