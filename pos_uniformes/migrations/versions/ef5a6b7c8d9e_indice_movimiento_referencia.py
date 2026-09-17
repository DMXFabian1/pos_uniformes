"""Índice en movimiento_inventario.referencia: cada venta del kiosko pregunta
"¿ya descontó libreta:N?" y cada borrado busca por referencia; sin índice era
un recorrido completo de la tabla por venta.

Revision ID: ef5a6b7c8d9e
Revises: de4f5a6b7c8d
"""

from __future__ import annotations

from alembic import op

revision = "ef5a6b7c8d9e"
down_revision = "de4f5a6b7c8d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_movimiento_inventario_referencia", "movimiento_inventario", ["referencia"])


def downgrade() -> None:
    op.drop_index("ix_movimiento_inventario_referencia", table_name="movimiento_inventario")
