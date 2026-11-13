"""Reglas de existencia de la pestaña Inventario (una sola cuenta: el total)."""

from __future__ import annotations

import unittest

from pos_uniformes.services.inventario_existencia_service import (
    clasificar_existencia,
    coincide_filtro_existencia,
    contar_existencias,
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

    def test_negativo_se_ve_en_rojo_con_texto_claro(self) -> None:
        self.assertEqual(clasificar_existencia(-2), "negativo")
        self.assertEqual(texto_existencia(-2), "\u22122 Negativo")
        self.assertEqual(tono_existencia(-2), "danger")

    def test_negativo_no_es_bajo_aunque_tenga_minimo(self) -> None:
        self.assertEqual(clasificar_existencia(-1, stock_minimo=5), "negativo")


def _fila(stock: int, minimo: int | None = None) -> dict[str, object]:
    return {"stock_actual": stock, "stock_minimo": minimo}


class ContarExistenciasTests(unittest.TestCase):
    def test_chips_separan_negativos_agotados_y_bajos(self) -> None:
        filas = [_fila(-2), _fila(-1), _fila(0), _fila(1), _fila(3), _fila(5, 8), _fila(9)]
        conteo = contar_existencias(filas)
        self.assertEqual(conteo.negativos, 2)
        self.assertEqual(conteo.agotados, 1)
        self.assertEqual(conteo.bajos, 3)  # 1, 3 y el 5 bajo mínimo


class FiltroExistenciaTests(unittest.TestCase):
    def _que_entra(self, filtro: str) -> list[int]:
        return [s for s in (-3, 0, 1, 3, 4, 10) if coincide_filtro_existencia(s, filtro)]

    def test_en_negativo(self) -> None:
        self.assertEqual(self._que_entra("negative"), [-3])

    def test_agotado_es_exactamente_cero(self) -> None:
        self.assertEqual(self._que_entra("zero"), [0])

    def test_bajo_es_uno_a_tres_sin_negativos(self) -> None:
        self.assertEqual(self._que_entra("low"), [1, 3])

    def test_disponible(self) -> None:
        self.assertEqual(self._que_entra("available"), [1, 3, 4, 10])

    def test_sin_filtro_entra_todo(self) -> None:
        self.assertEqual(self._que_entra(""), [-3, 0, 1, 3, 4, 10])

    def test_bajo_minimo_no_incluye_negativos(self) -> None:
        self.assertFalse(coincide_filtro_existencia(-1, "below_min", stock_minimo=5))
        self.assertTrue(coincide_filtro_existencia(0, "below_min", stock_minimo=5))
        self.assertTrue(coincide_filtro_existencia(6, "low", stock_minimo=8))

    def test_virtual_solo_en_disponible(self) -> None:
        self.assertTrue(coincide_filtro_existencia(0, "available", stock_minimo=-1))
        self.assertFalse(coincide_filtro_existencia(0, "zero", stock_minimo=-1))


if __name__ == "__main__":
    unittest.main()
