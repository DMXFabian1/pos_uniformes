"""Las fechas de las temporadas se pueden mover desde el menú.

Daniel, 2026-10-10: el sistema de temas debe permitir cambiar el inicio, el
final y la prioridad de cada temporada sin tocar código. Vive en
`configuracion_negocio` junto al modo, porque es de la TIENDA; el kiosko lo
cachea en `temporada_fechas.json` para cuando no hay red. Lo que no esté aquí
se queda con el calendario de fábrica de `temporada_service.TEMPORADAS`.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "configuracion_negocio",
        sa.Column(
            "temporada_fechas",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("configuracion_negocio", "temporada_fechas")
