"""Orden natural de tallas (filtros, Bodega y tabla de Inventario)."""

from __future__ import annotations

import unittest

from pos_uniformes.services.talla_orden_service import clave_talla, es_talla_numerica


def _orden(tallas: list[str]) -> list[str]:
    return sorted(tallas, key=clave_talla)


class ClaveTallaTests(unittest.TestCase):
    def test_numeros_y_rangos_ascendentes(self) -> None:
        self.assertEqual(_orden(["10", "2", "9-12", "0-2", "16"]), ["0-2", "2", "9-12", "10", "16"])

    def test_letras_mexicanas_con_xch_antes_de_ch(self) -> None:
        self.assertEqual(
            _orden(["EXG", "CH", "GD", "XCH", "MD", "2XG", "CH-MD"]),
            ["XCH", "CH", "CH-MD", "MD", "GD", "EXG", "2XG"],
        )

    def test_letras_en_ingles_en_su_orden(self) -> None:
        self.assertEqual(_orden(["XS", "S", "M", "L", "XL"][::-1]), ["XS", "S", "M", "L", "XL"])
        self.assertEqual(_orden(["XXL", "L", "XS", "M", "S", "XL"]), ["XS", "S", "M", "L", "XL", "XXL"])

    def test_numeros_luego_letras_luego_uni_y_lo_raro_al_final(self) -> None:
        self.assertEqual(
            _orden(["UNI", "Rara", "CH", "XS", "12", "EXG", "XCH"]),
            ["12", "XCH", "CH", "EXG", "XS", "UNI", "Rara"],
        )

    def test_minusculas_y_espacios(self) -> None:
        self.assertEqual(clave_talla(" ch "), clave_talla("CH"))
        self.assertEqual(clave_talla(None), (2, ""))

    def test_es_talla_numerica(self) -> None:
        self.assertTrue(es_talla_numerica("10"))
        self.assertTrue(es_talla_numerica("9-12"))
        self.assertFalse(es_talla_numerica("CH"))


if __name__ == "__main__":
    unittest.main()
