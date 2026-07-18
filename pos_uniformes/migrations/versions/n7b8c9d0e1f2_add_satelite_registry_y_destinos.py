"""add_satelite_registry_y_destinos

Anuncios dirigidos + presencia de satélites:
- tabla `satelite`: registro de cada satélite (identificador estable + nombre
  editable + ultimo_visto para presencia/heartbeat). La lee también la PWA.
- columna `anuncio.destinos` (JSONB): lista de identificadores a los que va
  dirigido el anuncio. NULL o vacío = todos los satélites.
"""

revision = 'n7b8c9d0e1f2'
down_revision = 'm6a7b8c9d0e1'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table(
        'satelite',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('identificador', sa.String(length=40), nullable=False),
        sa.Column('nombre', sa.String(length=60), nullable=False),
        sa.Column('ultimo_visto', sa.DateTime(timezone=True), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('identificador'),
    )
    op.create_index(op.f('ix_satelite_identificador'), 'satelite', ['identificador'], unique=False)
    op.create_index(op.f('ix_satelite_ultimo_visto'), 'satelite', ['ultimo_visto'], unique=False)
    op.add_column(
        'anuncio',
        sa.Column('destinos', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('anuncio', 'destinos')
    op.drop_index(op.f('ix_satelite_ultimo_visto'), table_name='satelite')
    op.drop_index(op.f('ix_satelite_identificador'), table_name='satelite')
    op.drop_table('satelite')
