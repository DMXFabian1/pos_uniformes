"""add_conteo_inventario_tables

Crea tablas para el módulo de conteo físico de inventario:
- conteo_inventario: registro de cada conteo por variante
- config_conteo_escuela: frecuencia configurable por escuela
"""

revision = '29e11361cabd'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table('config_conteo_escuela',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('escuela_id', sa.Integer(), nullable=False),
        sa.Column('dias_vigencia', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['escuela_id'], ['escuela.id'], name=op.f('fk_config_conteo_escuela_escuela_id_escuela'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_config_conteo_escuela')),
        sa.UniqueConstraint('escuela_id', name='config_conteo_escuela_escuela_unico'),
    )

    op.create_table('conteo_inventario',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('variante_id', sa.Integer(), nullable=False),
        sa.Column('escuela_id', sa.Integer(), nullable=True),
        sa.Column('stock_sistema', sa.Integer(), nullable=False),
        sa.Column('stock_fisico', sa.Integer(), nullable=False),
        sa.Column('diferencia', sa.Integer(), nullable=False),
        sa.Column('ajustado', sa.Boolean(), nullable=False),
        sa.Column('ajuste_lote_id', sa.Integer(), nullable=True),
        sa.Column('contado_por', sa.String(length=100), nullable=False),
        sa.Column('contado_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['ajuste_lote_id'], ['ajuste_inventario_lote.id'], name=op.f('fk_conteo_inventario_ajuste_lote_id_ajuste_inventario_lote'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['escuela_id'], ['escuela.id'], name=op.f('fk_conteo_inventario_escuela_id_escuela'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['variante_id'], ['variante.id'], name=op.f('fk_conteo_inventario_variante_id_variante'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_conteo_inventario')),
    )
    op.create_index(op.f('ix_conteo_inventario_ajustado'), 'conteo_inventario', ['ajustado'], unique=False)
    op.create_index(op.f('ix_conteo_inventario_contado_at'), 'conteo_inventario', ['contado_at'], unique=False)
    op.create_index(op.f('ix_conteo_inventario_escuela_id'), 'conteo_inventario', ['escuela_id'], unique=False)
    op.create_index(op.f('ix_conteo_inventario_variante_id'), 'conteo_inventario', ['variante_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_conteo_inventario_variante_id'), table_name='conteo_inventario')
    op.drop_index(op.f('ix_conteo_inventario_escuela_id'), table_name='conteo_inventario')
    op.drop_index(op.f('ix_conteo_inventario_contado_at'), table_name='conteo_inventario')
    op.drop_index(op.f('ix_conteo_inventario_ajustado'), table_name='conteo_inventario')
    op.drop_table('conteo_inventario')
    op.drop_table('config_conteo_escuela')
