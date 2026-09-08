"""afluencia_hora

Personas que entran (y pasan por fuera) por cámara y hora, contadas por
`afluencia/contador_afluencia.py` desde las cámaras del DVR. El kiosko la cruza
con la Libreta para la conversión por hora.
"""

revision = 's2a3b4c5d6e7'
down_revision = 'r1f2a3b4c5d6'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        'afluencia_hora',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('camara', sa.String(60), nullable=False),
        sa.Column('hora', sa.DateTime(timezone=True), nullable=False),
        sa.Column('entradas', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('salidas', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pasan', sa.Integer(), nullable=False, server_default='0'),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint('camara', 'hora', name='uq_afluencia_hora_camara_hora'),
    )
    op.create_index('ix_afluencia_hora_hora', 'afluencia_hora', ['hora'])


def downgrade() -> None:
    op.drop_index('ix_afluencia_hora_hora', table_name='afluencia_hora')
    op.drop_table('afluencia_hora')
