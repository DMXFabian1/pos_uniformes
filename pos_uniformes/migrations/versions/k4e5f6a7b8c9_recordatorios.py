"""tabla recordatorio (calendario: pagos, descansos, notas)

Recordatorios del calendario, compartidos entre PCs. Pueden ser en una fecha
específica o recurrentes (mensual por día del mes, semanal por día de la semana).
"""

revision = 'k4e5f6a7b8c9'
down_revision = 'j3d4e5f6a7b8'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        'recordatorio',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('titulo', sa.String(length=160), nullable=False),
        sa.Column('monto', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('recurrencia', sa.String(length=20), nullable=False, server_default='unica'),
        sa.Column('fecha', sa.Date(), nullable=True),
        sa.Column('dia_mes', sa.Integer(), nullable=True),
        sa.Column('dia_semana', sa.Integer(), nullable=True),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_recordatorio_tipo'), 'recordatorio', ['tipo'])
    op.create_index(op.f('ix_recordatorio_fecha'), 'recordatorio', ['fecha'])
    op.create_index(op.f('ix_recordatorio_activo'), 'recordatorio', ['activo'])


def downgrade() -> None:
    op.drop_index(op.f('ix_recordatorio_activo'), table_name='recordatorio')
    op.drop_index(op.f('ix_recordatorio_fecha'), table_name='recordatorio')
    op.drop_index(op.f('ix_recordatorio_tipo'), table_name='recordatorio')
    op.drop_table('recordatorio')
