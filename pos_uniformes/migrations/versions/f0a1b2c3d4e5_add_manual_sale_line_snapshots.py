"""add manual sale line snapshots

Revision ID: f0a1b2c3d4e5
Revises: c2f4d8a1b901
Create Date: 2026-04-10 18:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f0a1b2c3d4e5"
down_revision = "c2f4d8a1b901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("venta_detalle") as batch_op:
        batch_op.alter_column("variante_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("sku_snapshot", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("descripcion_snapshot", sa.String(length=220), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("venta_detalle") as batch_op:
        batch_op.drop_column("descripcion_snapshot")
        batch_op.drop_column("sku_snapshot")
        batch_op.alter_column("variante_id", existing_type=sa.Integer(), nullable=False)
