"""add employee pin hash

Revision ID: c2f4d8a1b901
Revises: b1d8f0e4c231
Create Date: 2026-04-09 23:55:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c2f4d8a1b901"
down_revision = "b1d8f0e4c231"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("empleada", sa.Column("pin_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("empleada", "pin_hash")
