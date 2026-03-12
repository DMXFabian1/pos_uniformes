"""add import traceability

Revision ID: 9c5d8a4b12ef
Revises: f7c9e12ab430
Create Date: 2026-03-11 17:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c5d8a4b12ef"
down_revision = "f7c9e12ab430"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "importacion_catalogo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fuente_nombre", sa.String(length=120), nullable=False),
        sa.Column("fuente_ruta", sa.Text(), nullable=False),
        sa.Column("reporte_ruta", sa.Text(), nullable=True),
        sa.Column("filas_leidas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("familias_creadas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("variantes_creadas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("assets_creados", sa.Integer(), server_default="0", nullable=False),
        sa.Column("movimientos_stock_creados", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicados_fallback", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_sku_legacy", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_importacion_catalogo")),
    )
    op.create_index(op.f("ix_importacion_catalogo_created_at"), "importacion_catalogo", ["created_at"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_finished_at"), "importacion_catalogo", ["finished_at"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_fuente_nombre"), "importacion_catalogo", ["fuente_nombre"], unique=False)

    op.create_table(
        "importacion_catalogo_fila",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("importacion_id", sa.Integer(), nullable=False),
        sa.Column("legacy_sku", sa.String(length=64), nullable=False),
        sa.Column("legacy_nombre", sa.String(length=220), nullable=False),
        sa.Column("legacy_nombre_base", sa.String(length=150), nullable=False),
        sa.Column("legacy_talla", sa.String(length=30), nullable=False),
        sa.Column("legacy_color", sa.String(length=50), nullable=False),
        sa.Column("legacy_precio", sa.Numeric(10, 2), nullable=False),
        sa.Column("legacy_inventario", sa.Integer(), server_default="0", nullable=False),
        sa.Column("legacy_last_modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("producto_id", sa.Integer(), nullable=True),
        sa.Column("variante_id", sa.Integer(), nullable=True),
        sa.Column("producto_fallback", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("clave_familia", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["importacion_id"], ["importacion_catalogo.id"], name=op.f("fk_importacion_catalogo_fila_importacion_id_importacion_catalogo"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["producto_id"], ["producto.id"], name=op.f("fk_importacion_catalogo_fila_producto_id_producto"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["variante_id"], ["variante.id"], name=op.f("fk_importacion_catalogo_fila_variante_id_variante"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_importacion_catalogo_fila")),
        sa.UniqueConstraint("importacion_id", "legacy_sku", name="importacion_catalogo_fila_sku_unico"),
    )
    op.create_index(op.f("ix_importacion_catalogo_fila_importacion_id"), "importacion_catalogo_fila", ["importacion_id"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_fila_legacy_nombre_base"), "importacion_catalogo_fila", ["legacy_nombre_base"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_fila_legacy_sku"), "importacion_catalogo_fila", ["legacy_sku"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_fila_producto_fallback"), "importacion_catalogo_fila", ["producto_fallback"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_fila_producto_id"), "importacion_catalogo_fila", ["producto_id"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_fila_variante_id"), "importacion_catalogo_fila", ["variante_id"], unique=False)

    op.create_table(
        "importacion_catalogo_incidencia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("importacion_id", sa.Integer(), nullable=False),
        sa.Column("fila_id", sa.Integer(), nullable=True),
        sa.Column("producto_id", sa.Integer(), nullable=True),
        sa.Column("variante_id", sa.Integer(), nullable=True),
        sa.Column("severidad", sa.String(length=20), server_default="WARNING", nullable=False),
        sa.Column("tipo", sa.String(length=80), nullable=False),
        sa.Column("legacy_sku", sa.String(length=64), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("detalle_json", sa.Text(), nullable=True),
        sa.Column("resuelta", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "severidad IN ('INFO', 'WARNING', 'ERROR')",
            name=op.f("ck_importacion_catalogo_incidencia_importacion_catalogo_incidencia_severidad_valida"),
        ),
        sa.ForeignKeyConstraint(["fila_id"], ["importacion_catalogo_fila.id"], name=op.f("fk_importacion_catalogo_incidencia_fila_id_importacion_catalogo_fila"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["importacion_id"], ["importacion_catalogo.id"], name=op.f("fk_importacion_catalogo_incidencia_importacion_id_importacion_catalogo"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["producto_id"], ["producto.id"], name=op.f("fk_importacion_catalogo_incidencia_producto_id_producto"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["variante_id"], ["variante.id"], name=op.f("fk_importacion_catalogo_incidencia_variante_id_variante"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_importacion_catalogo_incidencia")),
    )
    op.create_index(op.f("ix_importacion_catalogo_incidencia_created_at"), "importacion_catalogo_incidencia", ["created_at"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_incidencia_fila_id"), "importacion_catalogo_incidencia", ["fila_id"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_incidencia_importacion_id"), "importacion_catalogo_incidencia", ["importacion_id"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_incidencia_legacy_sku"), "importacion_catalogo_incidencia", ["legacy_sku"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_incidencia_producto_id"), "importacion_catalogo_incidencia", ["producto_id"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_incidencia_resuelta"), "importacion_catalogo_incidencia", ["resuelta"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_incidencia_severidad"), "importacion_catalogo_incidencia", ["severidad"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_incidencia_tipo"), "importacion_catalogo_incidencia", ["tipo"], unique=False)
    op.create_index(op.f("ix_importacion_catalogo_incidencia_variante_id"), "importacion_catalogo_incidencia", ["variante_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_importacion_catalogo_incidencia_variante_id"), table_name="importacion_catalogo_incidencia")
    op.drop_index(op.f("ix_importacion_catalogo_incidencia_tipo"), table_name="importacion_catalogo_incidencia")
    op.drop_index(op.f("ix_importacion_catalogo_incidencia_severidad"), table_name="importacion_catalogo_incidencia")
    op.drop_index(op.f("ix_importacion_catalogo_incidencia_resuelta"), table_name="importacion_catalogo_incidencia")
    op.drop_index(op.f("ix_importacion_catalogo_incidencia_producto_id"), table_name="importacion_catalogo_incidencia")
    op.drop_index(op.f("ix_importacion_catalogo_incidencia_legacy_sku"), table_name="importacion_catalogo_incidencia")
    op.drop_index(op.f("ix_importacion_catalogo_incidencia_importacion_id"), table_name="importacion_catalogo_incidencia")
    op.drop_index(op.f("ix_importacion_catalogo_incidencia_fila_id"), table_name="importacion_catalogo_incidencia")
    op.drop_index(op.f("ix_importacion_catalogo_incidencia_created_at"), table_name="importacion_catalogo_incidencia")
    op.drop_table("importacion_catalogo_incidencia")

    op.drop_index(op.f("ix_importacion_catalogo_fila_variante_id"), table_name="importacion_catalogo_fila")
    op.drop_index(op.f("ix_importacion_catalogo_fila_producto_id"), table_name="importacion_catalogo_fila")
    op.drop_index(op.f("ix_importacion_catalogo_fila_producto_fallback"), table_name="importacion_catalogo_fila")
    op.drop_index(op.f("ix_importacion_catalogo_fila_legacy_sku"), table_name="importacion_catalogo_fila")
    op.drop_index(op.f("ix_importacion_catalogo_fila_legacy_nombre_base"), table_name="importacion_catalogo_fila")
    op.drop_index(op.f("ix_importacion_catalogo_fila_importacion_id"), table_name="importacion_catalogo_fila")
    op.drop_table("importacion_catalogo_fila")

    op.drop_index(op.f("ix_importacion_catalogo_fuente_nombre"), table_name="importacion_catalogo")
    op.drop_index(op.f("ix_importacion_catalogo_finished_at"), table_name="importacion_catalogo")
    op.drop_index(op.f("ix_importacion_catalogo_created_at"), table_name="importacion_catalogo")
    op.drop_table("importacion_catalogo")
