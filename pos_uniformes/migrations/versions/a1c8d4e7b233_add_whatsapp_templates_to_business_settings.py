"""add whatsapp templates to business settings

Revision ID: a1c8d4e7b233
Revises: 9c3f5d7a1b22
Create Date: 2026-03-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1c8d4e7b233"
down_revision = "9c3f5d7a1b22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("configuracion_negocio", sa.Column("whatsapp_apartado_recordatorio", sa.Text(), nullable=True))
    op.add_column("configuracion_negocio", sa.Column("whatsapp_apartado_liquidado", sa.Text(), nullable=True))
    op.add_column("configuracion_negocio", sa.Column("whatsapp_cliente_promocion", sa.Text(), nullable=True))
    op.add_column("configuracion_negocio", sa.Column("whatsapp_cliente_seguimiento", sa.Text(), nullable=True))
    op.add_column("configuracion_negocio", sa.Column("whatsapp_cliente_saludo", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("configuracion_negocio", "whatsapp_cliente_saludo")
    op.drop_column("configuracion_negocio", "whatsapp_cliente_seguimiento")
    op.drop_column("configuracion_negocio", "whatsapp_cliente_promocion")
    op.drop_column("configuracion_negocio", "whatsapp_apartado_liquidado")
    op.drop_column("configuracion_negocio", "whatsapp_apartado_recordatorio")
