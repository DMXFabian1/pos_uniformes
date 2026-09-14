"""El stock puede quedar en negativo: la venta del kiosko descuenta y un
negativo es la señal de "esta talla hay que recontarla".

Revision ID: cd3e4f5a6b7c
Revises: bc2d3e4f5a6b
"""

from __future__ import annotations

from alembic import op

revision = "cd3e4f5a6b7c"
down_revision = "bc2d3e4f5a6b"
branch_labels = None
depends_on = None

# Los nombres reales en producción (Postgres recortó uno). Se quitan todos los
# candidatos con IF EXISTS para no depender de cómo se llamó cada uno.
_VARIANTE = (
    "ck_variante_variante_stock_actual_no_negativo",
    "variante_stock_actual_no_negativo",
)
_MOVIMIENTO = (
    "ck_movimiento_inventario_movimiento_inventario_stock_po_97fc",
    "ck_movimiento_inventario_movimiento_inventario_stock_posterior_no_negativo",
    "movimiento_inventario_stock_posterior_no_negativo",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for nombre in _VARIANTE:
        op.execute(f'ALTER TABLE variante DROP CONSTRAINT IF EXISTS "{nombre}"')
    for nombre in _MOVIMIENTO:
        op.execute(f'ALTER TABLE movimiento_inventario DROP CONSTRAINT IF EXISTS "{nombre}"')


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("UPDATE variante SET stock_actual = 0 WHERE stock_actual < 0")
    op.execute("UPDATE movimiento_inventario SET stock_posterior = 0 WHERE stock_posterior < 0")
    op.create_check_constraint("variante_stock_actual_no_negativo", "variante", "stock_actual >= 0")
    op.create_check_constraint("movimiento_inventario_stock_posterior_no_negativo", "movimiento_inventario", "stock_posterior >= 0")
