"""caja_parametros.ocultar_tarjeta

La casilla "Ocultar los cobros con tarjeta" del corte deja de arrancar
apagada: se recuerda la última decisión del dueño. Vive en la base (no en
un archivo local) para que valga igual en el kiosko y en el celular.
"""

revision = 'y8a9b0c1d2e3'
down_revision = 'x7f8a9b0c1d2'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        'caja_parametros',
        sa.Column('ocultar_tarjeta', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('caja_parametros', 'ocultar_tarjeta')
