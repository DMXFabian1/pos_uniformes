"""Una pieza del conjunto puede ser "cualquiera de estas": las piezas con el
mismo `grupo` son alternativas. Daniel, 2026-09-22: "el SABES puede llevar de
hombre o de mujer playera deportiva". Ver Obsidian 38 §5b.

Va aparte de `2d3e4f5a6b7c` porque esa ya corrió en la PC principal.

Revision ID: 3e4f5a6b7c8d
Revises: 2d3e4f5a6b7c
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "3e4f5a6b7c8d"
down_revision = "2d3e4f5a6b7c"
branch_labels = None
depends_on = None


def _tiene_grupo() -> bool:
    return any(
        c["name"] == "grupo"
        for c in sa.inspect(op.get_bind()).get_columns("conjunto_componente")
    )


def upgrade() -> None:
    # Las copias de trabajo ya la traen (la tabla se creó con ella antes de
    # separar la migración): ahí no hay nada que agregar.
    if not _tiene_grupo():
        op.add_column("conjunto_componente", sa.Column("grupo", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    if _tiene_grupo():
        op.drop_column("conjunto_componente", "grupo")
