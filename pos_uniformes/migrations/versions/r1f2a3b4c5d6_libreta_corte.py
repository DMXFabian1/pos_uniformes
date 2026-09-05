"""libreta_corte

Historial de cortes de la Libreta: solo la cifra FINAL que el dueño
confirmó (sin esperado ni diferencia — sin rastro de edición), con
operaciones/piezas y nota. Lo consulta el encargado en "Ver cortes".
"""

revision = 'r1f2a3b4c5d6'
down_revision = 'q0e1f2a3b4c5'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        'libreta_corte',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('periodo_label', sa.String(80), nullable=False, server_default='HOY'),
        sa.Column('monto_final', sa.Numeric(12, 2), nullable=False),
        sa.Column('operaciones', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('piezas', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('nota', sa.String(200), nullable=True),
        sa.Column('creado_por', sa.String(40), nullable=False, server_default=''),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index('ix_libreta_corte_fecha', 'libreta_corte', ['fecha'])


def downgrade() -> None:
    op.drop_index('ix_libreta_corte_fecha', table_name='libreta_corte')
    op.drop_table('libreta_corte')
