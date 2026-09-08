"""caja_retiro

Retiros del cajón con motivo (proveedor, renta, cambio...). El corte los
descuenta del esperado y el ticket los lista.
"""

revision = 'v5d6e7f8a9b0'
down_revision = 'u4c5d6e7f8a9'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        'caja_retiro',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('monto', sa.Numeric(12, 2), nullable=False),
        sa.Column('motivo', sa.String(120), nullable=False, server_default=''),
        sa.Column('creado_por', sa.String(40), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_caja_retiro_created_at', 'caja_retiro', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_caja_retiro_created_at', table_name='caja_retiro')
    op.drop_table('caja_retiro')
