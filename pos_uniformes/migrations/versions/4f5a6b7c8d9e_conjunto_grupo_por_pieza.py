"""Repara el `grupo` de las recetas que ya existían: la columna se agregó con
0 para todas, así que dos piezas distintas del mismo conjunto se leían como
alternativas ("se arma de Pants 2pz **o** Playera"). El grupo se recalcula por
tipo de pieza y signo: piezas de distinto tipo van en grupos distintos (se
llevan todas) y dos del mismo tipo siguen juntas (playera de hombre o de
mujer, que es lo que sí es una alternativa).

Revision ID: 4f5a6b7c8d9e
Revises: 3e4f5a6b7c8d
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "4f5a6b7c8d9e"
down_revision = "3e4f5a6b7c8d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    filas = bind.execute(sa.text("""
        SELECT cc.id, cc.conjunto_id, cc.cantidad, p.tipo_pieza_id
        FROM conjunto_componente cc JOIN producto p ON p.id = cc.componente_id
        ORDER BY cc.conjunto_id, cc.id
    """)).all()
    grupos_por_conjunto: dict[int, dict[tuple, int]] = {}
    for cid, conjunto_id, cantidad, tipo_pieza_id in filas:
        clave = (int(cantidad) > 0, tipo_pieza_id)
        vistos = grupos_por_conjunto.setdefault(int(conjunto_id), {})
        grupo = vistos.setdefault(clave, len(vistos))
        bind.execute(
            sa.text("UPDATE conjunto_componente SET grupo = :g WHERE id = :i"),
            {"g": grupo, "i": int(cid)},
        )


def downgrade() -> None:
    op.get_bind().execute(sa.text("UPDATE conjunto_componente SET grupo = 0"))
