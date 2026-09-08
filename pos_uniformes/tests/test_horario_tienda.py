"""Horario de la tienda: cierre 18:00 (jueves y domingo 17:00), corte 30 min antes."""

from __future__ import annotations

import unittest
from datetime import date, datetime, time

from pos_uniformes.services.horario_tienda_service import (
    decidir_corte_automatico,
    es_momento_de_corte,
    es_momento_de_resumen,
    hora_cierre,
    hora_corte,
    hora_resumen,
    horas_de_corte_posibles,
    horas_de_resumen_posibles,
    texto_horario_corte,
)
from pos_uniformes.services.nomina_service import puede_pagar

LUNES, JUEVES, SABADO, DOMINGO = date(2026, 9, 7), date(2026, 9, 10), date(2026, 9, 12), date(2026, 9, 13)


class HorarioTests(unittest.TestCase):
    def test_cierre_y_corte(self) -> None:
        self.assertEqual(hora_cierre(LUNES), time(18, 0))
        self.assertEqual(hora_cierre(SABADO), time(18, 0))
        self.assertEqual(hora_cierre(JUEVES), time(17, 0))
        self.assertEqual(hora_cierre(DOMINGO), time(17, 0))
        self.assertEqual(hora_corte(LUNES), time(17, 30))
        self.assertEqual(hora_corte(JUEVES), time(16, 30))
        self.assertEqual(hora_corte(DOMINGO), time(16, 30))

    def test_resumen_15_min_antes_de_cerrar(self) -> None:
        self.assertEqual(hora_resumen(LUNES), time(17, 45))
        self.assertEqual(hora_resumen(JUEVES), time(16, 45))
        self.assertEqual(hora_resumen(DOMINGO), time(16, 45))
        self.assertEqual(horas_de_resumen_posibles(), [time(16, 45), time(17, 45)])
        self.assertTrue(es_momento_de_resumen(datetime(2026, 9, 7, 17, 46)))
        self.assertFalse(es_momento_de_resumen(datetime(2026, 9, 7, 16, 46)))
        self.assertTrue(es_momento_de_resumen(datetime(2026, 9, 10, 16, 45)))
        self.assertFalse(es_momento_de_resumen(datetime(2026, 9, 10, 17, 45)))

    def test_horas_posibles_y_texto(self) -> None:
        self.assertEqual(horas_de_corte_posibles(), [time(16, 30), time(17, 30)])
        self.assertIn("17:30", texto_horario_corte())
        self.assertIn("16:30", texto_horario_corte())

    def test_ventana(self) -> None:
        self.assertTrue(es_momento_de_corte(datetime(2026, 9, 7, 17, 30)))
        self.assertTrue(es_momento_de_corte(datetime(2026, 9, 7, 17, 45)))
        self.assertFalse(es_momento_de_corte(datetime(2026, 9, 7, 16, 30)))  # lunes a las 16:30 no toca
        self.assertTrue(es_momento_de_corte(datetime(2026, 9, 10, 16, 31)))  # jueves sí
        self.assertFalse(es_momento_de_corte(datetime(2026, 9, 10, 17, 30)))


class DecisionTests(unittest.TestCase):
    def test_hace_cuando_toca_y_hay_movimiento(self) -> None:
        d = decidir_corte_automatico(datetime(2026, 9, 7, 17, 32), datetime(2026, 9, 6, 16, 30), True)
        self.assertTrue(d.hacer)

    def test_no_repite_si_ya_hubo_corte_hoy_cerca_de_la_hora(self) -> None:
        d = decidir_corte_automatico(datetime(2026, 9, 7, 17, 32), datetime(2026, 9, 7, 17, 0), True)
        self.assertFalse(d.hacer)
        self.assertIn("ya hubo corte", d.motivo)

    def test_corte_manual_temprano_no_bloquea_el_de_la_tarde(self) -> None:
        # Un corte a mediodía (p.ej. Daniel contando) no impide el de cierre.
        d = decidir_corte_automatico(datetime(2026, 9, 7, 17, 32), datetime(2026, 9, 7, 12, 0), True)
        self.assertTrue(d.hacer)

    def test_sin_movimiento_no_hace(self) -> None:
        d = decidir_corte_automatico(datetime(2026, 9, 7, 17, 32), None, False)
        self.assertFalse(d.hacer)

    def test_fuera_de_hora_no_hace(self) -> None:
        d = decidir_corte_automatico(datetime(2026, 9, 7, 16, 32), None, True)
        self.assertFalse(d.hacer)

    def test_auto_puede_registrar_pagos(self) -> None:
        self.assertTrue(puede_pagar("AUTO"))


if __name__ == "__main__":
    unittest.main()
