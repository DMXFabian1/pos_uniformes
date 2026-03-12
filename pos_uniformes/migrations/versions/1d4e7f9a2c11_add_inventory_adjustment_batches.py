"""add inventory adjustment batches

Revision ID: 1d4e7f9a2c11
Revises: 9c5d8a4b12ef
Create Date: 2026-03-11 19:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1d4e7f9a2c11"
down_revision = "9c5d8a4b12ef"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ajuste_inventario_lote",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("tipo_fuente", sa.String(length=30), server_default="SELECCION", nullable=False),
        sa.Column("tipo_ajuste", sa.String(length=30), server_default="STOCK_FINAL", nullable=False),
        sa.Column("referencia", sa.String(length=120), nullable=False),
        sa.Column("motivo", sa.String(length=160), nullable=False),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column("total_filas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("filas_validas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("filas_error", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unidades_positivas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unidades_negativas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], name=op.f("fk_ajuste_inventario_lote_usuario_id_usuario"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ajuste_inventario_lote")),
    )
    op.create_index(op.f("ix_ajuste_inventario_lote_created_at"), "ajuste_inventario_lote", ["created_at"], unique=False)
    op.create_index(op.f("ix_ajuste_inventario_lote_referencia"), "ajuste_inventario_lote", ["referencia"], unique=False)
    op.create_index(op.f("ix_ajuste_inventario_lote_usuario_id"), "ajuste_inventario_lote", ["usuario_id"], unique=False)

    op.create_table(
        "ajuste_inventario_lote_detalle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lote_id", sa.Integer(), nullable=False),
        sa.Column("variante_id", sa.Integer(), nullable=False),
        sa.Column("sku_snapshot", sa.String(length=64), nullable=False),
        sa.Column("stock_anterior", sa.Integer(), nullable=False),
        sa.Column("apartado_comprometido", sa.Integer(), server_default="0", nullable=False),
        sa.Column("valor_capturado", sa.Integer(), nullable=False),
        sa.Column("delta_aplicado", sa.Integer(), nullable=False),
        sa.Column("stock_final", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="VALIDO", nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "estado IN ('VALIDO', 'ERROR', 'SIN_CAMBIOS')",
            name=op.f("ck_ajuste_inventario_lote_detalle_ajuste_inventario_lote_detalle_estado_valido"),
        ),
        sa.ForeignKeyConstraint(["lote_id"], ["ajuste_inventario_lote.id"], name=op.f("fk_ajuste_inventario_lote_detalle_lote_id_ajuste_inventario_lote"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variante_id"], ["variante.id"], name=op.f("fk_ajuste_inventario_lote_detalle_variante_id_variante"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ajuste_inventario_lote_detalle")),
    )
    op.create_index(op.f("ix_ajuste_inventario_lote_detalle_created_at"), "ajuste_inventario_lote_detalle", ["created_at"], unique=False)
    op.create_index(op.f("ix_ajuste_inventario_lote_detalle_estado"), "ajuste_inventario_lote_detalle", ["estado"], unique=False)
    op.create_index(op.f("ix_ajuste_inventario_lote_detalle_lote_id"), "ajuste_inventario_lote_detalle", ["lote_id"], unique=False)
    op.create_index(op.f("ix_ajuste_inventario_lote_detalle_sku_snapshot"), "ajuste_inventario_lote_detalle", ["sku_snapshot"], unique=False)
    op.create_index(op.f("ix_ajuste_inventario_lote_detalle_variante_id"), "ajuste_inventario_lote_detalle", ["variante_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ajuste_inventario_lote_detalle_variante_id"), table_name="ajuste_inventario_lote_detalle")
    op.drop_index(op.f("ix_ajuste_inventario_lote_detalle_sku_snapshot"), table_name="ajuste_inventario_lote_detalle")
    op.drop_index(op.f("ix_ajuste_inventario_lote_detalle_lote_id"), table_name="ajuste_inventario_lote_detalle")
    op.drop_index(op.f("ix_ajuste_inventario_lote_detalle_estado"), table_name="ajuste_inventario_lote_detalle")
    op.drop_index(op.f("ix_ajuste_inventario_lote_detalle_created_at"), table_name="ajuste_inventario_lote_detalle")
    op.drop_table("ajuste_inventario_lote_detalle")

    op.drop_index(op.f("ix_ajuste_inventario_lote_usuario_id"), table_name="ajuste_inventario_lote")
    op.drop_index(op.f("ix_ajuste_inventario_lote_referencia"), table_name="ajuste_inventario_lote")
    op.drop_index(op.f("ix_ajuste_inventario_lote_created_at"), table_name="ajuste_inventario_lote")
    op.drop_table("ajuste_inventario_lote")
