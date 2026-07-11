"""trabajo_reintentos_y_notify

Fase 6 del despachador:
- columnas `intentos` y `disponible_en` para reintentos automáticos con backoff
- trigger AFTER INSERT que hace pg_notify('trabajo_nuevo', id) para que el
  satélite despache al instante (LISTEN/NOTIFY) en vez de solo hacer polling
"""

revision = 'i2c3d4e5f6a7'
down_revision = 'h1b2c3d4e5f6'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

_NOTIFY_FN = """
CREATE OR REPLACE FUNCTION notify_trabajo_nuevo() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('trabajo_nuevo', NEW.id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_NOTIFY_TRIGGER = """
CREATE TRIGGER trabajo_notify_insert
AFTER INSERT ON trabajo
FOR EACH ROW EXECUTE FUNCTION notify_trabajo_nuevo();
"""


def upgrade() -> None:
    op.add_column('trabajo', sa.Column('intentos', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('trabajo', sa.Column('disponible_en', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_trabajo_disponible_en'), 'trabajo', ['disponible_en'], unique=False)
    op.execute(_NOTIFY_FN)
    op.execute(_NOTIFY_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trabajo_notify_insert ON trabajo")
    op.execute("DROP FUNCTION IF EXISTS notify_trabajo_nuevo()")
    op.drop_index(op.f('ix_trabajo_disponible_en'), table_name='trabajo')
    op.drop_column('trabajo', 'disponible_en')
    op.drop_column('trabajo', 'intentos')
