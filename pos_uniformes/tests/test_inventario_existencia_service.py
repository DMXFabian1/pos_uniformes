"""Reglas de existencia de la pestaña Inventario (una sola cuenta: el total)."""

from __future__ import annotations

import unittest

from pos_uniformes.services.inventario_existencia_service import (
    clasificar_existencia,
    texto_existencia,
    tono_existencia,
)


class ClasificarExistenciaTests(unittest.TestCase):
    def test_cero_es_agotado(self) -> None:
        self.assertEqual(clasificar_existencia(0), "agotado")
        self.assertEqual(texto_existencia(0), "0 Agotado")
        self.assertEqual(tono_existencia(0), "danger")

    def test_uno_a_tres_es_bajo(self) -> None:
        for stock in (1, 2, 3):
            self.assertEqual(clasificar_existencia(stock), "bajo")
            self.assertEqual(tono_existencia(stock), "warning")
        self.assertEqual(texto_existencia(2), "2 Bajo")

    def test_bajo_minimo_gana_a_bajo(self) -> None:
        self.assertEqual(clasificar_existencia(5, stock_minimo=6), "bajo_minimo")
        self.assertEqual(texto_existencia(5, stock_minimo=6), "5 Bajo mín")

    def test_cuatro_o_mas_es_ok(self) -> None:
        self.assertEqual(clasificar_existencia(4), "ok")
        self.assertEqual(texto_existencia(6), "6 OK")
        self.assertEqual(tono_existencia(6), "positive")

    def test_minimo_negativo_es_virtual(self) -> None:
        self.assertEqual(clasificar_existencia(0, stock_minimo=-1), "virtual")
        self.assertEqual(tono_existencia(0, stock_minimo=-1), "neutral")


if __name__ == "__main__":
    unittest.main()
