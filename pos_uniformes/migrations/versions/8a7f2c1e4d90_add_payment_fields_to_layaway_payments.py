"""add payment fields to layaway payments"""

from alembic import op
import sqlalchemy as sa


revision = "8a7f2c1e4d90"
down_revision = "f18b4f9a2c31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("apartado_abono", sa.Column("metodo_pago", sa.String(length=30), nullable=True))
    op.add_column("apartado_abono", sa.Column("monto_efectivo", sa.Numeric(12, 2), nullable=True))
    op.create_check_constraint(
        "apartado_abono_monto_efectivo_no_negativo",
        "apartado_abono",
        "monto_efectivo IS NULL OR monto_efectivo >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("apartado_abono_monto_efectivo_no_negativo", "apartado_abono", type_="check")
    op.drop_column("apartado_abono", "monto_efectivo")
    op.drop_column("apartado_abono", "metodo_pago")
