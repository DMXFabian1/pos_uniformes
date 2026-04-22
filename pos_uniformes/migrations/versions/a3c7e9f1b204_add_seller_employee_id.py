"""add seller_employee_id to venta, presupuesto and apartado

Revision ID: a3c7e9f1b204
Revises: f0a1b2c3d4e5
Create Date: 2026-04-16

Agrega seller_employee_id (FK nullable a empleada) en las tres tablas
principales de operacion comercial. Permite atribuir ventas, presupuestos
y apartados a la empleada que realizo la atencion, independientemente del
usuario tecnico que opero el POS.

Las columnas nacen nullable para no romper registros historicos ni el
flujo actual del POS. Los registros anteriores a esta migracion quedaran
con seller_employee_id = NULL, lo cual es correcto: no habia atribucion.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a3c7e9f1b204"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "venta",
        sa.Column(
            "seller_employee_id",
            sa.Integer(),
            sa.ForeignKey("empleada.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    op.create_index(
        "ix_venta_seller_employee_id",
        "venta",
        ["seller_employee_id"],
        if_not_exists=True,
    )

    op.add_column(
        "presupuesto",
        sa.Column(
            "seller_employee_id",
            sa.Integer(),
            sa.ForeignKey("empleada.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    op.create_index(
        "ix_presupuesto_seller_employee_id",
        "presupuesto",
        ["seller_employee_id"],
        if_not_exists=True,
    )

    op.add_column(
        "apartado",
        sa.Column(
            "seller_employee_id",
            sa.Integer(),
            sa.ForeignKey("empleada.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    op.create_index(
        "ix_apartado_seller_employee_id",
        "apartado",
        ["seller_employee_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_apartado_seller_employee_id", table_name="apartado")
    op.drop_column("apartado", "seller_employee_id")

    op.drop_index("ix_presupuesto_seller_employee_id", table_name="presupuesto")
    op.drop_column("presupuesto", "seller_employee_id")

    op.drop_index("ix_venta_seller_employee_id", table_name="venta")
    op.drop_column("venta", "seller_employee_id")
