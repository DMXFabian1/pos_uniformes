"""Descansos: solicitudes ligadas al calendario, intercambios y bitácora.

Se conserva el modelo antiguo de descansos (autoservicio del Calendario) y la
solicitud de la Libreta, con las mismas reglas (Daniel, 2026-10-12). Lo que
necesita la base para hacerlo con integridad:

- `solicitud_descanso` aprende dos estados — `vencido` (nadie contestó y el
  día pasó) y `revocado` (se aprobó y luego se deshizo) — y lo necesario para
  intercambios (la compañera, su día, cuándo aceptó), el día que pasa a
  trabajo, el origen, los recordatorios y si ella ya vio la respuesta. Lo que
  aprueba el autoservicio también queda aquí (aprobado por «REGLAS»).
- `empleada_evento.solicitud_id`: el evento sabe qué solicitud lo produjo.
- `auditoria_ausencias`: quién hizo qué, cuándo, desde dónde y qué había antes.

No toca datos existentes (probado en una copia de producción el 2026-10-12:
calendario y nómina idénticos).

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d9e0f1a2b3c4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

_ESTADOS_VIEJOS = "estado IN ('pedido', 'aprobado', 'rechazado', 'cancelado')"
_ESTADOS_NUEVOS = (
    "estado IN ('pedido', 'aprobado', 'rechazado', 'cancelado', 'vencido', 'revocado')"
)


def upgrade() -> None:
    with op.batch_alter_table("solicitud_descanso") as t:
        t.drop_constraint("solicitud_descanso_estado_valido", type_="check")
        t.create_check_constraint("solicitud_descanso_estado_valido", _ESTADOS_NUEVOS)
        t.add_column(sa.Column("tipo", sa.String(20), nullable=False, server_default="cambio"))
        t.add_column(sa.Column("origen", sa.String(20), nullable=True))
        t.add_column(sa.Column("fecha_fijo", sa.Date(), nullable=True))
        t.add_column(sa.Column("companera_code", sa.String(40), nullable=True))
        t.add_column(sa.Column("companera_name", sa.String(120), nullable=True))
        t.add_column(sa.Column("fecha_companera", sa.Date(), nullable=True))
        t.add_column(sa.Column("companera_acepto_at", sa.DateTime(timezone=True), nullable=True))
        t.add_column(sa.Column("avisada_at", sa.DateTime(timezone=True), nullable=True))
        t.add_column(sa.Column("companera_avisada_at", sa.DateTime(timezone=True), nullable=True))
        t.add_column(sa.Column("ultimo_recordatorio_at", sa.DateTime(timezone=True), nullable=True))
        t.add_column(sa.Column("recordatorios", sa.Integer(), nullable=False, server_default="0"))
        t.create_check_constraint(
            "solicitud_descanso_tipo_valido", "tipo IN ('cambio', 'intercambio')"
        )
    op.create_index(
        "ix_solicitud_descanso_companera", "solicitud_descanso", ["companera_code"]
    )

    with op.batch_alter_table("empleada_evento") as t:
        t.add_column(sa.Column("solicitud_id", sa.Integer(), nullable=True))
        t.create_foreign_key(
            "fk_empleada_evento_solicitud", "solicitud_descanso", ["solicitud_id"], ["id"]
        )
    op.create_index("ix_empleada_evento_solicitud_id", "empleada_evento", ["solicitud_id"])

    op.create_table(
        "auditoria_ausencias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.Column("origen", sa.String(20), nullable=False),
        sa.Column("operacion", sa.String(40), nullable=False),
        sa.Column("entidad", sa.String(40), nullable=False),
        sa.Column("entidad_id", sa.Integer(), nullable=True),
        sa.Column("solicitud_id", sa.Integer(), nullable=True, index=True),
        sa.Column("employee_code", sa.String(40), nullable=True, index=True),
        sa.Column("antes", _JSON, nullable=True),
        sa.Column("despues", _JSON, nullable=True),
        sa.Column("motivo", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    # Bajar con solicitudes en los estados nuevos rompería el CHECK viejo: se
    # avisa en vez de reescribir su significado a ciegas.
    bind = op.get_bind()
    nuevos = bind.execute(sa.text(
        "SELECT count(*) FROM solicitud_descanso WHERE estado IN ('vencido', 'revocado') "
        "OR tipo = 'intercambio'"
    )).scalar()
    if nuevos:
        raise RuntimeError(
            f"Hay {nuevos} solicitudes vencidas, revocadas o de intercambio; "
            "revísalas antes de bajar esta migración."
        )
    op.drop_table("auditoria_ausencias")
    op.drop_index("ix_empleada_evento_solicitud_id", table_name="empleada_evento")
    with op.batch_alter_table("empleada_evento") as t:
        t.drop_constraint("fk_empleada_evento_solicitud", type_="foreignkey")
        t.drop_column("solicitud_id")
    op.drop_index("ix_solicitud_descanso_companera", table_name="solicitud_descanso")
    with op.batch_alter_table("solicitud_descanso") as t:
        t.drop_constraint("solicitud_descanso_tipo_valido", type_="check")
        for col in (
            "recordatorios", "ultimo_recordatorio_at", "companera_avisada_at", "avisada_at", "companera_acepto_at",
            "fecha_companera", "companera_name", "companera_code", "fecha_fijo", "origen", "tipo",
        ):
            t.drop_column(col)
        t.drop_constraint("solicitud_descanso_estado_valido", type_="check")
        t.create_check_constraint("solicitud_descanso_estado_valido", _ESTADOS_VIEJOS)
