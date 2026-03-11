"""add cash session table"""

from alembic import op
import sqlalchemy as sa


revision = "f18b4f9a2c31"
down_revision = "d4a2f1c77b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sesion_caja",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("abierta_por_id", sa.Integer(), nullable=False),
        sa.Column("cerrada_por_id", sa.Integer(), nullable=True),
        sa.Column("monto_apertura", sa.Numeric(12, 2), nullable=False),
        sa.Column("monto_cierre_declarado", sa.Numeric(12, 2), nullable=True),
        sa.Column("monto_esperado_cierre", sa.Numeric(12, 2), nullable=True),
        sa.Column("diferencia_cierre", sa.Numeric(12, 2), nullable=True),
        sa.Column("observacion_apertura", sa.Text(), nullable=True),
        sa.Column("observacion_cierre", sa.Text(), nullable=True),
        sa.Column("abierta_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("cerrada_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["abierta_por_id"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["cerrada_por_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sesion_caja_abierta_at"), "sesion_caja", ["abierta_at"], unique=False)
    op.create_index(op.f("ix_sesion_caja_abierta_por_id"), "sesion_caja", ["abierta_por_id"], unique=False)
    op.create_index(op.f("ix_sesion_caja_cerrada_at"), "sesion_caja", ["cerrada_at"], unique=False)
    op.create_index(op.f("ix_sesion_caja_cerrada_por_id"), "sesion_caja", ["cerrada_por_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sesion_caja_cerrada_por_id"), table_name="sesion_caja")
    op.drop_index(op.f("ix_sesion_caja_cerrada_at"), table_name="sesion_caja")
    op.drop_index(op.f("ix_sesion_caja_abierta_por_id"), table_name="sesion_caja")
    op.drop_index(op.f("ix_sesion_caja_abierta_at"), table_name="sesion_caja")
    op.drop_table("sesion_caja")
