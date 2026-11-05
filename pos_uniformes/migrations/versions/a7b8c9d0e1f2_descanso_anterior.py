"""El descanso fijo que una empleada tenía antes: `empleada_descanso_anterior`.

Cambiar el descanso fijo (Stayce: de sábado a lunes, 2026-11-05) repintaba toda
la historia, porque solo se guardaba el de ahora. Con esta tabla el anterior
queda con su último día y las fechas pasadas no se tocan. Solo crea la tabla.

Revision ID: a7b8c9d0e1f2
Revises: e9f0a1b2c3d4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "empleada_descanso_anterior",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_code", sa.String(40), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("hasta", sa.Date(), nullable=False),
        sa.Column("creado_por", sa.String(40), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_empleada_descanso_anterior_employee_code", "empleada_descanso_anterior", ["employee_code"])


def downgrade() -> None:
    op.drop_index("ix_empleada_descanso_anterior_employee_code", table_name="empleada_descanso_anterior")
    op.drop_table("empleada_descanso_anterior")
