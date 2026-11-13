"""Migración `c9a4e2b7d1f3` (compra a cuenta por columnas, 2026-11-12).

Dos pruebas:

- En SQLite (siempre corre): se arma el esquema de antes con lo mínimo, se
  corre `upgrade()` con Alembic y se revisa el backfill desde los textos de
  hoy; luego `downgrade()` quita las columnas.
- En PostgreSQL, en la base desechable de las pruebas de migración (como
  E6/E7): se lleva hasta la revisión anterior, se siembra y se sube. Se salta
  si no hay Postgres local de prueba. No toca `pos_uniformes_test`.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

_VERSIONES = Path(__file__).resolve().parents[1] / "migrations" / "versions"
REV_ANTES = "f1c2d3e4a5b6"
REV_COLUMNAS = "c9a4e2b7d1f3"

#: Los datos de ejemplo (iguales en las dos bases).
#  prestamo 1: compra con su venta (ticket abcdef12) y su retiro «· #1»
#  prestamo 2: préstamo normal aprobado con su retiro «Préstamo a Ana»
#  prestamo 3: parte cobrada del préstamo 2 («(parte del #2)»)
#  prestamo 4: otro préstamo de Ana, aprobado lejos en el tiempo: su retiro no
#              se adivina
#  prestamo 5: compra sin folio
#  prestamo 6 y 7: dos préstamos iguales el mismo minuto: ambiguos, NULL
_VENTAS = [
    (1, "abcdef12-0000-4000-8000-000000000001", "2026-11-10 10:00:00"),
    (2, "abcdef12-9999-4000-8000-000000000009", "2026-10-01 10:00:00"),   # mismo prefijo, lejos
    (3, "77777777-0000-4000-8000-000000000007", "2026-11-10 10:00:00"),
]
_PRESTAMOS = [
    (1, "VEND-3", "Cristal", "332.00", "Compra a cuenta · pago del sáb 14 nov · ticket abcdef12", "aprobado",
     "2026-11-10 11:00:00", "2026-11-10 10:00:05"),
    (2, "VEND-4", "Ana", "200.00", "renta", "aprobado", "2026-11-05 12:00:00", "2026-11-05 09:00:00"),
    (3, "VEND-4", "Ana", "100.00", "renta (parte del #2)", "cobrado", "2026-11-05 12:00:00", "2026-11-05 09:00:00"),
    (4, "VEND-4", "Ana", "300.00", "comida", "aprobado", "2026-11-08 12:00:00", "2026-11-08 09:00:00"),
    (5, "VEND-3", "Cristal", "50.00", "Compra a cuenta · pago del sáb 14 nov", "pedido", None, "2026-11-11 10:00:00"),
    (6, "VEND-5", "Lupe", "80.00", "a", "aprobado", "2026-11-09 12:00:00", "2026-11-09 09:00:00"),
    (7, "VEND-5", "Lupe", "80.00", "b", "aprobado", "2026-11-09 12:01:00", "2026-11-09 09:00:00"),
]
_RETIROS = [
    (1, "332.00", "Compra a cuenta de Cristal · #1", "2026-11-10 10:00:06"),
    (2, "300.00", "Préstamo a Ana", "2026-11-05 12:00:02"),   # 200 + la parte de 100
    (3, "300.00", "Préstamo a Ana", "2026-11-01 12:00:00"),   # lejos de cualquier aprobación
    (4, "50.00", "Compra a cuenta de bolsas", "2026-11-11 10:00:00"),
    (5, "80.00", "Préstamo a Lupe", "2026-11-09 12:00:30"),
]
_ESPERADO_PRESTAMOS = {
    # id: (tipo, libreta_venta_id, origen_id)
    1: ("compra_cuenta", 1, None),
    2: ("prestamo", None, None),
    3: ("prestamo", None, 2),
    4: ("prestamo", None, None),
    5: ("compra_cuenta", None, None),
    6: ("prestamo", None, None),
    7: ("prestamo", None, None),
}
_ESPERADO_RETIROS = {1: 1, 2: 2, 3: None, 4: None, 5: None}


def _modulo():
    ruta = next(_VERSIONES.glob(f"{REV_COLUMNAS}_*.py"))
    spec = importlib.util.spec_from_file_location("mig_compra_cuenta_columnas", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sembrar(conn) -> None:
    for i, u, c in _VENTAS:
        conn.execute(text("INSERT INTO libreta_venta (id, operacion_uuid, created_at) VALUES (:i, :u, :c)"),
                     {"i": i, "u": u, "c": c})
    for i, code, nombre, monto, motivo, estado, resuelto, creado in _PRESTAMOS:
        conn.execute(text(
            "INSERT INTO prestamo_empleada (id, employee_code, employee_name, monto, motivo, estado, resuelto_at, "
            "created_at) VALUES (:i, :code, :n, :m, :mo, :e, :r, :c)"
        ), {"i": i, "code": code, "n": nombre, "m": monto, "mo": motivo, "e": estado, "r": resuelto, "c": creado})
    for i, monto, motivo, creado in _RETIROS:
        conn.execute(text("INSERT INTO caja_retiro (id, monto, motivo, created_at) VALUES (:i, :m, :mo, :c)"),
                     {"i": i, "m": monto, "mo": motivo, "c": creado})


def _leer(conn):
    prestamos = {r[0]: (r[1], r[2], r[3]) for r in conn.execute(text(
        "SELECT id, tipo, libreta_venta_id, origen_id FROM prestamo_empleada ORDER BY id"))}
    retiros = {r[0]: r[1] for r in conn.execute(text("SELECT id, prestamo_id FROM caja_retiro ORDER BY id"))}
    return prestamos, retiros


class MigracionSQLiteTests(unittest.TestCase):
    """El esquema de antes, con lo mínimo que la migración toca."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as conn:
            conn.execute(text("CREATE TABLE libreta_venta (id INTEGER PRIMARY KEY, operacion_uuid VARCHAR(36), "
                              "created_at DATETIME)"))
            conn.execute(text(
                "CREATE TABLE prestamo_empleada (id INTEGER PRIMARY KEY, employee_code VARCHAR(40) NOT NULL, "
                "employee_name VARCHAR(120) NOT NULL DEFAULT '', monto NUMERIC(12,2) NOT NULL, "
                "motivo VARCHAR(200) NOT NULL DEFAULT '', estado VARCHAR(20) NOT NULL, resuelto_at DATETIME, "
                "created_at DATETIME NOT NULL)"))
            conn.execute(text("CREATE TABLE caja_retiro (id INTEGER PRIMARY KEY, monto NUMERIC(12,2) NOT NULL, "
                              "motivo VARCHAR(120) NOT NULL DEFAULT '', created_at DATETIME NOT NULL)"))
            _sembrar(conn)

    def _correr(self, accion: str) -> None:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        mod = _modulo()
        with self.engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                getattr(mod, accion)()

    def test_upgrade_rellena_desde_los_textos_y_downgrade_quita(self) -> None:
        self._correr("upgrade")
        with self.engine.connect() as conn:
            prestamos, retiros = _leer(conn)
        self.assertEqual(prestamos, _ESPERADO_PRESTAMOS)
        self.assertEqual(retiros, _ESPERADO_RETIROS)
        cols = {c["name"] for c in inspect(self.engine).get_columns("prestamo_empleada")}
        self.assertTrue({"tipo", "libreta_venta_id", "origen_id"} <= cols)
        self._correr("downgrade")
        insp = inspect(self.engine)
        self.assertFalse({"tipo", "libreta_venta_id", "origen_id"} & {c["name"] for c in insp.get_columns("prestamo_empleada")})
        self.assertNotIn("prestamo_id", {c["name"] for c in insp.get_columns("caja_retiro")})
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM prestamo_empleada")).scalar_one(), 7)

    def test_un_prestamo_nuevo_queda_como_prestamo(self) -> None:
        self._correr("upgrade")
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO prestamo_empleada (id, employee_code, monto, estado, created_at) "
                              "VALUES (99, 'VEND-9', 10, 'pedido', '2026-11-12 10:00:00')"))
            self.assertEqual(conn.execute(text("SELECT tipo FROM prestamo_empleada WHERE id = 99")).scalar_one(),
                             "prestamo")


def _base_e7():
    try:
        from pos_uniformes.tests import test_migracion_e7_rebajas as e7
    except Exception:  # noqa: BLE001
        return None
    return e7


_e7 = _base_e7()


@unittest.skipIf(_e7 is None, "Sin las pruebas de migración de Postgres")
class MigracionPostgresTests(_e7.MigracionE7Tests if _e7 is not None else unittest.TestCase):
    # Las de E7 (y anteriores) corren en su propio archivo.
    test_upgrade_crea_la_tabla_vacia_y_downgrade_la_quita = None

    def test_upgrade_rellena_y_downgrade_quita(self) -> None:
        self._alembic("upgrade", REV_ANTES)
        with self.engine.begin() as conn:
            # libreta_venta y prestamo_empleada piden más columnas en Postgres.
            for i, u, c in _VENTAS:
                conn.execute(text(
                    "INSERT INTO libreta_venta (id, employee_code, employee_name, tipo, piezas, comisiones, "
                    "monto_total, monto_neto, pago_tarjeta, privado, descuento_empleada, detalle, created_at, "
                    "operacion_uuid, monto_monedero) VALUES (:i, 'VEND-3', 'Cristal', 'venta', 1, 0, 332, 332, "
                    "false, false, true, '[]', CAST(:c AS timestamptz), :u, 0)"
                ), {"i": i, "u": u, "c": c})
            for i, code, nombre, monto, motivo, estado, resuelto, creado in _PRESTAMOS:
                conn.execute(text(
                    "INSERT INTO prestamo_empleada (id, employee_code, employee_name, monto, motivo, estado, "
                    "resuelto_at, created_at) VALUES (:i, :code, :n, :m, :mo, :e, CAST(:r AS timestamptz), "
                    "CAST(:c AS timestamptz))"
                ), {"i": i, "code": code, "n": nombre, "m": monto, "mo": motivo, "e": estado, "r": resuelto, "c": creado})
            for i, monto, motivo, creado in _RETIROS:
                conn.execute(text(
                    "INSERT INTO caja_retiro (id, monto, motivo, creado_por, en_cajon, created_at) "
                    "VALUES (:i, :m, :mo, 'VEND-1', true, CAST(:c AS timestamptz))"
                ), {"i": i, "m": monto, "mo": motivo, "c": creado})
        self._alembic("upgrade", REV_COLUMNAS)
        with self.engine.connect() as conn:
            prestamos, retiros = _leer(conn)
        self.assertEqual(prestamos, _ESPERADO_PRESTAMOS)
        self.assertEqual(retiros, _ESPERADO_RETIROS)
        self._alembic("downgrade", REV_ANTES)
        with self.engine.connect() as conn:
            cols = conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE "
                "(table_name = 'prestamo_empleada' AND column_name IN ('tipo', 'libreta_venta_id', 'origen_id')) "
                "OR (table_name = 'caja_retiro' AND column_name = 'prestamo_id')"
            )).all()
        self.assertEqual(cols, [])


if __name__ == "__main__":
    unittest.main()
