"""La Licra no tenía tipo de pieza, así que el mapa de conteos le hacía un
mosaico aparte llamado "Sin tipo" (Daniel, 2026-09-22: "siento que desentona,
es la licra"). Se le da su propio tipo, junto a la malla.

Revision ID: 5a6b7c8d9e0f
Revises: 4f5a6b7c8d9e
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5a6b7c8d9e0f"
down_revision = "4f5a6b7c8d9e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tipo_id = bind.execute(sa.text("SELECT id FROM tipo_pieza WHERE nombre = 'Licra'")).scalar()
    if tipo_id is None:
        tipo_id = bind.execute(
            sa.text("INSERT INTO tipo_pieza (nombre) VALUES ('Licra') RETURNING id")
        ).scalar()
    # Solo las que se llaman Licra y no tienen tipo: nada más se toca.
    bind.execute(
        sa.text("UPDATE producto SET tipo_pieza_id = :t WHERE tipo_pieza_id IS NULL AND nombre ILIKE 'licra%'"),
        {"t": tipo_id},
    )


def downgrade() -> None:
    bind = op.get_bind()
    tipo_id = bind.execute(sa.text("SELECT id FROM tipo_pieza WHERE nombre = 'Licra'")).scalar()
    if tipo_id is None:
        return
    bind.execute(sa.text("UPDATE producto SET tipo_pieza_id = NULL WHERE tipo_pieza_id = :t"), {"t": tipo_id})
    bind.execute(sa.text("DELETE FROM tipo_pieza WHERE id = :t"), {"t": tipo_id})
