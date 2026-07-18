"""tabla recordatorio_completado (marcar pagos/ocurrencias como hechos)

Registra qué ocurrencia de un recordatorio ya se hizo/pagó (recordatorio + fecha
de la ocurrencia). Se borra en cascada si se elimina el recordatorio.
"""

revision = 'l5f6a7b8c9d0'
down_revision = 'k4e5f6a7b8c9'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        'recordatorio_completado',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('recordatorio_id', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['recordatorio_id'], ['recordatorio.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('recordatorio_id', 'fecha', name='uq_recordatorio_completado'),
    )
    op.create_index(op.f('ix_recordatorio_completado_recordatorio_id'), 'recordatorio_completado', ['recordatorio_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_recordatorio_completado_recordatorio_id'), table_name='recordatorio_completado')
    op.drop_table('recordatorio_completado')
