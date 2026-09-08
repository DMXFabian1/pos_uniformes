"""caja_reactivo_y_nomina

- `caja_parametros`: una fila con el reactivo (fondo de caja) vigente y las
  reglas de pago (sueldo base por ciclo, pesos por comisión, descuento por
  falta). Se siembra con los valores de Daniel al 2026-09-08.
- `empleada_pago`: cada pago registrado con su desglose (base + comisiones
  - faltas). Es lo que el corte descuenta del cajón.
- `libreta_corte`: el corte pasa a ser POR PERIODO (desde el corte anterior
  hasta ahora) y guarda reactivo, esperado y retiros para el siguiente.
"""

revision = 't3b4c5d6e7f8'
down_revision = 's2a3b4c5d6e7'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        'caja_parametros',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('reactivo_actual', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('sueldo_base', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('tarifa_comision', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('descuento_falta', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute(
        "INSERT INTO caja_parametros (id, reactivo_actual, sueldo_base, tarifa_comision, descuento_falta) "
        "VALUES (1, 11160.00, 1300.00, 2.00, 216.67)"
    )

    op.create_table(
        'empleada_pago',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_code', sa.String(40), nullable=False),
        sa.Column('employee_name', sa.String(120), nullable=False, server_default=''),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('desde', sa.Date(), nullable=True),
        sa.Column('hasta', sa.Date(), nullable=False),
        sa.Column('comisiones', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sueldo_base', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('tarifa_comision', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('monto_comisiones', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('faltas', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('descuento_faltas', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('total', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('creado_por', sa.String(40), nullable=False, server_default=''),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index('ix_empleada_pago_employee_code', 'empleada_pago', ['employee_code'])
    op.create_index('ix_empleada_pago_created_at', 'empleada_pago', ['created_at'])

    op.add_column('libreta_corte', sa.Column('desde', sa.DateTime(timezone=True), nullable=True))
    op.add_column('libreta_corte', sa.Column('hasta', sa.DateTime(timezone=True), nullable=True))
    op.add_column('libreta_corte', sa.Column('reactivo_inicial', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.add_column('libreta_corte', sa.Column('monto_esperado', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.add_column('libreta_corte', sa.Column('retiros_pagos', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.add_column('libreta_corte', sa.Column('otros_retiros', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.add_column('libreta_corte', sa.Column('reactivo_final', sa.Numeric(12, 2), nullable=False, server_default='0'))
    # Cortes viejos: su "hasta" es el momento en que se hicieron.
    op.execute("UPDATE libreta_corte SET hasta = created_at WHERE hasta IS NULL")


def downgrade() -> None:
    for col in ('reactivo_final', 'otros_retiros', 'retiros_pagos', 'monto_esperado', 'reactivo_inicial', 'hasta', 'desde'):
        op.drop_column('libreta_corte', col)
    op.drop_index('ix_empleada_pago_created_at', table_name='empleada_pago')
    op.drop_index('ix_empleada_pago_employee_code', table_name='empleada_pago')
    op.drop_table('empleada_pago')
    op.drop_table('caja_parametros')
