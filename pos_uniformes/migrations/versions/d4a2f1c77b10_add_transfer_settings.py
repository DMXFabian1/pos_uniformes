"""add transfer settings to business config"""

from alembic import op
import sqlalchemy as sa


revision = "d4a2f1c77b10"
down_revision = "c9f4b8a1d211"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("configuracion_negocio", sa.Column("transferencia_banco", sa.String(length=120), nullable=True))
    op.add_column(
        "configuracion_negocio",
        sa.Column("transferencia_beneficiario", sa.String(length=160), nullable=True),
    )
    op.add_column("configuracion_negocio", sa.Column("transferencia_clabe", sa.String(length=40), nullable=True))
    op.add_column("configuracion_negocio", sa.Column("transferencia_instrucciones", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("configuracion_negocio", "transferencia_instrucciones")
    op.drop_column("configuracion_negocio", "transferencia_clabe")
    op.drop_column("configuracion_negocio", "transferencia_beneficiario")
    op.drop_column("configuracion_negocio", "transferencia_banco")
