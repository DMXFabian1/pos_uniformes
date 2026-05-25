"""add abono anulado fields for soft-delete

Revision ID: a2b3c4d5e6f7
Revises: f7c9e12ab430
Create Date: 2026-05-25 02:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a2b3c4d5e6f7"
down_revision = "c2d4e6f8a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "apartado_abono",
        sa.Column("anulado", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "apartado_abono",
        sa.Column("anulado_por_id", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True),
    )
    op.add_column(
        "apartado_abono",
        sa.Column("anulado_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "apartado_abono",
        sa.Column("anulado_observacion", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("apartado_abono", "anulado_observacion")
    op.drop_column("apartado_abono", "anulado_at")
    op.drop_column("apartado_abono", "anulado_por_id")
    op.drop_column("apartado_abono", "anulado")
