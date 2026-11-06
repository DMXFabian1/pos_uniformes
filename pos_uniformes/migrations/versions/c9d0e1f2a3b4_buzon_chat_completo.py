"""El buzón como chat completo: respuestas, estado del comando, borrar, imágenes y palomitas.

Daniel, 2026-11-06: «¿qué otra cosa mejorarías de este sistema de mensajes?» →
«hazlo completo».

- `buzon_mensaje.responde_a`: a qué mensaje contesta (el resultado va pegado a
  su comando; también las respuestas a mano).
- `buzon_mensaje.estado`: "recibido" | "ok" | "error" en lo que contesta a un comando.
- `buzon_mensaje.borrado_at`: se borró (el renglón queda, sin texto).
- `buzon_mensaje.adjunto` + tabla `buzon_adjunto`: una captura pegada.
- tabla `buzon_leido`: hasta dónde leyó cada PC cada chat (las palomitas).

Solo agrega columnas opcionales y dos tablas; no toca mensajes existentes.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("buzon_mensaje", sa.Column("responde_a", sa.Integer(), nullable=True))
    op.create_index("ix_buzon_mensaje_responde_a", "buzon_mensaje", ["responde_a"])
    op.add_column("buzon_mensaje", sa.Column("estado", sa.String(12), nullable=True))
    op.add_column("buzon_mensaje", sa.Column("borrado_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "buzon_mensaje",
        sa.Column("adjunto", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "buzon_adjunto",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "mensaje_id", sa.Integer(),
            sa.ForeignKey("buzon_mensaje.id", ondelete="CASCADE"), nullable=False, unique=True,
        ),
        sa.Column("datos", sa.LargeBinary(), nullable=False),
    )
    op.create_table(
        "buzon_leido",
        sa.Column("lector", sa.String(60), primary_key=True),
        sa.Column("chat", sa.String(60), primary_key=True),
        sa.Column("hasta_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("buzon_leido")
    op.drop_table("buzon_adjunto")
    op.drop_column("buzon_mensaje", "adjunto")
    op.drop_column("buzon_mensaje", "borrado_at")
    op.drop_column("buzon_mensaje", "estado")
    op.drop_index("ix_buzon_mensaje_responde_a", table_name="buzon_mensaje")
    op.drop_column("buzon_mensaje", "responde_a")
