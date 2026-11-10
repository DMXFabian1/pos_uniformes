"""E1-C0: catálogo de tipos de cliente y archivado reversible (solo agrega).

- Tabla `cliente_tipo` con exactamente GENERAL, DOCENTE, MAYORISTA e
  INSTITUCION (P1). Un tipo es una etiqueta: no da nivel ni beneficio.
- `cliente.tipo_cliente_id` (admite vacío): el tipo del catálogo. No se
  rellena desde el enum viejo: las fichas actuales son de prueba y se archivan
  (C15). El enum `tipo_cliente` no se toca.
- `cliente.archivado_en` y `cliente.archivado_motivo` (admiten vacío): el
  archivado reversible de C12. Ninguna fila cambia en esta migración.

El `downgrade` se detiene antes de perder información (K7): si alguna ficha
ya tiene tipo del catálogo o está archivada, salvo
`POS_E1C0_DOWNGRADE_ACEPTO_PERDIDA=1`.

Revision ID: 15f0e6fd053a
Revises: e767eaf1db92
"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "15f0e6fd053a"
down_revision = "e767eaf1db92"
branch_labels = None
depends_on = None

ENV_ACEPTO_PERDIDA = "POS_E1C0_DOWNGRADE_ACEPTO_PERDIDA"

TIPOS_INICIALES = (
    ("GENERAL", "General", 1),
    ("DOCENTE", "Docente", 2),
    ("MAYORISTA", "Mayorista", 3),
    ("INSTITUCION", "Institución", 4),
)


def upgrade() -> None:
    tabla = op.create_table(
        "cliente_tipo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clave", sa.String(length=30), nullable=False),
        sa.Column("nombre", sa.String(length=60), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("orden", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("clave", name="uq_cliente_tipo_clave"),
    )
    op.bulk_insert(
        tabla,
        [{"clave": clave, "nombre": nombre, "orden": orden} for clave, nombre, orden in TIPOS_INICIALES],
    )

    op.add_column(
        "cliente",
        sa.Column(
            "tipo_cliente_id",
            sa.Integer(),
            sa.ForeignKey("cliente_tipo.id", ondelete="RESTRICT", name="fk_cliente_tipo_cliente_id"),
            nullable=True,
        ),
    )
    op.create_index("ix_cliente_tipo_cliente_id", "cliente", ["tipo_cliente_id"], unique=False)
    op.add_column("cliente", sa.Column("archivado_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cliente", sa.Column("archivado_motivo", sa.String(length=255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    con_tipo = bind.execute(sa.text("SELECT count(*) FROM cliente WHERE tipo_cliente_id IS NOT NULL")).scalar_one()
    archivados = bind.execute(sa.text("SELECT count(*) FROM cliente WHERE archivado_en IS NOT NULL")).scalar_one()
    if (con_tipo or archivados) and os.environ.get(ENV_ACEPTO_PERDIDA) != "1":
        raise RuntimeError(
            f"Downgrade E1-C0 detenido: se perdería el tipo de {con_tipo} ficha(s) y el archivado de "
            f"{archivados}. Exporta esas columnas y, si aceptas la pérdida, repite con {ENV_ACEPTO_PERDIDA}=1."
        )

    op.drop_column("cliente", "archivado_motivo")
    op.drop_column("cliente", "archivado_en")
    op.drop_index("ix_cliente_tipo_cliente_id", table_name="cliente")
    op.drop_constraint("fk_cliente_tipo_cliente_id", "cliente", type_="foreignkey")
    op.drop_column("cliente", "tipo_cliente_id")
    op.drop_table("cliente_tipo")
