"""Avisos: vencimiento propio y acuse de recibo.

Dos huecos que se vieron al poder mandar un aviso desde Telegram (Daniel,
01/10): mandado de lejos, nadie vuelve a pasar a apagarlo, y nadie contesta.

- `anuncio.expira_en`: deja de verse solo. NULL = como hasta ahora.
- `anuncio.pide_acuse`: pide que alguien toque «Enterada».
- `anuncio_visto`: una fila por (anuncio, pantalla) con quién tocó y cuándo.
  Único por pantalla — el segundo toque no agrega renglones.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("anuncio", sa.Column("expira_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "anuncio",
        sa.Column("pide_acuse", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_table(
        "anuncio_visto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("anuncio_id", sa.Integer(), nullable=False),
        sa.Column("satelite", sa.String(length=80), nullable=False),
        sa.Column("satelite_nombre", sa.String(length=80), nullable=True),
        sa.Column("empleada", sa.String(length=80), nullable=True),
        sa.Column(
            "visto_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["anuncio_id"], ["anuncio.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("anuncio_id", "satelite", name="uq_anuncio_visto_pantalla"),
    )
    op.create_index(
        op.f("ix_anuncio_visto_anuncio_id"), "anuncio_visto", ["anuncio_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_anuncio_visto_anuncio_id"), table_name="anuncio_visto")
    op.drop_table("anuncio_visto")
    op.drop_column("anuncio", "pide_acuse")
    op.drop_column("anuncio", "expira_en")
