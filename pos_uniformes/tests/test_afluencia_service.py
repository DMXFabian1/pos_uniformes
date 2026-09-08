"""Afluencia vs ventas por hora: combinación pura y conversión."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from pos_uniformes.services.afluencia_service import FilaAfluencia, combinar, totales


def _af(camara, hora, entradas=0, salidas=0, pasan=0):
    return SimpleNamespace(camara=camara, hora=hora, entradas=entradas, salidas=salidas, pasan=pasan)


class CombinarTests(unittest.TestCase):
    def test_suma_camaras_y_pega_ventas(self) -> None:
        h12 = datetime(2026, 9, 8, 12)
        h13 = datetime(2026, 9, 8, 13)
        filas = combinar(
            [
                _af("ENTRADA1.1", h12, entradas=4, salidas=3),
                _af("ENTRADA2.2", h12, entradas=6, salidas=5),
                _af("ENTRADA1", h12, pasan=40),
                _af("ENTRADA1.1", h13, entradas=2),
            ],
            {h12: 3, h13: 0},
        )
        self.assertEqual([(f.hora, f.entradas, f.salidas, f.pasan, f.ventas) for f in filas], [
            (h12, 10, 8, 40, 3),
            (h13, 2, 0, 0, 0),
        ])
        self.assertEqual(filas[0].conversion, 30.0)
        self.assertEqual(filas[1].conversion, 0.0)

    def test_hora_utc_se_convierte_a_local(self) -> None:
        utc = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)
        filas = combinar([_af("X", utc, entradas=1)], {})
        esperado = utc.astimezone().replace(tzinfo=None)
        self.assertEqual(filas[0].hora, esperado)
        self.assertIsNone(filas[0].hora.tzinfo)

    def test_ventas_sin_afluencia_aparecen_con_conversion_none(self) -> None:
        h = datetime(2026, 9, 8, 9)
        filas = combinar([], {h: 2})
        self.assertEqual(filas[0].ventas, 2)
        self.assertEqual(filas[0].entradas, 0)
        self.assertIsNone(filas[0].conversion)

    def test_totales(self) -> None:
        filas = [
            FilaAfluencia(datetime(2026, 9, 8, 12), 10, 8, 40, 3),
            FilaAfluencia(datetime(2026, 9, 8, 13), 5, 5, 10, 1),
        ]
        t = totales(filas)
        self.assertEqual((t.entradas, t.pasan, t.ventas), (15, 50, 4))
        self.assertEqual(t.conversion, 26.7)
        self.assertIsNone(totales([]))


if __name__ == "__main__":
    unittest.main()
