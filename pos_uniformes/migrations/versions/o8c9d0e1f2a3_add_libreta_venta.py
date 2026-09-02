"""add_libreta_venta

La "Libreta": registro digital de operaciones del mostrador. Cada
venta/apartado de venta rápida se anota automáticamente ligado al gafete de
la empleada — sustituye la libreta física y la copia de ticket que solo
servía para registrar.
"""

revision = 'o8c9d0e1f2a3'
down_revision = 'n7b8c9d0e1f2'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table(
        'libreta_venta',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_code', sa.String(length=40), nullable=False),
        sa.Column('employee_name', sa.String(length=120), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('cliente', sa.String(length=120), nullable=True),
        sa.Column('piezas', sa.Integer(), nullable=False),
        sa.Column('monto_total', sa.Numeric(12, 2), nullable=False),
        sa.Column('descuento_empleada', sa.Boolean(), nullable=False),
        sa.Column('detalle', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('origen', sa.String(length=60), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_libreta_venta_employee_code'), 'libreta_venta', ['employee_code'], unique=False)
    op.create_index(op.f('ix_libreta_venta_tipo'), 'libreta_venta', ['tipo'], unique=False)
    op.create_index(op.f('ix_libreta_venta_origen'), 'libreta_venta', ['origen'], unique=False)
    op.create_index(op.f('ix_libreta_venta_created_at'), 'libreta_venta', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_libreta_venta_created_at'), table_name='libreta_venta')
    op.drop_index(op.f('ix_libreta_venta_origen'), table_name='libreta_venta')
    op.drop_index(op.f('ix_libreta_venta_tipo'), table_name='libreta_venta')
    op.drop_index(op.f('ix_libreta_venta_employee_code'), table_name='libreta_venta')
    op.drop_table('libreta_venta')
