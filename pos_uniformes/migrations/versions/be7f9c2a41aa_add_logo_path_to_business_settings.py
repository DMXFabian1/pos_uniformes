"""add logo path to business settings

Revision ID: be7f9c2a41aa
Revises: a1c8d4e7b233
Create Date: 2026-03-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "be7f9c2a41aa"
down_revision = "a1c8d4e7b233"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("configuracion_negocio", sa.Column("logo_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("configuracion_negocio", "logo_path")
