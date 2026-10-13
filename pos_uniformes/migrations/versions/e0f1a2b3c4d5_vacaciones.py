"""Vacaciones: expediente, periodos por año de servicio, solicitudes y movimientos.

Módulo aparte de los descansos (Daniel, 2026-10-12): su propio ciclo de vida,
saldo y bitácora; no gasta los dos cambios de descanso del mes.

- `expediente_vacacional`: fecha de ingreso CAPTURADA por Daniel. No se infiere
  de nada: sin expediente no hay periodos ni saldo.
- `periodo_vacaciones`: un renglón por año de servicio cumplido (LFT art. 76),
  con la fecha límite para concederlas (art. 81: seis meses).
- `solicitud_vacaciones`: pedido → aprobado | rechazado | cancelado | vencido;
  aprobado → revocado. Guarda la prima estimada (art. 80).
- `prima_vacacional`: la prima de cada solicitud (art. 80), pendiente hasta
  que Daniel la marca pagada; una por solicitud, nunca dos.
- `movimiento_vacaciones`: el saldo se reconstruye SUMANDO movimientos
  (generación, reserva, liberación, consumo, ajuste). Nunca se edita un saldo.
- `empleada_evento.vacacion_id`: los días de vacaciones en el calendario saben
  de qué solicitud salieron.

Solo crea tablas y una columna; no toca datos existentes.

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e0f1a2b3c4d5"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expediente_vacacional",
        sa.Column("employee_code", sa.String(40), primary_key=True),
        sa.Column("fecha_ingreso", sa.Date(), nullable=False),
        # Antigüedad reconocida, si es anterior al ingreso (p. ej. reingreso
        # o acuerdo). Sin dato, cuenta desde el ingreso.
        sa.Column("antiguedad_desde", sa.Date(), nullable=True),
        # Contrato o condición más favorable que el mínimo de ley: si hay,
        # el cálculo automático NO se usa sin revisión.
        sa.Column("condiciones_especiales", sa.String(300), nullable=True),
        # Si ella puede pedir sus vacaciones desde su Libreta. Arranca en NO:
        # Daniel las gestiona y lo va abriendo una por una (2026-10-12).
        sa.Column("autoservicio", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("capturado_por", sa.String(40), nullable=False),
        sa.Column("nota", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "periodo_vacaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_code", sa.String(40), nullable=False, index=True),
        sa.Column("anio_servicio", sa.Integer(), nullable=False),
        sa.Column("aniversario", sa.Date(), nullable=False),
        sa.Column("fecha_limite", sa.Date(), nullable=False),
        sa.Column("dias_correspondientes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("employee_code", "anio_servicio", name="uq_periodo_vacaciones_anio"),
    )
    op.create_table(
        "solicitud_vacaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_code", sa.String(40), nullable=False, index=True),
        sa.Column("employee_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("periodo_id", sa.Integer(), sa.ForeignKey("periodo_vacaciones.id"), nullable=False),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=False),
        sa.Column("dias", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="pedido", index=True),
        sa.Column("motivo", sa.String(200), nullable=True),
        sa.Column("origen", sa.String(20), nullable=True),
        sa.Column("resuelto_por", sa.String(40), nullable=True),
        sa.Column("resuelto_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("respuesta", sa.String(200), nullable=True),
        sa.Column("prima_estimada", sa.Numeric(12, 2), nullable=True),
        sa.Column("avisada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "estado IN ('pedido', 'aprobado', 'rechazado', 'cancelado', 'vencido', 'revocado')",
            name="solicitud_vacaciones_estado_valido",
        ),
        sa.CheckConstraint("hasta >= desde AND dias > 0", name="solicitud_vacaciones_rango"),
    )
    op.create_table(
        "movimiento_vacaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_code", sa.String(40), nullable=False, index=True),
        sa.Column("periodo_id", sa.Integer(), sa.ForeignKey("periodo_vacaciones.id"), nullable=False, index=True),
        sa.Column("solicitud_id", sa.Integer(), sa.ForeignKey("solicitud_vacaciones.id"), nullable=True),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("dias", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.Column("motivo", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('generacion', 'reserva', 'liberacion', 'consumo', 'ajuste')",
            name="movimiento_vacaciones_tipo_valido",
        ),
        sa.CheckConstraint("tipo = 'ajuste' OR dias > 0", name="movimiento_vacaciones_dias_positivos"),
    )
    op.create_table(
        "prima_vacacional",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Una prima por solicitud: no se puede registrar (ni pagar) dos veces.
        sa.Column("solicitud_id", sa.Integer(), sa.ForeignKey("solicitud_vacaciones.id"),
                  nullable=False, unique=True),
        sa.Column("employee_code", sa.String(40), nullable=False, index=True),
        sa.Column("dias", sa.Integer(), nullable=False),
        sa.Column("salario_diario", sa.Numeric(12, 2), nullable=False),
        sa.Column("porcentaje", sa.Numeric(5, 2), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="pendiente", index=True),
        sa.Column("pagada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pagada_por", sa.String(40), nullable=True),
        sa.Column("nota", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'pagada', 'cancelada')", name="prima_vacacional_estado_valido"
        ),
    )
    with op.batch_alter_table("empleada_evento") as t:
        t.add_column(sa.Column("vacacion_id", sa.Integer(), nullable=True))
        t.create_foreign_key(
            "fk_empleada_evento_vacacion", "solicitud_vacaciones", ["vacacion_id"], ["id"]
        )
    op.create_index("ix_empleada_evento_vacacion_id", "empleada_evento", ["vacacion_id"])


def downgrade() -> None:
    bind = op.get_bind()
    hay = bind.execute(sa.text("SELECT count(*) FROM movimiento_vacaciones")).scalar()
    if hay:
        raise RuntimeError(
            f"Hay {hay} movimientos de vacaciones: bajar esta migración borraría saldos. "
            "Respáldalos antes."
        )
    op.drop_index("ix_empleada_evento_vacacion_id", table_name="empleada_evento")
    with op.batch_alter_table("empleada_evento") as t:
        t.drop_constraint("fk_empleada_evento_vacacion", type_="foreignkey")
        t.drop_column("vacacion_id")
    op.drop_table("prima_vacacional")
    op.drop_table("movimiento_vacaciones")
    op.drop_table("solicitud_vacaciones")
    op.drop_table("periodo_vacaciones")
    op.drop_table("expediente_vacacional")
