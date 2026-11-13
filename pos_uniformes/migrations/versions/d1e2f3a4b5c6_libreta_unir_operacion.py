"""libreta_venta: unir dos ventas en UNA operación (2026-11-13).

Daniel: «a veces mis empleadas venden e imprimen el ticket, pero esa misma
persona se decide y se lleva otra cosa, haciendo que sean dos operaciones y
solo debería ser una». Las dos ventas siguen valiendo (dinero, piezas,
comisiones, existencia y Monedero no cambian): solo se cuentan como 1.

Agrega a `libreta_venta`:

- `operacion_grupo_id`: el id de la primera venta del grupo (todas las del
  grupo lo guardan, la primera también). NULL = venta sola. FK a la misma
  tabla con ON DELETE SET NULL: si alguien borra la primera por fuera del
  servicio, el grupo se deshace en vez de apuntar a la nada (contar de más
  es el lado seguro).
- `operacion_unida_por` y `operacion_unida_en`: el rastro (quién y cuándo).

Columnas nuevas y vacías: no hay backfill. Solo se aplica en la caja con el
sí de Daniel. El downgrade las quita (se pierden las uniones hechas, nada
más: las ventas quedan intactas).

Revision ID: d1e2f3a4b5c6
Revises: c9a4e2b7d1f3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "c9a4e2b7d1f3"
branch_labels = None
depends_on = None

FK_GRUPO = "fk_libreta_venta_operacion_grupo_id_libreta_venta"
IX_GRUPO = "ix_libreta_venta_operacion_grupo_id"


def upgrade() -> None:
    with op.batch_alter_table("libreta_venta") as b:
        b.add_column(sa.Column("operacion_grupo_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("operacion_unida_por", sa.String(40), nullable=True))
        b.add_column(sa.Column("operacion_unida_en", sa.DateTime(timezone=True), nullable=True))
        b.create_foreign_key(FK_GRUPO, "libreta_venta", ["operacion_grupo_id"], ["id"], ondelete="SET NULL")
        b.create_index(IX_GRUPO, ["operacion_grupo_id"])


def downgrade() -> None:
    with op.batch_alter_table("libreta_venta") as b:
        b.drop_index(IX_GRUPO)
        b.drop_constraint(FK_GRUPO, type_="foreignkey")
        b.drop_column("operacion_unida_en")
        b.drop_column("operacion_unida_por")
        b.drop_column("operacion_grupo_id")
