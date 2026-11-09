"""Monedero de clientes: saldo de fidelización en MXN con cashback.

El saldo NO es un campo: se deriva del libro de movimientos. Cada crédito
(cashback, devolución de canje, ajuste a favor) vence a los 12 meses de
calendario de acreditado, y `monedero_aplicacion` dice qué crédito consumió
cada débito — así cada peso sabe cuándo vence.

La Libreta gana tres columnas para ligar la venta del kiosko al cliente:
`cliente_id`, `operacion_uuid` (identidad persistente de la venta, la misma
en todos los reintentos de la cola offline) y `monto_monedero` (la parte de
la venta que se pagó con saldo; no es efectivo ni tarjeta).

Los movimientos no se editan ni se borran: un trigger lo impide en la base.
La única excepción es soltar la liga a la Libreta (`libreta_venta_id` → NULL)
al anular una venta, porque el movimiento conserva `operacion_uuid`.

No crea monederos ni movimientos para datos existentes: nada retroactivo.

Revision ID: e2f3a4b5c6d7
Revises: d0e1f2a3b4c5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


_TIPOS = (
    "'cashback', 'canje', 'devolucion_canje', 'reversa_cashback', "
    "'expiracion', 'ajuste_abono', 'ajuste_cargo'"
)

_INMUTABLE_FN = """
CREATE OR REPLACE FUNCTION monedero_inmutable() RETURNS trigger AS $$
DECLARE
    permitido monedero_movimiento;
BEGIN
    IF TG_TABLE_NAME = 'monedero_movimiento' AND TG_OP = 'UPDATE' THEN
        -- Única edición válida: soltar la liga a la Libreta al anular la venta.
        permitido := OLD;
        permitido.libreta_venta_id := NULL;
        IF OLD.libreta_venta_id IS NOT NULL AND NEW IS NOT DISTINCT FROM permitido THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'Los movimientos del monedero no se modifican ni se borran (%).', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.create_table(
        "monedero",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cliente_id",
            sa.Integer(),
            sa.ForeignKey("cliente.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="activo"),
        sa.Column("motivo_estado", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("estado IN ('activo', 'bloqueado', 'cerrado')", name="monedero_estado_valido"),
    )

    op.create_table(
        "monedero_movimiento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "monedero_id",
            sa.Integer(),
            sa.ForeignKey("monedero.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("tipo", sa.String(length=30), nullable=False, index=True),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "libreta_venta_id",
            sa.Integer(),
            sa.ForeignKey("libreta_venta.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column("operacion_uuid", sa.String(length=36), nullable=True, index=True),
        sa.Column(
            "movimiento_relacionado_id",
            sa.Integer(),
            sa.ForeignKey("monedero_movimiento.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False, unique=True),
        sa.Column("tasa_snapshot", sa.Numeric(5, 2), nullable=True),
        sa.Column("base_calculo", sa.Numeric(12, 2), nullable=True),
        sa.Column("expira_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("motivo", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuario.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("employee_code", sa.String(length=40), nullable=True),
        sa.Column("origen", sa.String(length=60), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
        sa.CheckConstraint(f"tipo IN ({_TIPOS})", name="monedero_mov_tipo_valido"),
        sa.CheckConstraint(
            "(tipo IN ('cashback', 'devolucion_canje', 'ajuste_abono') AND monto > 0)"
            " OR (tipo IN ('canje', 'reversa_cashback', 'expiracion', 'ajuste_cargo') AND monto < 0)",
            name="monedero_mov_signo_valido",
        ),
        sa.CheckConstraint(
            "tipo NOT IN ('cashback', 'devolucion_canje', 'ajuste_abono') OR expira_at IS NOT NULL",
            name="monedero_mov_credito_con_vencimiento",
        ),
    )

    op.create_table(
        "monedero_aplicacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "debito_id",
            sa.Integer(),
            sa.ForeignKey("monedero_movimiento.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "credito_id",
            sa.Integer(),
            sa.ForeignKey("monedero_movimiento.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("monto > 0", name="monedero_aplicacion_monto_positivo"),
        sa.UniqueConstraint("debito_id", "credito_id", name="uq_monedero_aplicacion_par"),
    )

    op.create_table(
        "monedero_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tasa_cashback", sa.Numeric(5, 2), nullable=False),
        sa.Column("habilitado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("vigente_desde", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuario.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("nota", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "tasa_cashback >= 0 AND tasa_cashback <= 100",
            name="monedero_config_tasa_valida",
        ),
    )

    # La Libreta: liga estable al cliente, identidad persistente de la venta
    # y la parte pagada con monedero. Todo opcional: las ventas viejas quedan
    # exactamente como estaban (monto_monedero = 0).
    op.add_column(
        "libreta_venta",
        sa.Column(
            "cliente_id",
            sa.Integer(),
            sa.ForeignKey("cliente.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_libreta_venta_cliente_id", "libreta_venta", ["cliente_id"])
    op.add_column("libreta_venta", sa.Column("operacion_uuid", sa.String(length=36), nullable=True))
    op.create_index("uq_libreta_venta_operacion_uuid", "libreta_venta", ["operacion_uuid"], unique=True)
    op.add_column(
        "libreta_venta",
        sa.Column("monto_monedero", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "libreta_monto_monedero_valido",
        "libreta_venta",
        "monto_monedero >= 0 AND monto_monedero <= monto_total",
    )

    op.execute(_INMUTABLE_FN)
    for tabla in ("monedero_movimiento", "monedero_aplicacion"):
        op.execute(
            f"CREATE TRIGGER {tabla}_inmutable BEFORE UPDATE OR DELETE ON {tabla} "
            "FOR EACH ROW EXECUTE FUNCTION monedero_inmutable();"
        )


def downgrade() -> None:
    for tabla in ("monedero_aplicacion", "monedero_movimiento"):
        op.execute(f"DROP TRIGGER IF EXISTS {tabla}_inmutable ON {tabla};")
    op.execute("DROP FUNCTION IF EXISTS monedero_inmutable();")
    op.drop_constraint("libreta_monto_monedero_valido", "libreta_venta", type_="check")
    op.drop_column("libreta_venta", "monto_monedero")
    op.drop_index("uq_libreta_venta_operacion_uuid", table_name="libreta_venta")
    op.drop_column("libreta_venta", "operacion_uuid")
    op.drop_index("ix_libreta_venta_cliente_id", table_name="libreta_venta")
    op.drop_column("libreta_venta", "cliente_id")
    op.drop_table("monedero_config")
    op.drop_table("monedero_aplicacion")
    op.drop_table("monedero_movimiento")
    op.drop_table("monedero")
