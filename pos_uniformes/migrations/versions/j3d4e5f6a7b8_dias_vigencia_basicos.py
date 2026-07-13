"""dias_vigencia_basicos en configuracion_negocio

Frecuencia de conteo de los "productos básicos" (los que no pertenecen a una
escuela). Es global (una sola columna en la config del negocio) porque los
básicos no están ligados a una escuela. NULL = usar el default global de días.
"""

revision = 'j3d4e5f6a7b8'
down_revision = 'i2c3d4e5f6a7'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        'configuracion_negocio',
        sa.Column('dias_vigencia_basicos', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('configuracion_negocio', 'dias_vigencia_basicos')
