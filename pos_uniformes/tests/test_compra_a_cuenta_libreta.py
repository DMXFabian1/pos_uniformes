"""La venta de una compra a cuenta viva no se borra de la Libreta (revisión
2026-11-12).

El corte deja fuera la venta y el retiro de la compra juntos mientras están
ligados. Si se borrara la venta, la FK pone `libreta_venta_id` en NULL y el
retiro volvería a contar solo: un sobrante falso.
"""

from __future__ import annotations

import unittest
from decimal import Decimal as D

from tests.test_compra_a_cuenta_columnas import _Base
from pos_uniformes.services import prestamos_service as pr


class BorrarVentaACuentaTests(_Base):
    def test_no_se_borra_la_venta_de_una_compra_viva(self):
        from pos_uniformes.services import libreta_service as lib

        venta = self._venta()
        p = self._compra(venta=venta)
        for borrar in (lambda: lib.eliminar_operacion(self.s, venta.id),
                       lambda: lib.borrar_desde_libreta(self.s, venta.id, actor="VEND-1")):
            with self.subTest(borrar=borrar), self.assertRaises(lib.OperacionConCambios) as err:
                borrar()
            self.assertIn("recházala", str(err.exception))
        self.assertEqual(self._corte(), ([], [], D("0.00")))
        # Rechazada, ya se puede borrar y el corte sigue neutro.
        pr.rechazar(self.s, p.id, quien="VEND-1")
        self.assertTrue(lib.eliminar_operacion(self.s, venta.id))
        self.s.flush()
        self.assertEqual(self._corte(), ([], [], D("0.00")))

    def test_autorizada_tampoco_se_borra(self):
        from pos_uniformes.services import libreta_service as lib

        venta = self._venta()
        p = self._compra(venta=venta)
        pr.aprobar(self.s, p.id, quien="VEND-1")
        with self.assertRaises(lib.OperacionACuenta) as err:
            lib.eliminar_operacion(self.s, venta.id)
        self.assertIn("autorizada", str(err.exception))


if __name__ == "__main__":
    unittest.main()
