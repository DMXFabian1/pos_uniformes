"""«Vendido» tiene que querer decir vendido.

El encabezado de Cortes anteriores decía «Vendido» pero sumaba la cifra que
Daniel **entregó**: efectivo, con sus ajustes y sin la tarjeta (2026-10-01:
"¿es eso lo que se vendió en el mes? quiero saber solo ventas").
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from pos_uniformes.services.historial_cortes_service import totales_cortes


class _Corte:
    """Un corte como lo guarda la Libreta."""

    def __init__(self, final, esperado, *, reactivo="11160", pagos="0", gastos="0"):
        # `desde` marca que es un corte por periodo; sin él se trata como de
        # los viejos, donde la cifra ERA el total del día.
        from datetime import datetime

        self.desde = datetime(2026, 9, 17, 17, 0)
        self.monto_final = Decimal(final)
        self.monto_esperado = Decimal(esperado)
        self.reactivo_inicial = Decimal(reactivo)
        self.reactivo_final = Decimal(reactivo)
        self.retiros_pagos = Decimal(pagos)
        self.otros_retiros = Decimal(gastos)


class VendidoTest(unittest.TestCase):
    def setUp(self) -> None:
        # Entregó 1,000 menos de lo que la caja esperaba: un ajuste suyo.
        self.cortes = [_Corte("16082", "17082"), _Corte("20548", "22548")]

    def test_el_reactivo_no_cuenta_como_venta(self):
        t = totales_cortes([_Corte("12160", "12160", reactivo="11160")])
        self.assertEqual(t.venta, Decimal("1000.00"), "solo lo que entró, no el fondo")

    def test_vendido_suma_la_tarjeta_que_el_cajon_no_ve(self):
        t = totales_cortes(self.cortes, tarjeta=Decimal("14445.00"))
        # efectivo real: (17082−11160) + (22548−11160) = 17310
        self.assertEqual(t.venta_real, Decimal("17310.00"))
        self.assertEqual(t.vendido, Decimal("31755.00"))

    def test_lo_entregado_se_guarda_aparte_y_no_se_confunde(self):
        t = totales_cortes(self.cortes)
        self.assertEqual(t.venta, Decimal("14310.00"))      # con los ajustes
        self.assertEqual(t.venta_real, Decimal("17310.00"))  # sin ellos
        self.assertNotEqual(t.venta, t.venta_real)

    def test_dice_cuanto_se_ajusto(self):
        self.assertEqual(totales_cortes(self.cortes).ajustes, Decimal("-3000.00"))

    def test_sin_ajustes_la_entrega_y_lo_real_coinciden(self):
        t = totales_cortes([_Corte("17082", "17082")])
        self.assertEqual(t.ajustes, Decimal("0.00"))
        self.assertEqual(t.venta, t.venta_real)

    def test_los_pagos_y_gastos_vuelven_a_la_venta(self):
        # Salieron del cajón, pero se vendieron: si no se suman, la venta sale corta.
        t = totales_cortes([_Corte("12160", "12160", pagos="500", gastos="300")])
        self.assertEqual(t.venta, Decimal("1800.00"))


class ElEncabezadoTest(unittest.TestCase):
    def test_el_dialogo_enseña_vendido_y_no_lo_entregado(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "ui" / "dialogs" / "historial_cortes_dialog.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Vendido: ${t.vendido:,.2f}", fuente)
        self.assertIn("tarjeta ${t.tarjeta:,.2f}", fuente)
        self.assertIn("Entregado", fuente)


if __name__ == "__main__":
    unittest.main()
