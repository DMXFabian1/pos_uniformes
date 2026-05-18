"""add bodega module

Revision ID: a1b3c5d7e9f0
Revises: f7c9e12ab430
Create Date: 2026-05-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a1b3c5d7e9f0"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bodega_ubicacion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=30), nullable=False),
        sa.Column("rack", sa.String(length=20), nullable=False),
        sa.Column("nivel", sa.Integer(), nullable=False),
        sa.Column("descripcion", sa.String(length=120), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
        sa.UniqueConstraint("rack", "nivel", name="bodega_ubicacion_rack_nivel_unico"),
    )
    op.create_index("ix_bodega_ubicacion_codigo", "bodega_ubicacion", ["codigo"])
    op.create_index("ix_bodega_ubicacion_rack", "bodega_ubicacion", ["rack"])

    op.create_table(
        "bodega_caja",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=30), nullable=False),
        sa.Column("ubicacion_id", sa.Integer(), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="ACTIVA"),
        sa.Column("qr_data", sa.Text(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
        sa.ForeignKeyConstraint(["ubicacion_id"], ["bodega_ubicacion.id"], ondelete="SET NULL"),
        sa.CheckConstraint("estado IN ('ACTIVA', 'VACIA', 'CERRADA')", name="bodega_caja_estado_valido"),
    )
    op.create_index("ix_bodega_caja_codigo", "bodega_caja", ["codigo"])
    op.create_index("ix_bodega_caja_ubicacion_id", "bodega_caja", ["ubicacion_id"])

    op.create_table(
        "bodega_contenido",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("caja_id", sa.Integer(), nullable=False),
        sa.Column("variante_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["caja_id"], ["bodega_caja.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variante_id"], ["variante.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("caja_id", "variante_id", name="bodega_contenido_caja_variante_unico"),
        sa.CheckConstraint("cantidad > 0", name="bodega_contenido_cantidad_positiva"),
    )
    op.create_index("ix_bodega_contenido_caja_id", "bodega_contenido", ["caja_id"])
    op.create_index("ix_bodega_contenido_variante_id", "bodega_contenido", ["variante_id"])

    op.create_table(
        "bodega_movimiento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("caja_id", sa.Integer(), nullable=False),
        sa.Column("variante_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=True),
        sa.Column("caja_destino_id", sa.Integer(), nullable=True),
        sa.Column("ubicacion_anterior_id", sa.Integer(), nullable=True),
        sa.Column("ubicacion_nueva_id", sa.Integer(), nullable=True),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column("creado_por", sa.String(length=60), nullable=False, server_default="SYSTEM"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["caja_id"], ["bodega_caja.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variante_id"], ["variante.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["caja_destino_id"], ["bodega_caja.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ubicacion_anterior_id"], ["bodega_ubicacion.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ubicacion_nueva_id"], ["bodega_ubicacion.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "tipo IN ('INGRESO', 'RETIRO', 'TRANSFERENCIA', 'MOVER_CAJA', 'CREAR_CAJA', 'AJUSTE')",
            name="bodega_movimiento_tipo_valido",
        ),
    )
    op.create_index("ix_bodega_movimiento_caja_id", "bodega_movimiento", ["caja_id"])
    op.create_index("ix_bodega_movimiento_variante_id", "bodega_movimiento", ["variante_id"])
    op.create_index("ix_bodega_movimiento_tipo", "bodega_movimiento", ["tipo"])
    op.create_index("ix_bodega_movimiento_created_at", "bodega_movimiento", ["created_at"])


def downgrade() -> None:
    op.drop_table("bodega_movimiento")
    op.drop_table("bodega_contenido")
    op.drop_table("bodega_caja")
    op.drop_table("bodega_ubicacion")
