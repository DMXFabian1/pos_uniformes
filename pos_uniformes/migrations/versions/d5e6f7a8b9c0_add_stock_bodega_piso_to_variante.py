"""add stock_bodega and stock_piso to variante

Agrega columnas para desglose de stock por ubicación:
- stock_bodega: unidades en almacén externo
- stock_piso: unidades en caja / piso de tienda
- stock en tienda (estantes) se calcula: stock_actual - stock_bodega - stock_piso
"""

from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "29e11361cabd"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_constraint("ck_variante_stock_piso_no_negativo", "variante", type_="check")
    op.drop_constraint("ck_variante_stock_bodega_no_negativo", "variante", type_="check")
    op.drop_column("variante", "stock_piso")
    op.drop_column("variante", "stock_bodega")
