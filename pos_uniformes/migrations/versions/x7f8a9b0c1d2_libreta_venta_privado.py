"""libreta_venta.privado

Movimientos privados del dueño: un cobro con TARJETA que Daniel marca como
privado desaparece por completo de lo que ve el encargado (su ticket de
corte, su pantalla y su modo del celular). Solo tarjeta: ocultar efectivo
descuadraría el corte del cajón.
"""

revision = 'x7f8a9b0c1d2'
down_revision = 'w6e7f8a9b0c1'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        'libreta_venta',
        sa.Column('privado', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('libreta_venta', 'privado')
