"""Migración `d1e2f3a4b5c6` (unir ventas en una operación, 2026-11-13).

En SQLite (siempre corre): se arma `libreta_venta` como estaba, se corre
`upgrade()` y se revisa que las ventas de antes queden solas (NULL) y que una
unión nueva se pueda guardar; luego `downgrade()` quita las columnas sin
tocar las ventas. No se aplica en ninguna base real.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

_VERSIONES = Path(__file__).resolve().parents[1] / "migrations" / "versions"
REV = "d1e2f3a4b5c6"
COLUMNAS = {"operacion_grupo_id", "operacion_unida_por", "operacion_unida_en"}


def _modulo():
    ruta = next(_VERSIONES.glob(f"{REV}_*.py"))
    spec = importlib.util.spec_from_file_location("mig_libreta_unir", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MigracionUnirSQLiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE libreta_venta (id INTEGER PRIMARY KEY, employee_code VARCHAR(40) NOT NULL, "
                "tipo VARCHAR(20) NOT NULL DEFAULT 'venta', created_at DATETIME)"))
            for i in (1, 2, 3):
                conn.execute(text("INSERT INTO libreta_venta (id, employee_code, created_at) "
                                  "VALUES (:i, 'VEND-4', '2026-11-13 10:00:00')"), {"i": i})

    def _correr(self, accion: str) -> None:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        mod = _modulo()
        with self.engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                getattr(mod, accion)()

    def test_revision_sigue_a_la_cabeza_anterior(self) -> None:
        self.assertEqual(_modulo().down_revision, "c9a4e2b7d1f3")

    def test_upgrade_deja_todo_solo_y_downgrade_quita(self) -> None:
        self._correr("upgrade")
        cols = {c["name"] for c in inspect(self.engine).get_columns("libreta_venta")}
        self.assertTrue(COLUMNAS <= cols)
        with self.engine.begin() as conn:
            self.assertEqual(conn.execute(text(
                "SELECT count(*) FROM libreta_venta WHERE operacion_grupo_id IS NOT NULL")).scalar_one(), 0)
            conn.execute(text("UPDATE libreta_venta SET operacion_grupo_id = 1, operacion_unida_por = 'VEND-1', "
                              "operacion_unida_en = '2026-11-13 11:00:00' WHERE id IN (1, 2)"))
            self.assertEqual(conn.execute(text(
                "SELECT count(DISTINCT coalesce(operacion_grupo_id, id)) FROM libreta_venta")).scalar_one(), 2)
        self._correr("downgrade")
        cols = {c["name"] for c in inspect(self.engine).get_columns("libreta_venta")}
        self.assertFalse(COLUMNAS & cols)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM libreta_venta")).scalar_one(), 3)


if __name__ == "__main__":
    unittest.main()
