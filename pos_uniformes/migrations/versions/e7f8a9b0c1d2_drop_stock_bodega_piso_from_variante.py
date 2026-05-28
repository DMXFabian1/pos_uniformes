"""drop stock_bodega and stock_piso from variante

These fields are now derived from bodega_contenido tables at query time,
eliminating sync issues between bodega operations and inventory display.
"""

from alembic import op
import sqlalchemy as sa

revision = "e7f8a9b0c1d2"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_variante_stock_piso_no_negativo", "variante", type_="check")
    op.drop_constraint("ck_variante_stock_bodega_no_negativo", "variante", type_="check")
    op.drop_column("variante", "stock_piso")
    op.drop_column("variante", "stock_bodega")


def downgrade() -> None:
    op.add_column(
        "variante",
        sa.Column("stock_bodega", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "variante",
        sa.Column("stock_piso", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_variante_stock_bodega_no_negativo",
        "variante",
        "stock_bodega >= 0",
    )
    op.create_check_constraint(
        "ck_variante_stock_piso_no_negativo",
        "variante",
        "stock_piso >= 0",
    )
