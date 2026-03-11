"""add cash movements

Revision ID: e2b4c6d8f901
Revises: cc8a1e7d0f42
Create Date: 2026-03-11 21:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "e2b4c6d8f901"
down_revision = "cc8a1e7d0f42"
branch_labels = None
depends_on = None


cash_movement_enum = sa.Enum(
    "REACTIVO",
    "INGRESO",
    "RETIRO",
    name="tipo_movimiento_caja",
)

cash_movement_column_enum = postgresql.ENUM(
    "REACTIVO",
    "INGRESO",
    "RETIRO",
    name="tipo_movimiento_caja",
    create_type=False,
)


def upgrade() -> None:
    cash_movement_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "movimiento_caja",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sesion_caja_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("tipo", cash_movement_column_enum, nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("concepto", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["sesion_caja_id"], ["sesion_caja.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_movimiento_caja_sesion_caja_id"), "movimiento_caja", ["sesion_caja_id"], unique=False)
    op.create_index(op.f("ix_movimiento_caja_usuario_id"), "movimiento_caja", ["usuario_id"], unique=False)
    op.create_index(op.f("ix_movimiento_caja_tipo"), "movimiento_caja", ["tipo"], unique=False)
    op.create_index(op.f("ix_movimiento_caja_created_at"), "movimiento_caja", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_movimiento_caja_created_at"), table_name="movimiento_caja")
    op.drop_index(op.f("ix_movimiento_caja_tipo"), table_name="movimiento_caja")
    op.drop_index(op.f("ix_movimiento_caja_usuario_id"), table_name="movimiento_caja")
    op.drop_index(op.f("ix_movimiento_caja_sesion_caja_id"), table_name="movimiento_caja")
    op.drop_table("movimiento_caja")
    cash_movement_enum.drop(op.get_bind(), checkfirst=True)
