"""E7: prendas en Oferta o Liquidación (Daniel, 2026-11-11).

`rebaja_producto`: el precio rebajado de una variante, con su tipo, el precio
de antes y, en ofertas, el último día. El precio normal de la variante no se
toca. Una sola rebaja activa por variante.

Solo agrega.

Revision ID: d7a3f9c2e8b1
Revises: c6d1e8a4b2f7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d7a3f9c2e8b1"
down_revision = "c6d1e8a4b2f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rebaja_producto",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("variante_id", sa.Integer(), sa.ForeignKey("variante.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("precio", sa.Numeric(10, 2), nullable=False),
        sa.Column("precio_antes", sa.Numeric(10, 2), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("terminada_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("tipo IN ('oferta', 'liquidacion')", name="rebaja_tipo_valido"),
        sa.CheckConstraint("precio > 0", name="rebaja_precio_positivo"),
    )
    op.create_index("ix_rebaja_producto_variante_id", "rebaja_producto", ["variante_id"])
    op.create_index(
        "uq_rebaja_producto_activa_por_variante",
        "rebaja_producto",
        ["variante_id"],
        unique=True,
        postgresql_where=sa.text("activa"),
    )


def downgrade() -> None:
    op.drop_index("uq_rebaja_producto_activa_por_variante", table_name="rebaja_producto")
    op.drop_index("ix_rebaja_producto_variante_id", table_name="rebaja_producto")
    op.drop_table("rebaja_producto")
