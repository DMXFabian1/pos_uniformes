"""add layaway tables

Revision ID: c9f4b8a1d211
Revises: b3e41f7b7d2c
Create Date: 2026-03-10 19:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c9f4b8a1d211"
down_revision = "b3e41f7b7d2c"
branch_labels = None
depends_on = None


estado_apartado_enum = postgresql.ENUM(
    "ACTIVO",
    "LIQUIDADO",
    "ENTREGADO",
    "CANCELADO",
    name="estado_apartado",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum
                    WHERE enumlabel = 'APARTADO_RESERVA'
                    AND enumtypid = 'tipo_movimiento_inventario'::regtype
                ) THEN
                    ALTER TYPE tipo_movimiento_inventario ADD VALUE 'APARTADO_RESERVA';
                END IF;
            END
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum
                    WHERE enumlabel = 'APARTADO_LIBERACION'
                    AND enumtypid = 'tipo_movimiento_inventario'::regtype
                ) THEN
                    ALTER TYPE tipo_movimiento_inventario ADD VALUE 'APARTADO_LIBERACION';
                END IF;
            END
            $$;
            """
        )
    )

    postgresql.ENUM(
        "ACTIVO",
        "LIQUIDADO",
        "ENTREGADO",
        "CANCELADO",
        name="estado_apartado",
    ).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "apartado",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("cancelado_por_id", sa.Integer(), nullable=True),
        sa.Column("entregado_por_id", sa.Integer(), nullable=True),
        sa.Column("folio", sa.String(length=40), nullable=False),
        sa.Column("cliente_nombre", sa.String(length=150), nullable=False),
        sa.Column("cliente_telefono", sa.String(length=40), nullable=True),
        sa.Column("estado", estado_apartado_enum, nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("total_abonado", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("saldo_pendiente", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("fecha_compromiso", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column("liquidado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entregado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["cancelado_por_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["entregado_por_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_apartado")),
        sa.UniqueConstraint("folio", name=op.f("uq_apartado_folio")),
    )
    op.create_index(op.f("ix_apartado_usuario_id"), "apartado", ["usuario_id"], unique=False)
    op.create_index(op.f("ix_apartado_cancelado_por_id"), "apartado", ["cancelado_por_id"], unique=False)
    op.create_index(op.f("ix_apartado_entregado_por_id"), "apartado", ["entregado_por_id"], unique=False)
    op.create_index(op.f("ix_apartado_cliente_nombre"), "apartado", ["cliente_nombre"], unique=False)
    op.create_index(op.f("ix_apartado_estado"), "apartado", ["estado"], unique=False)
    op.create_index(op.f("ix_apartado_folio"), "apartado", ["folio"], unique=False)

    op.create_table(
        "apartado_detalle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("apartado_id", sa.Integer(), nullable=False),
        sa.Column("variante_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(10, 2), nullable=False),
        sa.Column("subtotal_linea", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("cantidad > 0", name="apartado_detalle_cantidad_positiva"),
        sa.CheckConstraint("precio_unitario >= 0", name="apartado_detalle_precio_unitario_no_negativo"),
        sa.ForeignKeyConstraint(["apartado_id"], ["apartado.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variante_id"], ["variante.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_apartado_detalle")),
        sa.UniqueConstraint("apartado_id", "variante_id", name="apartado_detalle_variante_unica"),
    )
    op.create_index(op.f("ix_apartado_detalle_apartado_id"), "apartado_detalle", ["apartado_id"], unique=False)
    op.create_index(op.f("ix_apartado_detalle_variante_id"), "apartado_detalle", ["variante_id"], unique=False)

    op.create_table(
        "apartado_abono",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("apartado_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("referencia", sa.String(length=120), nullable=True),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("monto > 0", name="apartado_abono_monto_positivo"),
        sa.ForeignKeyConstraint(["apartado_id"], ["apartado.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_apartado_abono")),
    )
    op.create_index(op.f("ix_apartado_abono_apartado_id"), "apartado_abono", ["apartado_id"], unique=False)
    op.create_index(op.f("ix_apartado_abono_usuario_id"), "apartado_abono", ["usuario_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_apartado_abono_usuario_id"), table_name="apartado_abono")
    op.drop_index(op.f("ix_apartado_abono_apartado_id"), table_name="apartado_abono")
    op.drop_table("apartado_abono")

    op.drop_index(op.f("ix_apartado_detalle_variante_id"), table_name="apartado_detalle")
    op.drop_index(op.f("ix_apartado_detalle_apartado_id"), table_name="apartado_detalle")
    op.drop_table("apartado_detalle")

    op.drop_index(op.f("ix_apartado_folio"), table_name="apartado")
    op.drop_index(op.f("ix_apartado_estado"), table_name="apartado")
    op.drop_index(op.f("ix_apartado_cliente_nombre"), table_name="apartado")
    op.drop_index(op.f("ix_apartado_entregado_por_id"), table_name="apartado")
    op.drop_index(op.f("ix_apartado_cancelado_por_id"), table_name="apartado")
    op.drop_index(op.f("ix_apartado_usuario_id"), table_name="apartado")
    op.drop_table("apartado")

    estado_apartado_enum.drop(op.get_bind(), checkfirst=True)
