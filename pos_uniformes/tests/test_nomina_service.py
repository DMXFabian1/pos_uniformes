"""Nómina: 1300 base + 2 por comisión − 216.67 por falta, por ciclo de 7 días."""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from pos_uniformes.services import nomina_service as nomina
from pos_uniformes.services.corte_caja_service import ParametrosCaja
from pos_uniformes.services.calendario_empleadas_service import FALTA, HorarioEmpleada
from pos_uniformes.services.nomina_service import AvisoPago, ResumenEncargado, calcular_pago, puede_pagar, texto_resumen_encargado

PARAMS = ParametrosCaja(
    reactivo_actual=Decimal("11160.00"),
    sueldo_base=Decimal("1300.00"),
    tarifa_comision=Decimal("2.00"),
    descuento_falta=Decimal("216.67"),
)


class CalcularPagoTests(unittest.TestCase):
    def test_base_mas_comisiones(self) -> None:
        h = HorarioEmpleada("VEND-2", descanso_weekday=6, fecha_ultimo_pago=date(2026, 9, 1))
        d = calcular_pago(h, comisiones=45, params=PARAMS, hasta=date(2026, 9, 8))
        self.assertEqual(d.desde, date(2026, 9, 2))
        self.assertEqual(d.monto_comisiones, Decimal("90.00"))
        self.assertEqual(d.faltas, 0)
        self.assertEqual(d.total, Decimal("1390.00"))

    def test_falta_dentro_del_ciclo_descuenta(self) -> None:
        h = HorarioEmpleada("VEND-2", fecha_ultimo_pago=date(2026, 9, 1))
        h.eventos[date(2026, 9, 4)] = FALTA
        h.eventos[date(2026, 8, 30)] = FALTA  # ciclo anterior: no cuenta
        d = calcular_pago(h, comisiones=10, params=PARAMS, hasta=date(2026, 9, 8))
        self.assertEqual(d.faltas, 1)
        self.assertEqual(d.descuento_faltas, Decimal("216.67"))
        self.assertEqual(d.total, Decimal("1103.33"))

    def test_sin_pago_previo_mira_los_ultimos_7_dias(self) -> None:
        h = HorarioEmpleada("VEND-3")
        h.eventos[date(2026, 9, 3)] = FALTA
        h.eventos[date(2026, 8, 20)] = FALTA
        d = calcular_pago(h, comisiones=0, params=PARAMS, hasta=date(2026, 9, 8))
        self.assertIsNone(d.desde)
        self.assertEqual(d.faltas, 1)
        self.assertEqual(d.total, Decimal("1083.33"))

    def test_nunca_negativo(self) -> None:
        h = HorarioEmpleada("VEND-2", fecha_ultimo_pago=date(2026, 9, 1))
        for dia in range(2, 9):
            h.eventos[date(2026, 9, dia)] = FALTA
        d = calcular_pago(h, comisiones=0, params=PARAMS, hasta=date(2026, 9, 8))
        self.assertEqual(d.total, Decimal("0.00"))

    def test_quien_puede_pagar(self) -> None:
        self.assertTrue(puede_pagar("VEND-1"))
        self.assertTrue(puede_pagar("enc-1"))
        self.assertFalse(puede_pagar("VEND-2"))
        self.assertFalse(puede_pagar(None))


class RegistrarPagoTests(unittest.TestCase):
    def test_empleada_no_puede_registrar(self) -> None:
        with self.assertRaises(PermissionError):
            nomina.registrar_pago_con_monto(MagicMock(), "VEND-3", creado_por="VEND-2")

    def test_guarda_desglose_y_anota_calendario(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        h = HorarioEmpleada("VEND-2", fecha_ultimo_pago=date(2026, 9, 1))
        with patch.object(nomina, "cargar_horario", return_value=h), patch.object(
            nomina, "comisiones_desde_ultimo_pago", return_value=45
        ), patch.object(nomina, "cargar_parametros", return_value=PARAMS), patch.object(
            nomina, "registrar_pago"
        ) as reg:
            pago = nomina.registrar_pago_con_monto(session, "vend-2", creado_por="ENC-1", fecha=date(2026, 9, 8))
        session.add.assert_called_once_with(pago)
        reg.assert_called_once_with(session, "VEND-2", date(2026, 9, 8))
        self.assertEqual(pago.total, Decimal("1390.00"))
        self.assertEqual(pago.comisiones, 45)
        self.assertEqual(pago.creado_por, "ENC-1")
        self.assertEqual(pago.desde, date(2026, 9, 2))
        self.assertEqual(pago.hasta, date(2026, 9, 8))


class TextoEncargadoTests(unittest.TestCase):
    def test_texto_con_descansos_y_pagos(self) -> None:
        r = ResumenEncargado(
            descansan_hoy=["Ana"],
            descansan_manana=[],
            pagos=[
                AvisoPago("VEND-2", "Ana", date(2026, 9, 8), 0, 45, Decimal("1390.00")),
                AvisoPago("VEND-3", "Bety", date(2026, 9, 6), -2, 10, Decimal("1320.00")),
                AvisoPago("VEND-4", "Caro", None, None, 3, Decimal("1306.00")),
            ],
        )
        texto = texto_resumen_encargado(r, hoy=date(2026, 9, 8))
        self.assertIn("Hoy descansa: Ana", texto)
        self.assertIn("Mañana descansa: nadie", texto)
        self.assertIn("Ana: HOY · 45 comisiones · $1,390.00", texto)
        self.assertIn("Bety: ATRASADO 2 día(s)", texto)
        self.assertIn("Caro: sin fecha", texto)

    def test_sin_pagos(self) -> None:
        texto = texto_resumen_encargado(ResumenEncargado([], [], []), hoy=date(2026, 9, 8))
        self.assertIn("ninguno en los próximos 7 días", texto)


if __name__ == "__main__":
    unittest.main()
