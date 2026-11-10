"""E1-A: identidad del cliente (solo agrega).

- `cliente.telefono_normalizado` (10 dígitos, índice NO único) y
  `cliente.origen_alta`. `telefono` no se modifica.
- `cliente.nivel_lealtad` acepta vacío («Sin nivel»). Ningún dato cambia: los
  niveles históricos se conservan tal cual (D5).
- Tabla `cliente_evento`: bitácora de la ficha; solo se le agregan filas.
- Relleno de `telefono_normalizado` con la regla K6 (misma que
  `services/clientes/telefono.py`; una prueba verifica que coinciden).

El `downgrade` se detiene antes de perder información (K7):
- si hay eventos o altas con origen, salvo `POS_E1A_DOWNGRADE_ACEPTO_PERDIDA=1`;
- si hay clientes sin nivel, siempre: volver a exigir el nivel obligaría a
  darles BASICO, y eso es otorgar un beneficio (K1).

Revision ID: e767eaf1db92
Revises: e2f3a4b5c6d7
"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e767eaf1db92"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None

ENV_ACEPTO_PERDIDA = "POS_E1A_DOWNGRADE_ACEPTO_PERDIDA"

# Copia congelada de `SQL_NORMALIZAR_TELEFONO` (services/clientes/telefono.py).
_SQL_NORMALIZAR_TELEFONO = r"""
(SELECT CASE WHEN c ~ '^(\d)\1+$' THEN NULL ELSE c END
   FROM (SELECT CASE
                  WHEN length(d) = 10 THEN d
                  WHEN length(d) = 12 AND d LIKE '52%' THEN right(d, 10)
                  WHEN length(d) = 13 AND d LIKE '521%' THEN right(d, 10)
                  ELSE NULL
                END AS c
           FROM (SELECT regexp_replace(coalesce(telefono, ''), '\D', '', 'g') AS d) AS solo_digitos
        ) AS candidato)
""".strip()


def upgrade() -> None:
    op.add_column("cliente", sa.Column("telefono_normalizado", sa.String(length=10), nullable=True))
    op.create_index("ix_cliente_telefono_normalizado", "cliente", ["telefono_normalizado"], unique=False)
    op.add_column("cliente", sa.Column("origen_alta", sa.String(length=30), nullable=True))
    op.alter_column(
        "cliente",
        "nivel_lealtad",
        existing_type=postgresql.ENUM(name="nivel_lealtad", create_type=False),
        nullable=True,
    )

    op.create_table(
        "cliente_evento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("cliente.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("detalle", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("employee_code", sa.String(length=40), nullable=True),
        sa.Column("origen", sa.String(length=60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_cliente_evento_cliente_id", "cliente_evento", ["cliente_id"], unique=False)
    op.create_index("ix_cliente_evento_created_at", "cliente_evento", ["created_at"], unique=False)

    # Única escritura: llena la columna nueva. `telefono` no se toca.
    op.execute(
        f"UPDATE cliente SET telefono_normalizado = {_SQL_NORMALIZAR_TELEFONO} WHERE telefono IS NOT NULL"
    )


def downgrade() -> None:
    bind = op.get_bind()
    eventos = bind.execute(sa.text("SELECT count(*) FROM cliente_evento")).scalar_one()
    con_origen = bind.execute(sa.text("SELECT count(*) FROM cliente WHERE origen_alta IS NOT NULL")).scalar_one()
    sin_nivel = bind.execute(sa.text("SELECT count(*) FROM cliente WHERE nivel_lealtad IS NULL")).scalar_one()

    if sin_nivel:
        raise RuntimeError(
            f"Downgrade E1-A detenido: {sin_nivel} cliente(s) sin nivel. Volver a exigir el nivel "
            "obligaría a asignarles BASICO (un beneficio). Asigna o revisa esos niveles a mano antes."
        )
    if (eventos or con_origen) and os.environ.get(ENV_ACEPTO_PERDIDA) != "1":
        raise RuntimeError(
            f"Downgrade E1-A detenido: se perderían {eventos} evento(s) de cliente y el origen de "
            f"{con_origen} alta(s). Exporta esas filas y, si aceptas la pérdida, repite con "
            f"{ENV_ACEPTO_PERDIDA}=1."
        )

    op.drop_index("ix_cliente_evento_created_at", table_name="cliente_evento")
    op.drop_index("ix_cliente_evento_cliente_id", table_name="cliente_evento")
    op.drop_table("cliente_evento")
    op.drop_column("cliente", "origen_alta")
    op.drop_index("ix_cliente_telefono_normalizado", table_name="cliente")
    op.drop_column("cliente", "telefono_normalizado")
    op.alter_column(
        "cliente",
        "nivel_lealtad",
        existing_type=postgresql.ENUM(name="nivel_lealtad", create_type=False),
        nullable=False,
    )
