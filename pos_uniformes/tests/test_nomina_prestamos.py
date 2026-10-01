"""El préstamo se descuenta del sueldo.

Es la parte que toca dinero de verdad: si el descuento no entra, se le paga de
más; si entra dos veces, se le paga de menos. Y si el préstamo es más grande
que el sueldo, el pago se queda en cero — nunca en negativo.
"""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from pos_uniformes.services.nomina_service import DetallePago


def _detalle(*, sueldo="1300", comisiones=56, faltas=0, prestamos="0"):
    return DetallePago(
        employee_code="VEND-5", desde=date(2026, 9, 18), hasta=date(2026, 9, 25),
        comisiones=comisiones, sueldo_base=Decimal(sueldo),
        tarifa_comision=Decimal("2.00"), faltas=faltas,
        descuento_falta=Decimal("100.00"), prestamos=Decimal(prestamos),
    )


class ElDescuentoTest(unittest.TestCase):
    def test_sin_prestamo_el_total_no_cambia(self):
        self.assertEqual(_detalle().total, Decimal("1412.00"))   # 1300 + 112

    def test_el_prestamo_se_resta_completo(self):
        self.assertEqual(_detalle(prestamos="500").total, Decimal("912.00"))

    def test_convive_con_el_descuento_por_faltas(self):
        # 1300 + 112 − 100 (una falta) − 500 = 812
        self.assertEqual(_detalle(faltas=1, prestamos="500").total, Decimal("812.00"))


class CuandoElPrestamoSeComeElPagoTest(unittest.TestCase):
    """Se le entrega cero, no se le cobra la diferencia."""

    def test_el_pago_nunca_sale_negativo(self):
        self.assertEqual(_detalle(prestamos="5000").total, Decimal("0.00"))

    def test_lo_que_no_alcanzo_se_hace_visible(self):
        # 1300 + 112 = 1412 de bruto; préstamo de 2000 deja 588 sin cubrir.
        d = _detalle(prestamos="2000")
        self.assertEqual(d.prestamo_sin_cubrir, Decimal("588.00"))

    def test_si_alcanza_no_queda_nada_pendiente(self):
        self.assertEqual(_detalle(prestamos="500").prestamo_sin_cubrir, Decimal("0.00"))


class ElDesgloseLoDiceTest(unittest.TestCase):
    def test_el_bot_enseña_el_prestamo_y_lo_que_falto(self):
        from pos_uniformes.services.telegram_pagos_service import _detalle_texto

        texto = "\n".join(_detalle_texto(_detalle(prestamos="2000"), "Fanny Ortiz"))
        self.assertIn("Préstamo: −$2,000.00", texto)
        self.assertIn("TOTAL: $0.00", texto)
        self.assertIn("$588.00 del préstamo sin cubrir", texto)

    def test_sin_prestamo_no_ensucia_el_desglose(self):
        from pos_uniformes.services.telegram_pagos_service import _detalle_texto

        texto = "\n".join(_detalle_texto(_detalle(), "Fanny Ortiz"))
        self.assertNotIn("Préstamo", texto)


class ElPagoLoGuardaTest(unittest.TestCase):
    def test_el_pago_registra_cuanto_se_descripto_y_salda_el_prestamo(self):
        import inspect

        from pos_uniformes.services import nomina_service as nom

        fuente = inspect.getsource(nom.registrar_pago_con_monto)
        # Queda guardado en la fila del pago, para entender un pago viejo.
        self.assertIn("descuento_prestamos=detalle.prestamos", fuente)
        # Y los préstamos quedan saldados con el id de ESE pago.
        self.assertIn("marcar_cobrados", fuente)
        self.assertIn("pago_id=int(pago.id)", fuente)

    def test_el_pendiente_trae_los_prestamos(self):
        import inspect

        from pos_uniformes.services import nomina_service as nom

        self.assertIn("total_por_cobrar", inspect.getsource(nom.pago_pendiente))


if __name__ == "__main__":
    unittest.main()
