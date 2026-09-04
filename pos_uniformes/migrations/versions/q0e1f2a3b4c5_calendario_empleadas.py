"""calendario_empleadas

Calendario de empleadas en la Libreta:
- empleada_horario: descanso fijo semanal + ciclo de pago (cada N días
  TRABAJADOS) + fecha del último pago.
- empleada_evento: excepciones y hechos por día (falta, descanso extra,
  trabajó en su descanso, pago), que le ganan al patrón fijo.
"""

revision = 'q0e1f2a3b4c5'
down_revision = 'p9d0e1f2a3b4'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        'empleada_horario',
        sa.Column('employee_code', sa.String(40), primary_key=True),
        sa.Column('descanso_weekday', sa.Integer(), nullable=True),
        sa.Column('ciclo_dias_pago', sa.Integer(), nullable=False, server_default='6'),
        sa.Column('fecha_ultimo_pago', sa.Date(), nullable=True),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        'empleada_evento',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_code', sa.String(40), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('tipo', sa.String(20), nullable=False),
        sa.Column('nota', sa.String(200), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint('employee_code', 'fecha', 'tipo', name='uq_empleada_evento_dia'),
    )
    op.create_index('ix_empleada_evento_employee_code', 'empleada_evento', ['employee_code'])
    op.create_index('ix_empleada_evento_fecha', 'empleada_evento', ['fecha'])


def downgrade() -> None:
    op.drop_index('ix_empleada_evento_fecha', table_name='empleada_evento')
    op.drop_index('ix_empleada_evento_employee_code', table_name='empleada_evento')
    op.drop_table('empleada_evento')
    op.drop_table('empleada_horario')
