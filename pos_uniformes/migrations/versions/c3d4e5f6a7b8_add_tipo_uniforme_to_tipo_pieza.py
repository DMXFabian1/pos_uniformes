"""add tipo_uniforme to tipo_pieza

Revision ID: c3d4e5f6a7b8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tipo_pieza",
        sa.Column(
            "tipo_uniforme",
            sa.String(length=20),
            nullable=True,
            server_default=sa.text("'oficial'"),
        ),
    )
    # Piezas deportivas reciben 'deportivo'; el resto queda con el default 'oficial'.
    op.execute(
        """
        UPDATE tipo_pieza
        SET tipo_uniforme = 'deportivo'
        WHERE nombre IN ('Pants 3pz', 'Pants 2pz', 'Pants Suelto', 'Chamarra', 'Playera')
        """
    )


def downgrade() -> None:
    op.drop_column("tipo_pieza", "tipo_uniforme")
