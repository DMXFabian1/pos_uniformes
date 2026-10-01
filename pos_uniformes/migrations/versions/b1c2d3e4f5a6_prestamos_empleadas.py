"""Préstamos a empleadas: lo pide ella en la Libreta, Daniel lo aprueba desde
el celular y se descuenta completo en su siguiente pago.

Revision ID: b1c2d3e4f5a6
Revises: 5a6b7c8d9e0f
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "5a6b7c8d9e0f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prestamo_empleada",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_code", sa.String(length=40), nullable=False, index=True),
        sa.Column("employee_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="pedido", index=True),
        sa.Column("resuelto_por", sa.String(length=40), nullable=True),
        sa.Column("resuelto_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pago_id", sa.Integer(), sa.ForeignKey("empleada_pago.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cobrado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("monto > 0", name="prestamo_monto_positivo"),
        sa.CheckConstraint(
            "estado IN ('pedido', 'aprobado', 'rechazado', 'cobrado')",
            name="prestamo_estado_valido",
        ),
    )
    # Lo descontado por préstamos queda guardado en el pago, para que el
    # desglose de un pago viejo se siga entendiendo años después.
    op.add_column(
        "empleada_pago",
        sa.Column("descuento_prestamos", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
    )


def downgrade() -> None:
    op.drop_column("empleada_pago", "descuento_prestamos")
    op.drop_table("prestamo_empleada")
