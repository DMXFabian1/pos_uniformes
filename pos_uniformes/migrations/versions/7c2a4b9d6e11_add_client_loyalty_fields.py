"""add client loyalty fields

Revision ID: 7c2a4b9d6e11
Revises: 6f3b2c8d1a55
Create Date: 2026-03-11 21:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "7c2a4b9d6e11"
down_revision = "6f3b2c8d1a55"
branch_labels = None
depends_on = None


nivel_lealtad_enum = postgresql.ENUM(
    "BASICO",
    "LEAL",
    "PROFESOR",
    "MAYORISTA",
    name="nivel_lealtad",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(
        "BASICO",
        "LEAL",
        "PROFESOR",
        "MAYORISTA",
        name="nivel_lealtad",
    ).create(bind, checkfirst=True)

    op.add_column(
        "cliente",
        sa.Column(
            "nivel_lealtad",
            nivel_lealtad_enum,
            nullable=False,
            server_default="BASICO",
        ),
    )
    op.add_column(
        "cliente",
        sa.Column(
            "cliente_desde",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column("cliente", sa.Column("nivel_asignado_por_user_id", sa.Integer(), nullable=True))
    op.add_column("cliente", sa.Column("nivel_asignado_por_rol", sa.String(length=20), nullable=True))
    op.add_column("cliente", sa.Column("nivel_asignacion_motivo", sa.String(length=255), nullable=True))
    op.add_column("cliente", sa.Column("card_image_path", sa.Text(), nullable=True))

    op.create_index(op.f("ix_cliente_nivel_lealtad"), "cliente", ["nivel_lealtad"], unique=False)
    op.create_index(op.f("ix_cliente_nivel_asignado_por_user_id"), "cliente", ["nivel_asignado_por_user_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_cliente_nivel_asignado_por_user_id_usuario"),
        "cliente",
        "usuario",
        ["nivel_asignado_por_user_id"],
        ["id"],
    )

    op.execute(
        """
        UPDATE cliente
        SET nivel_lealtad = CASE
            WHEN tipo_cliente = 'PROFESOR' THEN 'PROFESOR'::nivel_lealtad
            WHEN tipo_cliente = 'MAYORISTA' THEN 'MAYORISTA'::nivel_lealtad
            ELSE 'BASICO'::nivel_lealtad
        END,
        cliente_desde = COALESCE(created_at, CURRENT_TIMESTAMP),
        nivel_asignado_por_rol = 'MIGRACION',
        nivel_asignacion_motivo = 'migracion_inicial'
        """
    )

    op.alter_column("cliente", "nivel_lealtad", server_default=None)
    op.drop_column("cliente", "direccion")
    op.drop_column("cliente", "email")


def downgrade() -> None:
    op.add_column("cliente", sa.Column("email", sa.String(length=120), nullable=True))
    op.add_column("cliente", sa.Column("direccion", sa.Text(), nullable=True))
    op.drop_constraint(op.f("fk_cliente_nivel_asignado_por_user_id_usuario"), "cliente", type_="foreignkey")
    op.drop_index(op.f("ix_cliente_nivel_asignado_por_user_id"), table_name="cliente")
    op.drop_index(op.f("ix_cliente_nivel_lealtad"), table_name="cliente")
    op.drop_column("cliente", "card_image_path")
    op.drop_column("cliente", "nivel_asignacion_motivo")
    op.drop_column("cliente", "nivel_asignado_por_rol")
    op.drop_column("cliente", "nivel_asignado_por_user_id")
    op.drop_column("cliente", "cliente_desde")
    op.drop_column("cliente", "nivel_lealtad")
    bind = op.get_bind()
    postgresql.ENUM(
        "BASICO",
        "LEAL",
        "PROFESOR",
        "MAYORISTA",
        name="nivel_lealtad",
    ).drop(bind, checkfirst=True)
