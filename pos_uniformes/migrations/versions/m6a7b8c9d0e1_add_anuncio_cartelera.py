"""add_anuncio_cartelera

Cartelera/anuncios para los satélites (broadcast, no cola de consumo):
- tabla `anuncio` con texto (titulo/mensaje) y/o imagen embebida (bytea)
- `activo` controla la membresía en la cartelera; se apaga para quitar el anuncio
- trigger AFTER INSERT/UPDATE que hace pg_notify('anuncio', payload) para que
  todos los satélites refresquen su cartelera al instante (LISTEN/NOTIFY) y
  puedan mostrar un aviso inmediato. El polling del watchdog sigue de respaldo.
"""

revision = 'm6a7b8c9d0e1'
down_revision = 'l5f6a7b8c9d0'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

# El trigger solo pide 'refrescar' (recargar la cartelera) en cualquier cambio.
# El aviso inmediato NO lo decide la DB: lo dispara quien crea el anuncio con un
# pg_notify('anuncio', {"accion":"inmediato",...}) explícito (checkbox del admin),
# para poder tener anuncios de solo-cartelera que no interrumpen a nadie.
_NOTIFY_FN = """
CREATE OR REPLACE FUNCTION notify_anuncio() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('anuncio', json_build_object('accion', 'refrescar', 'id', NEW.id)::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_NOTIFY_TRIGGER = """
CREATE TRIGGER anuncio_notify
AFTER INSERT OR UPDATE ON anuncio
FOR EACH ROW EXECUTE FUNCTION notify_anuncio();
"""


def upgrade() -> None:
    op.create_table(
        'anuncio',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('titulo', sa.String(length=120), nullable=True),
        sa.Column('mensaje', sa.Text(), nullable=True),
        sa.Column('imagen', sa.LargeBinary(), nullable=True),
        sa.Column('imagen_mime', sa.String(length=40), nullable=True),
        sa.Column('activo', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('prioridad', sa.Integer(), server_default='0', nullable=False),
        sa.Column('duracion_seg', sa.Integer(), server_default='8', nullable=False),
        sa.Column('creado_por', sa.String(length=60), nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_anuncio_activo'), 'anuncio', ['activo'], unique=False)
    op.create_index(op.f('ix_anuncio_creado_en'), 'anuncio', ['creado_en'], unique=False)
    op.execute(_NOTIFY_FN)
    op.execute(_NOTIFY_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS anuncio_notify ON anuncio")
    op.execute("DROP FUNCTION IF EXISTS notify_anuncio()")
    op.drop_index(op.f('ix_anuncio_creado_en'), table_name='anuncio')
    op.drop_index(op.f('ix_anuncio_activo'), table_name='anuncio')
    op.drop_table('anuncio')
