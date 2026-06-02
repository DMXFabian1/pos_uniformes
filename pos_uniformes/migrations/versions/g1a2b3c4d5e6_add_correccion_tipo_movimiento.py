"""Add CORRECCION to bodega_movimiento tipo check constraint.

Revision ID: g1a2b3c4d5e6
Revises: f8a9b0c1d2e3
Create Date: 2026-06-02
"""
from alembic import op

revision = "g1a2b3c4d5e6"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None

_OLD = "tipo IN ('INGRESO', 'RETIRO', 'TRANSFERENCIA', 'MOVER_CAJA', 'CREAR_CAJA', 'AJUSTE')"
_NEW = "tipo IN ('INGRESO', 'RETIRO', 'TRANSFERENCIA', 'MOVER_CAJA', 'CREAR_CAJA', 'AJUSTE', 'CORRECCION')"


def upgrade() -> None:
    op.drop_constraint("bodega_movimiento_tipo_valido", "bodega_movimiento", type_="check")
    op.create_check_constraint("bodega_movimiento_tipo_valido", "bodega_movimiento", _NEW)


def downgrade() -> None:
    op.drop_constraint("bodega_movimiento_tipo_valido", "bodega_movimiento", type_="check")
    op.create_check_constraint("bodega_movimiento_tipo_valido", "bodega_movimiento", _OLD)
