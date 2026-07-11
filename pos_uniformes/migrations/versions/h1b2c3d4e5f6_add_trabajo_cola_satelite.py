"""add_trabajo_cola_satelite

Crea la tabla `trabajo`: cola de trabajos que el POS/kiosko envían al satélite
para imprimir (ticket/etiqueta/conteo) o atender (pedido). Fase 0 del despachador.
"""

revision = 'h1b2c3d4e5f6'
down_revision = 'g1a2b3c4d5e6'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

tipo_trabajo = sa.Enum('TICKET', 'ETIQUETA', 'CONTEO', 'PEDIDO', name='tipo_trabajo')
estado_trabajo = sa.Enum('PENDIENTE', 'EN_PROCESO', 'HECHO', 'ERROR', 'CANCELADO', name='estado_trabajo')


def upgrade() -> None:
    op.create_table(
        'trabajo',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tipo', tipo_trabajo, nullable=False),
        sa.Column('estado', estado_trabajo, nullable=False, server_default='PENDIENTE'),
        sa.Column('origen', sa.String(length=60), nullable=False),
        sa.Column('prioridad', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('contenido', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('creado_por', sa.String(length=60), nullable=False),
        sa.Column('procesado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_trabajo')),
    )
    op.create_index(op.f('ix_trabajo_tipo'), 'trabajo', ['tipo'], unique=False)
    op.create_index(op.f('ix_trabajo_estado'), 'trabajo', ['estado'], unique=False)
    op.create_index(op.f('ix_trabajo_origen'), 'trabajo', ['origen'], unique=False)
    op.create_index(op.f('ix_trabajo_created_at'), 'trabajo', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_trabajo_created_at'), table_name='trabajo')
    op.drop_index(op.f('ix_trabajo_origen'), table_name='trabajo')
    op.drop_index(op.f('ix_trabajo_estado'), table_name='trabajo')
    op.drop_index(op.f('ix_trabajo_tipo'), table_name='trabajo')
    op.drop_table('trabajo')
    bind = op.get_bind()
    estado_trabajo.drop(bind, checkfirst=True)
    tipo_trabajo.drop(bind, checkfirst=True)
