"""Compra a cuenta ligada por columnas, no por el texto del motivo (2026-11-12).

Hasta hoy la compra a cuenta, su venta y su retiro se encontraban leyendo el
motivo («Compra a cuenta · pago del … · ticket 9e9ad282», «Compra a cuenta de
X · #12», «(parte del #7)»). Si la liga por texto fallaba (folio nulo, venta
fuera de la ventana) el retiro salía del corte pero la venta no —un faltante
falso—, y un retiro manual «Compra a cuenta de bolsas» desaparecía del corte.

Agrega:

- `prestamo_empleada.tipo`: 'prestamo' | 'compra_cuenta'.
- `prestamo_empleada.libreta_venta_id`: la venta de la Libreta de la compra.
- `prestamo_empleada.origen_id`: la parte cobrada de un pago parcial apunta
  al préstamo del que salió.
- `caja_retiro.prestamo_id`: el préstamo (o compra) que sacó ese dinero.

El backfill lee los textos de hoy UNA vez; a partir de aquí nadie los parsea.
Lo que no se puede ligar sin dudas se queda en NULL. Funciona en PostgreSQL y
SQLite (batch para las llaves foráneas). El downgrade quita las columnas.

Revision ID: c9a4e2b7d1f3
Revises: f1c2d3e4a5b6
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "c9a4e2b7d1f3"
down_revision = "f1c2d3e4a5b6"
branch_labels = None
depends_on = None

PREFIJO = "Compra a cuenta"
_RE_TICKET = re.compile(r"ticket\s+([0-9a-fA-F]{8})")
_RE_PARTE = re.compile(r"parte del #(\d+)\)?$")
_RE_RETIRO_COMPRA = re.compile(r"^Compra a cuenta de .* · #(\d+)$")
#: Un préstamo aprobado y su retiro nacen en el mismo acto (`aprobar`): más
#: de diez minutos entre uno y otro ya no es el mismo.
_VENTANA_SEG = 600

FK_LIBRETA = "fk_prestamo_empleada_libreta_venta_id_libreta_venta"
FK_ORIGEN = "fk_prestamo_empleada_origen_id_prestamo_empleada"
FK_RETIRO = "fk_caja_retiro_prestamo_id_prestamo_empleada"


def upgrade() -> None:
    with op.batch_alter_table("prestamo_empleada") as b:
        b.add_column(sa.Column("tipo", sa.String(20), nullable=False, server_default="prestamo"))
        b.add_column(sa.Column("libreta_venta_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("origen_id", sa.Integer(), nullable=True))
        b.create_foreign_key(FK_LIBRETA, "libreta_venta", ["libreta_venta_id"], ["id"], ondelete="SET NULL")
        b.create_foreign_key(FK_ORIGEN, "prestamo_empleada", ["origen_id"], ["id"], ondelete="SET NULL")
        b.create_index("ix_prestamo_empleada_tipo", ["tipo"])
        b.create_index("ix_prestamo_empleada_libreta_venta_id", ["libreta_venta_id"])
    with op.batch_alter_table("caja_retiro") as b:
        b.add_column(sa.Column("prestamo_id", sa.Integer(), nullable=True))
        b.create_foreign_key(FK_RETIRO, "prestamo_empleada", ["prestamo_id"], ["id"], ondelete="SET NULL")
        b.create_index("ix_caja_retiro_prestamo_id", ["prestamo_id"])
    rellenar(op.get_bind())


def downgrade() -> None:
    with op.batch_alter_table("caja_retiro") as b:
        b.drop_index("ix_caja_retiro_prestamo_id")
        b.drop_constraint(FK_RETIRO, type_="foreignkey")
        b.drop_column("prestamo_id")
    with op.batch_alter_table("prestamo_empleada") as b:
        b.drop_index("ix_prestamo_empleada_libreta_venta_id")
        b.drop_index("ix_prestamo_empleada_tipo")
        b.drop_constraint(FK_ORIGEN, type_="foreignkey")
        b.drop_constraint(FK_LIBRETA, type_="foreignkey")
        b.drop_column("origen_id")
        b.drop_column("libreta_venta_id")
        b.drop_column("tipo")


# ─── Backfill (puro: recibe la conexión; la prueba lo corre en SQLite) ──────


def _segundos(valor) -> float | None:
    """Fecha a segundos UTC. SQLite la devuelve como texto; sin zona = UTC."""
    if valor is None:
        return None
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor.replace(" ", "T", 1))
        except ValueError:
            return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.timestamp()


def rellenar(conn) -> None:
    prestamos = [dict(r._mapping) for r in conn.execute(sa.text(
        "SELECT id, employee_code, employee_name, monto, motivo, estado, resuelto_at, created_at "
        "FROM prestamo_empleada ORDER BY id"
    ))]
    por_id = {p["id"]: p for p in prestamos}

    # 1) Tipo: la compra a cuenta empezaba su motivo con «Compra a cuenta».
    compras = {p["id"] for p in prestamos if str(p["motivo"] or "").startswith(PREFIJO)}
    for pid in sorted(compras):
        conn.execute(sa.text("UPDATE prestamo_empleada SET tipo = 'compra_cuenta' WHERE id = :i"), {"i": pid})

    # 2) Origen de la parte cobrada de un pago parcial («(parte del #N)»).
    origen_de: dict[int, int] = {}
    for p in prestamos:
        m = _RE_PARTE.search(str(p["motivo"] or ""))
        if not m:
            continue
        origen = por_id.get(int(m.group(1)))
        if origen is None or origen["id"] == p["id"] or origen["employee_code"] != p["employee_code"]:
            continue
        origen_de[p["id"]] = origen["id"]
        conn.execute(sa.text("UPDATE prestamo_empleada SET origen_id = :o WHERE id = :i"),
                     {"o": origen["id"], "i": p["id"]})

    # 3) La venta de la compra, por el folio del ticket (el más cercano en
    #    fecha si el prefijo de 8 caracteres se repitiera).
    for pid in sorted(compras):
        p = por_id[pid]
        m = _RE_TICKET.search(str(p["motivo"] or ""))
        if not m:
            continue
        ventas = conn.execute(sa.text(
            "SELECT id, created_at FROM libreta_venta WHERE lower(operacion_uuid) LIKE :f ORDER BY id"
        ), {"f": f"{m.group(1).lower()}%"}).all()
        if not ventas:
            continue
        t = _segundos(p["created_at"]) or 0.0
        venta_id = min(ventas, key=lambda v: (abs((_segundos(v[1]) or 0.0) - t), v[0]))[0]
        conn.execute(sa.text("UPDATE prestamo_empleada SET libreta_venta_id = :v WHERE id = :i"),
                     {"v": venta_id, "i": pid})

    # 4) Los retiros.
    retiros = [dict(r._mapping) for r in conn.execute(sa.text(
        "SELECT id, monto, motivo, created_at FROM caja_retiro "
        "WHERE motivo LIKE 'Compra a cuenta de %' OR motivo LIKE 'Préstamo a %' ORDER BY id"
    ))]
    ligados: set[int] = set()
    # 4a) El de una compra lleva su número: «Compra a cuenta de X · #12».
    for r in retiros:
        m = _RE_RETIRO_COMPRA.match(str(r["motivo"] or ""))
        if m and int(m.group(1)) in compras:
            conn.execute(sa.text("UPDATE caja_retiro SET prestamo_id = :p WHERE id = :i"),
                         {"p": int(m.group(1)), "i": r["id"]})
            ligados.add(r["id"])
    # 4b) Préstamo normal: «Préstamo a <nombre>», mismo monto (el original,
    #     sumando sus partes cobradas) y cerca de cuando se aprobó. Solo si
    #     el par es único en las dos direcciones.
    partes_de: dict[int, list[int]] = {}
    for parte, origen in origen_de.items():
        partes_de.setdefault(origen, []).append(parte)
    candidatos: dict[int, list[int]] = {}
    for p in prestamos:
        if p["id"] in compras or p["id"] in origen_de or p["estado"] not in ("aprobado", "cobrado"):
            continue
        t = _segundos(p["resuelto_at"])
        if t is None:
            continue
        monto = sa_decimal(p["monto"]) + sum(sa_decimal(por_id[x]["monto"]) for x in partes_de.get(p["id"], []))
        motivo = f"Préstamo a {p['employee_name'] or p['employee_code']}"[:120]
        candidatos[p["id"]] = [
            r["id"] for r in retiros
            if r["id"] not in ligados and r["motivo"] == motivo and sa_decimal(r["monto"]) == monto
            and _segundos(r["created_at"]) is not None and abs(_segundos(r["created_at"]) - t) <= _VENTANA_SEG
        ]
    usos: dict[int, int] = {}
    for rs in candidatos.values():
        for rid in rs:
            usos[rid] = usos.get(rid, 0) + 1
    for pid, rs in sorted(candidatos.items()):
        if len(rs) == 1 and usos[rs[0]] == 1:
            conn.execute(sa.text("UPDATE caja_retiro SET prestamo_id = :p WHERE id = :i"), {"p": pid, "i": rs[0]})


def sa_decimal(valor):
    from decimal import Decimal

    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))
