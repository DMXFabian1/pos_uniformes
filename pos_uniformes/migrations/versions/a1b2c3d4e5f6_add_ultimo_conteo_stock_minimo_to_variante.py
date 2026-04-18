"""add ultimo_conteo_at and stock_minimo to variante"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("variante", sa.Column("ultimo_conteo_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("variante", sa.Column("stock_minimo", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("variante", "stock_minimo")
    op.drop_column("variante", "ultimo_conteo_at")
