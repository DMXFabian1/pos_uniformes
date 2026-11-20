"""pago_dueno: la cuenta del pago del dueño, calendarizado (2026-11-19).

Daniel (VEND-1) recibe de su papá $10,000 al mes en 4 pagos de $2,500, los
días 7, 14, 21 y 28. El sistema le lleva la cuenta como a las empleadas, pero
SIN tocar el cajón ni `empleada_pago`: es solo un recordatorio en el corte.

Tablas nuevas:

- `pago_dueno_config`: una sola fila (monto por pago, valor del día, días de
  pago del mes, fecha de inicio y si está activo). Sin fila = nada cambia.
- `pago_dueno_registro`: los pagos que ya le hicieron (fecha programada única,
  fecha real, monto y el desglose con que se calculó).
- `pago_dueno_dia_extra`: qué se hace con cada día de más («pagar» o
  «acumular» como día a favor).

Tablas nuevas y vacías: no hay backfill. Solo se aplica en la caja con el sí
de Daniel. El downgrade las quita (se pierde la cuenta del dueño, nada más).

Revision ID: a7d3e9f1c2b4
Revises: d1e2f3a4b5c6
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a7d3e9f1c2b4"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "pago_dueno_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_code", sa.String(length=40), nullable=False, server_default="VEND-1"),
        sa.Column("monto_por_pago", sa.Numeric(12, 2), nullable=False, server_default="2500"),
        sa.Column("valor_dia", sa.Numeric(12, 2), nullable=False, server_default="385"),
        sa.Column("dias_de_pago", _JSON, nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "pago_dueno_registro",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fecha_programada", sa.Date(), nullable=False),
        sa.Column("fecha_pago", sa.Date(), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("desglose", _JSON, nullable=True),
        sa.Column("creado_por", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("fecha_programada", name="uq_pago_dueno_registro_fecha_programada"),
    )
    op.create_table(
        "pago_dueno_dia_extra",
        sa.Column("fecha", sa.Date(), primary_key=True),
        sa.Column("destino", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("destino IN ('pagar', 'acumular')", name="pago_dueno_dia_extra_destino_valido"),
    )


def downgrade() -> None:
    op.drop_table("pago_dueno_dia_extra")
    op.drop_table("pago_dueno_registro")
    op.drop_table("pago_dueno_config")
