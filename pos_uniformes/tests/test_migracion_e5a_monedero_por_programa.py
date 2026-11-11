"""E5-A: migración `e5a_monedero_por_programa`, en una base desechable propia
(la misma preparación que la de E4-A). No toca `pos_uniformes_test`.
"""

from __future__ import annotations

import unittest

from sqlalchemy import text

from pos_uniformes.tests import test_migracion_e4a_programas as e4a

REV_E4A = e4a.REV_E4A

REV_E5A = "b5e7c2d9a1f4"


class MigracionE5ATests(e4a.MigracionE4ATests):
    # Las pruebas de E4-A corren en su propio archivo.
    test_upgrade_crea_programas_activos_sin_tocar_clientes = None
    test_candado_de_una_activa_por_cliente_en_postgres = None
    test_downgrade_limpio_y_candado_si_hay_membresias = None

    def setUp(self) -> None:
        super().setUp()
        self._alembic("upgrade", REV_E4A)
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO membresia (cliente_id, programa_id, estado, desde) "
                "SELECT 1, id, 'activa', now() FROM programa WHERE clave = 'CLUB'"
            ))

    def _programas(self):
        with self.engine.connect() as conn:
            return [tuple(r) for r in conn.execute(text(
                "SELECT clave, orden, tasa_monedero::text, permite_descuento, ingreso_modo FROM programa ORDER BY orden"
            ))]

    def test_upgrade_pone_tasas_y_agrega_leal_sin_tocar_membresias(self) -> None:
        clientes = self._foto()
        self._alembic("upgrade", REV_E5A)
        self.assertEqual(self._programas(), [
            ("CLUB", 1, "5.00", False, "directo_empleada"),
            ("LEAL", 2, "10.00", False, "automatico"),
            ("PROFESIONAL", 3, "13.00", False, "aprobacion_dueno"),
            ("MAYORISTA", 4, "15.00", True, "aprobacion_dueno"),
        ])
        self.assertEqual(self._foto(), clientes)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM membresia")).scalar_one(), 1)
            self.assertEqual(conn.execute(text("SELECT count(*) FROM programa_tasa_cambio")).scalar_one(), 0)

    def test_la_tasa_no_sale_de_0_a_100(self) -> None:
        self._alembic("upgrade", REV_E5A)
        for mala in ("-1", "100.5"):
            with self.subTest(mala=mala), self.assertRaises(Exception):
                with self.engine.begin() as conn:
                    conn.execute(text(f"UPDATE programa SET tasa_monedero = {mala} WHERE clave = 'CLUB'"))

    def test_downgrade_regresa_a_tres_y_se_detiene_si_hay_miembros_de_leal(self) -> None:
        self._alembic("upgrade", REV_E5A)
        self._alembic("downgrade", REV_E4A)
        with self.engine.connect() as conn:
            progs = [tuple(r) for r in conn.execute(text("SELECT clave, orden FROM programa ORDER BY orden"))]
            membresias = conn.execute(text("SELECT count(*) FROM membresia")).scalar_one()
        self.assertEqual(progs, [("CLUB", 1), ("PROFESIONAL", 2), ("MAYORISTA", 3)])
        self.assertEqual(membresias, 1, "la de Club se queda")
        self.assertFalse(self._existe("programa_tasa_cambio"))

        self._alembic("upgrade", REV_E5A)
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO membresia (cliente_id, programa_id, estado, desde) "
                "SELECT 2, id, 'activa', now() FROM programa WHERE clave = 'LEAL'"
            ))
        self.assertIn("Downgrade E5-A detenido", self._alembic("downgrade", REV_E4A, debe_fallar=True))
        self._alembic("downgrade", REV_E4A, extra_env={"POS_E5A_DOWNGRADE_ACEPTO_PERDIDA": "1"})
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM membresia")).scalar_one(), 1)


if __name__ == "__main__":
    unittest.main()
