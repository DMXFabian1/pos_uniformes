"""add quotes tables

Revision ID: 5e2c1a7b9d44
Revises: 1d4e7f9a2c11
Create Date: 2026-03-11 18:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "5e2c1a7b9d44"
down_revision = "1d4e7f9a2c11"
branch_labels = None
depends_on = None


estado_presupuesto = postgresql.ENUM(
    "BORRADOR",
    "EMITIDO",
    "CANCELADO",
    "CONVERTIDO",
    name="estado_presupuesto",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(
        "BORRADOR",
        "EMITIDO",
        "CANCELADO",
        "CONVERTIDO",
        name="estado_presupuesto",
    ).create(bind, checkfirst=True)

    op.create_table(
        "presupuesto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("folio", sa.String(length=40), nullable=False),
        sa.Column("cliente_nombre", sa.String(length=150), nullable=True),
        sa.Column("cliente_telefono", sa.String(length=40), nullable=True),
        sa.Column("estado", estado_presupuesto, nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("vigencia_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column("emitido_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("convertido_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cliente_id"], ["cliente.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_presupuesto")),
        sa.UniqueConstraint("folio", name=op.f("uq_presupuesto_folio")),
    )
    op.create_index(op.f("ix_presupuesto_cliente_id"), "presupuesto", ["cliente_id"], unique=False)
    op.create_index(op.f("ix_presupuesto_cliente_nombre"), "presupuesto", ["cliente_nombre"], unique=False)
    op.create_index(op.f("ix_presupuesto_created_at"), "presupuesto", ["created_at"], unique=False)
    op.create_index(op.f("ix_presupuesto_estado"), "presupuesto", ["estado"], unique=False)
    op.create_index(op.f("ix_presupuesto_folio"), "presupuesto", ["folio"], unique=True)
    op.create_index(op.f("ix_presupuesto_usuario_id"), "presupuesto", ["usuario_id"], unique=False)
    op.create_index(op.f("ix_presupuesto_vigencia_hasta"), "presupuesto", ["vigencia_hasta"], unique=False)

    op.create_table(
        "presupuesto_detalle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("presupuesto_id", sa.Integer(), nullable=False),
        sa.Column("variante_id", sa.Integer(), nullable=True),
        sa.Column("sku_snapshot", sa.String(length=64), nullable=False),
        sa.Column("descripcion_snapshot", sa.String(length=220), nullable=False),
        sa.Column("talla_snapshot", sa.String(length=30), nullable=True),
        sa.Column("color_snapshot", sa.String(length=50), nullable=True),
        sa.Column("precio_unitario", sa.Numeric(10, 2), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("subtotal_linea", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("cantidad > 0", name=op.f("ck_presupuesto_detalle_presupuesto_detalle_cantidad_positiva")),
        sa.CheckConstraint(
            "precio_unitario >= 0",
            name=op.f("ck_presupuesto_detalle_presupuesto_detalle_precio_unitario_no_negativo"),
        ),
        sa.ForeignKeyConstraint(["presupuesto_id"], ["presupuesto.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variante_id"], ["variante.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_presupuesto_detalle")),
        sa.UniqueConstraint("presupuesto_id", "sku_snapshot", name=op.f("uq_presupuesto_detalle_presupuesto_id")),
    )
    op.create_index(op.f("ix_presupuesto_detalle_presupuesto_id"), "presupuesto_detalle", ["presupuesto_id"], unique=False)
    op.create_index(op.f("ix_presupuesto_detalle_sku_snapshot"), "presupuesto_detalle", ["sku_snapshot"], unique=False)
    op.create_index(op.f("ix_presupuesto_detalle_variante_id"), "presupuesto_detalle", ["variante_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_presupuesto_detalle_variante_id"), table_name="presupuesto_detalle")
    op.drop_index(op.f("ix_presupuesto_detalle_sku_snapshot"), table_name="presupuesto_detalle")
    op.drop_index(op.f("ix_presupuesto_detalle_presupuesto_id"), table_name="presupuesto_detalle")
    op.drop_table("presupuesto_detalle")

    op.drop_index(op.f("ix_presupuesto_vigencia_hasta"), table_name="presupuesto")
    op.drop_index(op.f("ix_presupuesto_usuario_id"), table_name="presupuesto")
    op.drop_index(op.f("ix_presupuesto_folio"), table_name="presupuesto")
    op.drop_index(op.f("ix_presupuesto_estado"), table_name="presupuesto")
    op.drop_index(op.f("ix_presupuesto_created_at"), table_name="presupuesto")
    op.drop_index(op.f("ix_presupuesto_cliente_nombre"), table_name="presupuesto")
    op.drop_index(op.f("ix_presupuesto_cliente_id"), table_name="presupuesto")
    op.drop_table("presupuesto")

    bind = op.get_bind()
    postgresql.ENUM(
        "BORRADOR",
        "EMITIDO",
        "CANCELADO",
        "CONVERTIDO",
        name="estado_presupuesto",
    ).drop(bind, checkfirst=True)
