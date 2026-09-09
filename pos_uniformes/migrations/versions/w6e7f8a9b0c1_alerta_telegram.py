"""alerta_telegram

Cola de alertas para el bot de Telegram: cortes, retiros y avisos que
cualquier máquina (kiosko, PWA, tarea) deja aquí y el bot de la PC servidor
manda al instante. Así los kioskos no necesitan el token.
"""

revision = 'w6e7f8a9b0c1'
down_revision = 'v5d6e7f8a9b0'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        'alerta_telegram',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('texto', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('enviado_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('intentos', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_alerta_telegram_enviado_at', 'alerta_telegram', ['enviado_at'])


def downgrade() -> None:
    op.drop_index('ix_alerta_telegram_enviado_at', table_name='alerta_telegram')
    op.drop_table('alerta_telegram')
