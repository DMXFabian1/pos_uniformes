"""«Hoy» en la Libreta empieza en el último corte, no a medianoche.

El caso que lo pidió (Daniel, 2026-10-15): el 14 se hizo el corte a las 16:56,
después se vendieron $190 y $942, y el 15 no salían en «Hoy» aunque ese dinero
se entregaba el 15."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from pos_uniformes.services import libreta_service as lib

MX = timezone(timedelta(hours=-6))
CORTE_14 = datetime(2026, 10, 14, 16, 56, 3, tzinfo=MX)


def _op(dia, hora, minuto, monto):
    return SimpleNamespace(created_at=datetime(2026, 10, dia, hora, minuto, tzinfo=MX), monto_total=monto)


class DesdeElCorteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ops = [
            _op(14, 16, 50, 299),     # antes del corte: ya se entregó
            _op(14, 17, 16, 190),     # después del corte del 14
            _op(14, 18, 0, 942),
            _op(15, 10, 1, 149),      # el 15
        ]

    def test_lo_vendido_despues_del_corte_de_ayer_sale_hoy(self) -> None:
        montos = [o.monto_total for o in lib.desde_el_corte(self.ops, CORTE_14, date(2026, 10, 15))]
        self.assertEqual(montos, [190, 942, 149])

    def test_lo_de_antes_del_corte_ya_no_sale(self) -> None:
        montos = [o.monto_total for o in lib.desde_el_corte(self.ops, CORTE_14, date(2026, 10, 15))]
        self.assertNotIn(299, montos)

    def test_la_venta_del_mismo_instante_del_corte_es_del_corte_que_cerro(self) -> None:
        en_el_corte = SimpleNamespace(created_at=CORTE_14, monto_total=1)
        self.assertEqual(lib.desde_el_corte([en_el_corte], CORTE_14), [])

    def test_sin_ningun_corte_es_el_dia_de_calendario(self) -> None:
        montos = [o.monto_total for o in lib.desde_el_corte(self.ops, None, date(2026, 10, 15))]
        self.assertEqual(montos, [149])

    def test_si_el_corte_fue_hace_dias_sale_todo_lo_que_hay_por_entregar(self) -> None:
        viejo = datetime(2026, 10, 12, 17, 36, tzinfo=MX)
        self.assertEqual(len(lib.desde_el_corte(self.ops, viejo, date(2026, 10, 15))), 4)

    def test_funciona_con_la_hora_en_otra_zona(self) -> None:
        # La base devuelve las horas en UTC; el corte, en hora local.
        utc = SimpleNamespace(created_at=datetime(2026, 10, 14, 23, 16, tzinfo=timezone.utc), monto_total=190)
        self.assertEqual(lib.desde_el_corte([utc], CORTE_14), [utc])     # 17:16 en México


class EtiquetaTests(unittest.TestCase):
    def test_se_dice_desde_cuando(self) -> None:
        self.assertEqual(
            lib.etiqueta_desde_el_corte(CORTE_14.astimezone(), date(2026, 10, 15)),
            f"desde el corte de ayer a las {CORTE_14.astimezone():%H:%M}",
        )

    def test_corte_de_hoy_y_corte_viejo(self) -> None:
        hoy = datetime(2026, 10, 15, 17, 0, tzinfo=MX).astimezone()
        self.assertTrue(lib.etiqueta_desde_el_corte(hoy, hoy.date()).startswith("desde el corte de hoy"))
        viejo = datetime(2026, 10, 12, 17, 36, tzinfo=MX).astimezone()
        self.assertIn(f"del {viejo:%d/%m}", lib.etiqueta_desde_el_corte(viejo, date(2026, 10, 15)))

    def test_sin_corte_dice_hoy(self) -> None:
        self.assertEqual(lib.etiqueta_desde_el_corte(None), "hoy")


if __name__ == "__main__":
    unittest.main()
