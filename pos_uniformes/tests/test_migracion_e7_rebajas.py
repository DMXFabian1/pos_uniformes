"""E7: migración `e7_ofertas_y_liquidacion`, en la base desechable de las
pruebas de migración. No toca `pos_uniformes_test`.
"""

from __future__ import annotations

import unittest

from sqlalchemy import text

from pos_uniformes.tests import test_migracion_e6_descuento_empleadas as e6

REV_E6 = e6.REV_E6
REV_E7 = "d7a3f9c2e8b1"


class MigracionE7Tests(e6.MigracionE6Tests):
    # Las de E6 corren en su propio archivo.
    test_upgrade_pone_niveles_y_tope_sin_tocar_ventas = None
    test_downgrade_limpio = None

    def setUp(self) -> None:
        super().setUp()
        self._alembic("upgrade", REV_E6)

    def test_upgrade_crea_la_tabla_vacia_y_downgrade_la_quita(self) -> None:
        clientes = self._foto()
        self._alembic("upgrade", REV_E7)
        self.assertTrue(self._existe("rebaja_producto"))
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM rebaja_producto")).scalar_one(), 0)
        self.assertEqual(self._foto(), clientes)
        self._alembic("downgrade", REV_E6)
        self.assertFalse(self._existe("rebaja_producto"))


if __name__ == "__main__":
    unittest.main()
