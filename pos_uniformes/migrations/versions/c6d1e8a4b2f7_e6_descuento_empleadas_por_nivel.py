"""E6: descuento de empleadas por nivel según sus ventas (Daniel, 2026-11-10).

- `nivel_descuento_empleada`: comisiones de un mes → % con el que la
  empleada compra el mes siguiente. Provisionales: 0→5, 150→10, 250→15,
  350→20 (se calibran con las ventas reales).
- `configuracion_negocio.tope_compra_empleada_mes`: importe a precio de lista
  por mes con su nivel (3000; 0 = sin tope).
- `libreta_venta.compradora_code`: quién compra en una venta con descuento de
  empleada. Vacío en todas las de antes: esas no cambian.

Solo agrega.

Revision ID: c6d1e8a4b2f7
Revises: b5e7c2d9a1f4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c6d1e8a4b2f7"
down_revision = "b5e7c2d9a1f4"
branch_labels = None
depends_on = None

NIVELES = ((0, 5), (150, 10), (250, 15), (350, 20))


def upgrade() -> None:
    op.create_table(
        "nivel_descuento_empleada",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("comisiones_minimas", sa.Integer(), nullable=False, unique=True),
        sa.Column("porcentaje", sa.Numeric(5, 2), nullable=False),
        sa.CheckConstraint("comisiones_minimas >= 0", name="nivel_desc_emp_comisiones_validas"),
        sa.CheckConstraint("porcentaje >= 0 AND porcentaje <= 30", name="nivel_desc_emp_pct_valido"),
    )
    tabla = sa.table(
        "nivel_descuento_empleada",
        sa.column("comisiones_minimas", sa.Integer()),
        sa.column("porcentaje", sa.Numeric(5, 2)),
    )
    op.bulk_insert(tabla, [{"comisiones_minimas": c, "porcentaje": p} for c, p in NIVELES])
    op.add_column(
        "configuracion_negocio",
        sa.Column("tope_compra_empleada_mes", sa.Numeric(12, 2), nullable=False, server_default=sa.text("3000")),
    )
    op.add_column("libreta_venta", sa.Column("compradora_code", sa.String(40), nullable=True))
    op.create_index("ix_libreta_venta_compradora_code", "libreta_venta", ["compradora_code"])


def downgrade() -> None:
    op.drop_index("ix_libreta_venta_compradora_code", table_name="libreta_venta")
    op.drop_column("libreta_venta", "compradora_code")
    op.drop_column("configuracion_negocio", "tope_compra_empleada_mes")
    op.drop_table("nivel_descuento_empleada")
