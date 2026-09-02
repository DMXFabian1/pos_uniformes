"""libreta_comisiones_y_tarjeta

Libreta v2:
- comisiones: piezas de comisión para la empleada (3pz=3, lo demás 1/unidad;
  abonos=0). Filas históricas: comisiones = piezas.
- pago_tarjeta + monto_neto: si la venta fue con tarjeta, el neto descuenta
  el 4.5% de terminal por producto. Históricas: neto = monto_total.
- tipo gana el valor "abono" (registro de abonos de apartados, sin comisión).
"""

revision = 'p9d0e1f2a3b4'
down_revision = 'o8c9d0e1f2a3'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        'libreta_venta',
        sa.Column('comisiones', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'libreta_venta',
        sa.Column('monto_neto', sa.Numeric(12, 2), nullable=False, server_default='0'),
    )
    op.add_column(
        'libreta_venta',
        sa.Column('pago_tarjeta', sa.Boolean(), nullable=False, server_default='false'),
    )
    # Backfill de filas existentes: sin dato mejor, comisiones = piezas y
    # neto = monto_total (todas eran efectivo antes de esta versión).
    op.execute("UPDATE libreta_venta SET comisiones = piezas, monto_neto = monto_total")


def downgrade() -> None:
    op.drop_column('libreta_venta', 'pago_tarjeta')
    op.drop_column('libreta_venta', 'monto_neto')
    op.drop_column('libreta_venta', 'comisiones')
