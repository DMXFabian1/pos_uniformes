"""E5-A: el Monedero abona según el programa del cliente (Daniel, 2026-11-10).

- `programa.tasa_monedero`: % de cada compra que va al Monedero.
  Club 5, Leal 10, Profesional 13, Mayorista 15. Sin programa no hay abono.
- `programa.permite_descuento`: el programa puede cambiar su % por descuento
  en la compra (solo Mayorista: su precio de mayoreo).
- Programa nuevo `LEAL` («Maximoda Leal»), con ingreso `automatico`: sube
  solo desde Club al llegar al gasto del año. Queda en orden 2.
- `programa_tasa_cambio`: bitácora de cada cambio de % hecho en Programas.
- `libreta_venta.descuento_programa`: el % que se descontó en la venta por
  el programa (Mayorista que eligió descuento en vez de Monedero). Vacío en
  todas las ventas de antes: esas no cambian.

Solo agrega: no cambia membresías, saldos ni ventas. El `downgrade` se
detiene si ya hay miembros de Leal, salvo `POS_E5A_DOWNGRADE_ACEPTO_PERDIDA=1`.

Revision ID: b5e7c2d9a1f4
Revises: 7741ff4c020d
"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "b5e7c2d9a1f4"
down_revision = "7741ff4c020d"
branch_labels = None
depends_on = None

ENV_ACEPTO_PERDIDA = "POS_E5A_DOWNGRADE_ACEPTO_PERDIDA"

TASAS = {"CLUB": 5, "LEAL": 10, "PROFESIONAL": 13, "MAYORISTA": 15}
ORDEN = {"CLUB": 1, "LEAL": 2, "PROFESIONAL": 3, "MAYORISTA": 4}

LEAL = {
    "clave": "LEAL",
    "nombre": "Maximoda Leal",
    "descripcion": "Sube solo desde Maximoda Club cuando el cliente llega al gasto del año.",
    "estado": "activo",
    "ingreso_modo": "automatico",
    "tipo_sugerido_clave": None,
    "orden": 2,
    "tasa_monedero": 10,
    "permite_descuento": False,
}


def upgrade() -> None:
    op.add_column(
        "programa",
        sa.Column("tasa_monedero", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "programa",
        sa.Column("permite_descuento", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_check_constraint(
        "programa_tasa_monedero_valida", "programa", "tasa_monedero >= 0 AND tasa_monedero <= 100"
    )
    op.drop_constraint("programa_ingreso_modo_valido", "programa", type_="check")
    op.create_check_constraint(
        "programa_ingreso_modo_valido",
        "programa",
        "ingreso_modo IN ('directo_empleada', 'aprobacion_dueno', 'automatico')",
    )

    bind = op.get_bind()
    # Primero se recorren los órdenes para dejarle el 2 a Leal.
    for clave, orden in ORDEN.items():
        bind.execute(sa.text("UPDATE programa SET orden = :o WHERE clave = :c"), {"o": orden, "c": clave})
    existe = bind.execute(sa.text("SELECT count(*) FROM programa WHERE clave = 'LEAL'")).scalar_one()
    if not existe:
        bind.execute(
            sa.text(
                "INSERT INTO programa (clave, nombre, descripcion, estado, ingreso_modo, tipo_sugerido_clave, "
                "orden, tasa_monedero, permite_descuento) VALUES (:clave, :nombre, :descripcion, :estado, "
                ":ingreso_modo, :tipo_sugerido_clave, :orden, :tasa_monedero, :permite_descuento)"
            ),
            LEAL,
        )
    for clave, tasa in TASAS.items():
        bind.execute(sa.text("UPDATE programa SET tasa_monedero = :t WHERE clave = :c"), {"t": tasa, "c": clave})
    bind.execute(sa.text("UPDATE programa SET permite_descuento = (clave = 'MAYORISTA')"))

    op.create_table(
        "programa_tasa_cambio",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("programa_id", sa.Integer(), sa.ForeignKey("programa.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("antes", sa.Numeric(5, 2), nullable=False),
        sa.Column("despues", sa.Numeric(5, 2), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_programa_tasa_cambio_programa_id", "programa_tasa_cambio", ["programa_id"])
    op.add_column("libreta_venta", sa.Column("descuento_programa", sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    miembros = bind.execute(
        sa.text("SELECT count(*) FROM membresia m JOIN programa p ON p.id = m.programa_id WHERE p.clave = 'LEAL'")
    ).scalar_one()
    if miembros and os.environ.get(ENV_ACEPTO_PERDIDA) != "1":
        raise RuntimeError(
            f"Downgrade E5-A detenido: hay {miembros} membresía(s) de Maximoda Leal. "
            f"Pásalas a otro programa o, si aceptas perderlas, repite con {ENV_ACEPTO_PERDIDA}=1."
        )
    op.drop_column("libreta_venta", "descuento_programa")
    op.drop_index("ix_programa_tasa_cambio_programa_id", table_name="programa_tasa_cambio")
    op.drop_table("programa_tasa_cambio")
    if miembros:
        bind.execute(sa.text(
            "DELETE FROM membresia_evento WHERE membresia_id IN (SELECT m.id FROM membresia m "
            "JOIN programa p ON p.id = m.programa_id WHERE p.clave = 'LEAL')"
        ))
        bind.execute(sa.text(
            "DELETE FROM membresia WHERE programa_id IN (SELECT id FROM programa WHERE clave = 'LEAL')"
        ))
    bind.execute(sa.text("DELETE FROM programa WHERE clave = 'LEAL'"))
    for clave, orden in (("CLUB", 1), ("PROFESIONAL", 2), ("MAYORISTA", 3)):
        bind.execute(sa.text("UPDATE programa SET orden = :o WHERE clave = :c"), {"o": orden, "c": clave})
    op.drop_constraint("programa_ingreso_modo_valido", "programa", type_="check")
    op.create_check_constraint(
        "programa_ingreso_modo_valido", "programa", "ingreso_modo IN ('directo_empleada', 'aprobacion_dueno')"
    )
    op.drop_constraint("programa_tasa_monedero_valida", "programa", type_="check")
    op.drop_column("programa", "permite_descuento")
    op.drop_column("programa", "tasa_monedero")
