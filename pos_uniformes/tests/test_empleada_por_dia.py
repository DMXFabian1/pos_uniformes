"""Empleadas por días (Naye): trabaja ciertos días, cobra por día al terminar sus días."""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from pos_uniformes.services.calendario_empleadas_service import (
    DESCANSO,
    FALTA,
    MODO_POR_DIA,
    TRABAJO,
    HorarioEmpleada,
    estado_del_dia,
    fecha_proximo_pago,
    quienes_descansan,
)
from pos_uniformes.services.corte_caja_service import ParametrosCaja
from pos_uniformes.services.nomina_service import calcular_pago

PARAMS = ParametrosCaja(Decimal("11160"), Decimal("1300.00"), Decimal("2.00"), Decimal("216.67"))
# Semana del lunes 7 al domingo 13 de septiembre de 2026.
LUNES, SABADO, DOMINGO = date(2026, 9, 7), date(2026, 9, 12), date(2026, 9, 13)


def _naye(ultimo_pago=None):
    return HorarioEmpleada("VEND-6", modo_pago=MODO_POR_DIA, dias_trabajo=[5, 6], fecha_ultimo_pago=ultimo_pago)


class EstadoTests(unittest.TestCase):
    def test_trabaja_solo_sus_dias(self) -> None:
        h = _naye()
        self.assertEqual(estado_del_dia(h, LUNES), DESCANSO)
        self.assertEqual(estado_del_dia(h, SABADO), TRABAJO)
        self.assertEqual(estado_del_dia(h, DOMINGO), TRABAJO)

    def test_dia_extra_apuntado_cuenta_como_trabajo(self) -> None:
        h = _naye()
        h.eventos[date(2026, 9, 9)] = TRABAJO  # vino el miércoles
        self.assertEqual(estado_del_dia(h, date(2026, 9, 9)), TRABAJO)

    def test_configurado(self) -> None:
        self.assertTrue(_naye().configurado)
        self.assertFalse(HorarioEmpleada("X", modo_pago=MODO_POR_DIA).configurado)
        self.assertFalse(HorarioEmpleada("X").configurado)
        self.assertTrue(HorarioEmpleada("X", descanso_weekday=2).configurado)

    def test_no_aparece_como_descanso_entre_semana_para_el_encargado(self) -> None:
        # Un lunes no "descansa": simplemente no le toca. No se avisa.
        self.assertNotIn("VEND-6", quienes_descansan({"VEND-6": _naye()}, LUNES))
        self.assertIn("VEND-2", quienes_descansan({"VEND-2": HorarioEmpleada("VEND-2", descanso_weekday=0)}, LUNES))


class ProximoPagoTests(unittest.TestCase):
    def test_cobra_al_terminar_sus_dias(self) -> None:
        # Le pagaron el domingo pasado: el próximo es el domingo 13.
        self.assertEqual(fecha_proximo_pago(_naye(date(2026, 9, 6)), LUNES), DOMINGO)
        # Sin pago previo: el primer domingo desde hoy.
        self.assertEqual(fecha_proximo_pago(_naye(), date(2026, 9, 10)), DOMINGO)
        self.assertEqual(fecha_proximo_pago(_naye(), DOMINGO), DOMINGO)

    def test_atrasado_se_sigue_mostrando(self) -> None:
        self.assertEqual(fecha_proximo_pago(_naye(date(2026, 9, 6)), date(2026, 9, 16)), DOMINGO)

    def test_sin_dias_no_hay_fecha(self) -> None:
        self.assertIsNone(fecha_proximo_pago(HorarioEmpleada("X", modo_pago=MODO_POR_DIA), LUNES))


class PagoPorDiaTests(unittest.TestCase):
    def test_dos_dias_mas_comisiones(self) -> None:
        d = calcular_pago(_naye(date(2026, 9, 6)), comisiones=9, params=PARAMS, hasta=DOMINGO)
        self.assertTrue(d.por_dia)
        self.assertEqual(d.dias_trabajados, 2)
        self.assertEqual(d.tarifa_dia, Decimal("216.67"))
        self.assertEqual(d.sueldo_base, Decimal("433.34"))
        self.assertEqual(d.monto_comisiones, Decimal("18.00"))
        self.assertEqual(d.faltas, 0)
        self.assertEqual(d.total, Decimal("451.34"))

    def test_semana_completa_cuando_ayuda_toda_la_semana(self) -> None:
        h = _naye(date(2026, 9, 6))
        for dia in (7, 8, 9, 10, 11):
            h.eventos[date(2026, 9, dia)] = TRABAJO
        d = calcular_pago(h, comisiones=0, params=PARAMS, hasta=DOMINGO)
        self.assertEqual(d.dias_trabajados, 7)
        self.assertEqual(d.sueldo_base, Decimal("1516.69"))

    def test_dia_que_no_vino_no_se_paga_ni_se_descuenta(self) -> None:
        h = _naye(date(2026, 9, 6))
        h.eventos[SABADO] = FALTA
        d = calcular_pago(h, comisiones=0, params=PARAMS, hasta=DOMINGO)
        self.assertEqual(d.dias_trabajados, 1)
        self.assertEqual(d.total, Decimal("216.67"))
        self.assertEqual(d.descuento_faltas, Decimal("0.00"))

    def test_semana_normal_no_cambia(self) -> None:
        h = HorarioEmpleada("VEND-2", descanso_weekday=6, fecha_ultimo_pago=date(2026, 9, 6))
        d = calcular_pago(h, comisiones=10, params=PARAMS, hasta=DOMINGO)
        self.assertFalse(d.por_dia)
        self.assertEqual(d.total, Decimal("1320.00"))


if __name__ == "__main__":
    unittest.main()
