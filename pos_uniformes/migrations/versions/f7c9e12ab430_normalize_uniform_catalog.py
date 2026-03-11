"""normalize uniform catalog

Revision ID: f7c9e12ab430
Revises: e2b4c6d8f901
Create Date: 2026-03-11 13:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f7c9e12ab430"
down_revision = "e2b4c6d8f901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "escuela",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_escuela")),
    )
    op.create_index(op.f("ix_escuela_nombre"), "escuela", ["nombre"], unique=True)

    op.create_table(
        "tipo_prenda",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tipo_prenda")),
    )
    op.create_index(op.f("ix_tipo_prenda_nombre"), "tipo_prenda", ["nombre"], unique=True)

    op.create_table(
        "tipo_pieza",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tipo_pieza")),
    )
    op.create_index(op.f("ix_tipo_pieza_nombre"), "tipo_pieza", ["nombre"], unique=True)

    op.create_table(
        "nivel_educativo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_nivel_educativo")),
    )
    op.create_index(op.f("ix_nivel_educativo_nombre"), "nivel_educativo", ["nombre"], unique=True)

    op.create_table(
        "atributo_producto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_atributo_producto")),
    )
    op.create_index(op.f("ix_atributo_producto_nombre"), "atributo_producto", ["nombre"], unique=True)

    op.create_table(
        "sku_sequence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=50), nullable=False),
        sa.Column("prefijo", sa.String(length=20), server_default="SKU", nullable=False),
        sa.Column("padding", sa.Integer(), server_default="6", nullable=False),
        sa.Column("ultimo_numero", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sku_sequence")),
    )
    op.create_index(op.f("ix_sku_sequence_codigo"), "sku_sequence", ["codigo"], unique=True)

    op.add_column("producto", sa.Column("nombre_base", sa.String(length=150), nullable=True))
    op.add_column("producto", sa.Column("escuela_id", sa.Integer(), nullable=True))
    op.add_column("producto", sa.Column("tipo_prenda_id", sa.Integer(), nullable=True))
    op.add_column("producto", sa.Column("tipo_pieza_id", sa.Integer(), nullable=True))
    op.add_column("producto", sa.Column("nivel_educativo_id", sa.Integer(), nullable=True))
    op.add_column("producto", sa.Column("atributo_id", sa.Integer(), nullable=True))
    op.add_column("producto", sa.Column("genero", sa.String(length=50), nullable=True))
    op.add_column("producto", sa.Column("escudo", sa.String(length=120), nullable=True))
    op.add_column("producto", sa.Column("ubicacion", sa.String(length=120), nullable=True))
    op.execute("UPDATE producto SET nombre_base = nombre WHERE nombre_base IS NULL")
    op.alter_column("producto", "nombre_base", nullable=False)
    op.create_index(op.f("ix_producto_nombre_base"), "producto", ["nombre_base"], unique=False)
    op.create_index(op.f("ix_producto_escuela_id"), "producto", ["escuela_id"], unique=False)
    op.create_index(op.f("ix_producto_tipo_prenda_id"), "producto", ["tipo_prenda_id"], unique=False)
    op.create_index(op.f("ix_producto_tipo_pieza_id"), "producto", ["tipo_pieza_id"], unique=False)
    op.create_index(op.f("ix_producto_nivel_educativo_id"), "producto", ["nivel_educativo_id"], unique=False)
    op.create_index(op.f("ix_producto_atributo_id"), "producto", ["atributo_id"], unique=False)
    op.create_index(op.f("ix_producto_genero"), "producto", ["genero"], unique=False)
    op.create_foreign_key(
        op.f("fk_producto_escuela_id_escuela"),
        "producto",
        "escuela",
        ["escuela_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_producto_tipo_prenda_id_tipo_prenda"),
        "producto",
        "tipo_prenda",
        ["tipo_prenda_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_producto_tipo_pieza_id_tipo_pieza"),
        "producto",
        "tipo_pieza",
        ["tipo_pieza_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_producto_nivel_educativo_id_nivel_educativo"),
        "producto",
        "nivel_educativo",
        ["nivel_educativo_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_producto_atributo_id_atributo_producto"),
        "producto",
        "atributo_producto",
        ["atributo_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column("variante", sa.Column("nombre_legacy", sa.String(length=220), nullable=True))
    op.add_column(
        "variante",
        sa.Column("origen_legacy", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("variante", sa.Column("legacy_last_modified", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_variante_nombre_legacy"), "variante", ["nombre_legacy"], unique=False)
    op.create_index(op.f("ix_variante_origen_legacy"), "variante", ["origen_legacy"], unique=False)

    op.create_table(
        "producto_asset",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("variante_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("ruta", sa.Text(), nullable=False),
        sa.Column("es_legacy", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('QR', 'LABEL_SPLIT', 'IMAGE')",
            name=op.f("ck_producto_asset_producto_asset_tipo_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["variante_id"],
            ["variante.id"],
            name=op.f("fk_producto_asset_variante_id_variante"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_producto_asset")),
        sa.UniqueConstraint(
            "variante_id",
            "tipo",
            "es_legacy",
            "ruta",
            name="producto_asset_variante_tipo_ruta_unico",
        ),
    )
    op.create_index(op.f("ix_producto_asset_variante_id"), "producto_asset", ["variante_id"], unique=False)
    op.create_index(op.f("ix_producto_asset_tipo"), "producto_asset", ["tipo"], unique=False)
    op.create_index(op.f("ix_producto_asset_es_legacy"), "producto_asset", ["es_legacy"], unique=False)

    op.execute(
        """
        INSERT INTO sku_sequence (codigo, prefijo, padding, ultimo_numero)
        SELECT
            'VARIANTE',
            'SKU',
            6,
            COALESCE(
                MAX(
                    CASE
                        WHEN sku ~ '^SKU[0-9]+$' THEN SUBSTRING(sku FROM 4)::integer
                        ELSE 0
                    END
                ),
                0
            )
        FROM variante
        ON CONFLICT (codigo) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_producto_asset_es_legacy"), table_name="producto_asset")
    op.drop_index(op.f("ix_producto_asset_tipo"), table_name="producto_asset")
    op.drop_index(op.f("ix_producto_asset_variante_id"), table_name="producto_asset")
    op.drop_table("producto_asset")

    op.drop_index(op.f("ix_variante_origen_legacy"), table_name="variante")
    op.drop_index(op.f("ix_variante_nombre_legacy"), table_name="variante")
    op.drop_column("variante", "legacy_last_modified")
    op.drop_column("variante", "origen_legacy")
    op.drop_column("variante", "nombre_legacy")

    op.drop_constraint(op.f("fk_producto_atributo_id_atributo_producto"), "producto", type_="foreignkey")
    op.drop_constraint(op.f("fk_producto_nivel_educativo_id_nivel_educativo"), "producto", type_="foreignkey")
    op.drop_constraint(op.f("fk_producto_tipo_pieza_id_tipo_pieza"), "producto", type_="foreignkey")
    op.drop_constraint(op.f("fk_producto_tipo_prenda_id_tipo_prenda"), "producto", type_="foreignkey")
    op.drop_constraint(op.f("fk_producto_escuela_id_escuela"), "producto", type_="foreignkey")
    op.drop_index(op.f("ix_producto_genero"), table_name="producto")
    op.drop_index(op.f("ix_producto_atributo_id"), table_name="producto")
    op.drop_index(op.f("ix_producto_nivel_educativo_id"), table_name="producto")
    op.drop_index(op.f("ix_producto_tipo_pieza_id"), table_name="producto")
    op.drop_index(op.f("ix_producto_tipo_prenda_id"), table_name="producto")
    op.drop_index(op.f("ix_producto_escuela_id"), table_name="producto")
    op.drop_index(op.f("ix_producto_nombre_base"), table_name="producto")
    op.drop_column("producto", "ubicacion")
    op.drop_column("producto", "escudo")
    op.drop_column("producto", "genero")
    op.drop_column("producto", "atributo_id")
    op.drop_column("producto", "nivel_educativo_id")
    op.drop_column("producto", "tipo_pieza_id")
    op.drop_column("producto", "tipo_prenda_id")
    op.drop_column("producto", "escuela_id")
    op.drop_column("producto", "nombre_base")

    op.drop_index(op.f("ix_sku_sequence_codigo"), table_name="sku_sequence")
    op.drop_table("sku_sequence")

    op.drop_index(op.f("ix_atributo_producto_nombre"), table_name="atributo_producto")
    op.drop_table("atributo_producto")

    op.drop_index(op.f("ix_nivel_educativo_nombre"), table_name="nivel_educativo")
    op.drop_table("nivel_educativo")

    op.drop_index(op.f("ix_tipo_pieza_nombre"), table_name="tipo_pieza")
    op.drop_table("tipo_pieza")

    op.drop_index(op.f("ix_tipo_prenda_nombre"), table_name="tipo_prenda")
    op.drop_table("tipo_prenda")

    op.drop_index(op.f("ix_escuela_nombre"), table_name="escuela")
    op.drop_table("escuela")
