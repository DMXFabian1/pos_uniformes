"""add catalog change audit"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


revision = "1e4d7b6c9f21"
down_revision = "8a7f2c1e4d90"
branch_labels = None
depends_on = None


tipo_entidad_catalogo = postgresql.ENUM(
    "CATEGORIA",
    "MARCA",
    "PRODUCTO",
    "PRESENTACION",
    name="tipo_entidad_catalogo",
    create_type=False,
)
tipo_cambio_catalogo = postgresql.ENUM(
    "CREACION",
    "ACTUALIZACION",
    "ESTADO",
    "ELIMINACION",
    name="tipo_cambio_catalogo",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    tipo_entidad_catalogo.create(bind, checkfirst=True)
    tipo_cambio_catalogo.create(bind, checkfirst=True)

    op.create_table(
        "cambio_catalogo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("entidad_tipo", tipo_entidad_catalogo, nullable=False),
        sa.Column("entidad_id", sa.Integer(), nullable=False),
        sa.Column("accion", tipo_cambio_catalogo, nullable=False),
        sa.Column("campo", sa.String(length=80), nullable=False),
        sa.Column("valor_anterior", sa.Text(), nullable=True),
        sa.Column("valor_nuevo", sa.Text(), nullable=True),
        sa.Column("descripcion_entidad", sa.String(length=200), nullable=False),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cambio_catalogo_usuario_id"), "cambio_catalogo", ["usuario_id"], unique=False)
    op.create_index(op.f("ix_cambio_catalogo_entidad_tipo"), "cambio_catalogo", ["entidad_tipo"], unique=False)
    op.create_index(op.f("ix_cambio_catalogo_entidad_id"), "cambio_catalogo", ["entidad_id"], unique=False)
    op.create_index(op.f("ix_cambio_catalogo_accion"), "cambio_catalogo", ["accion"], unique=False)
    op.create_index(op.f("ix_cambio_catalogo_created_at"), "cambio_catalogo", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cambio_catalogo_created_at"), table_name="cambio_catalogo")
    op.drop_index(op.f("ix_cambio_catalogo_accion"), table_name="cambio_catalogo")
    op.drop_index(op.f("ix_cambio_catalogo_entidad_id"), table_name="cambio_catalogo")
    op.drop_index(op.f("ix_cambio_catalogo_entidad_tipo"), table_name="cambio_catalogo")
    op.drop_index(op.f("ix_cambio_catalogo_usuario_id"), table_name="cambio_catalogo")
    op.drop_table("cambio_catalogo")

    bind = op.get_bind()
    tipo_cambio_catalogo.drop(bind, checkfirst=True)
    tipo_entidad_catalogo.drop(bind, checkfirst=True)
