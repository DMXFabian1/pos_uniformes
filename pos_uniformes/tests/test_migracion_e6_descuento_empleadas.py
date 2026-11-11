"""E6: migración `e6_descuento_empleadas_por_nivel`, en la base desechable de
las pruebas de migración de E4-A/E5-A. No toca `pos_uniformes_test`.
"""

from __future__ import annotations

import unittest

from sqlalchemy import text

from pos_uniformes.tests import test_migracion_e5a_monedero_por_programa as e5a

REV_E5A = e5a.REV_E5A
REV_E6 = "c6d1e8a4b2f7"


class MigracionE6Tests(e5a.MigracionE5ATests):
    # Las de E5-A corren en su propio archivo.
    test_upgrade_pone_tasas_y_agrega_leal_sin_tocar_membresias = None
    test_la_tasa_no_sale_de_0_a_100 = None
    test_downgrade_regresa_a_tres_y_se_detiene_si_hay_miembros_de_leal = None

    def setUp(self) -> None:
        super().setUp()
        self._alembic("upgrade", REV_E5A)

    def test_upgrade_pone_niveles_y_tope_sin_tocar_ventas(self) -> None:
        clientes = self._foto()
        self._alembic("upgrade", REV_E6)
        with self.engine.connect() as conn:
            niveles = [tuple(r) for r in conn.execute(text(
                "SELECT comisiones_minimas, porcentaje::text FROM nivel_descuento_empleada ORDER BY 1"
            ))]
            topes = conn.execute(text("SELECT DISTINCT tope_compra_empleada_mes::text FROM configuracion_negocio")).scalars().all()
            compradoras = conn.execute(text("SELECT count(*) FROM libreta_venta WHERE compradora_code IS NOT NULL")).scalar_one()
        self.assertEqual(niveles, [(0, "5.00"), (150, "10.00"), (250, "15.00"), (350, "20.00")])
        self.assertIn(topes, ([], ["3000.00"]))
        self.assertEqual(compradoras, 0)
        self.assertEqual(self._foto(), clientes)
        for malo in ("-1", "31"):
            with self.subTest(malo=malo), self.assertRaises(Exception):
                with self.engine.begin() as conn:
                    conn.execute(text(f"UPDATE nivel_descuento_empleada SET porcentaje = {malo} WHERE comisiones_minimas = 0"))

    def test_downgrade_limpio(self) -> None:
        self._alembic("upgrade", REV_E6)
        self._alembic("downgrade", REV_E5A)
        self.assertFalse(self._existe("nivel_descuento_empleada"))
        with self.engine.connect() as conn:
            cols = conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'libreta_venta' "
                "AND column_name = 'compradora_code'"
            )).all()
        self.assertEqual(cols, [])


if __name__ == "__main__":
    unittest.main()
