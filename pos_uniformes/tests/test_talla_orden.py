"""Orden de tallas para conteo, incluyendo rangos de edad (0-2, 9-12, 13-18)."""

from __future__ import annotations

import unittest

from pos_uniformes.services.conteo_service import _talla_sort_key


class _V:
    def __init__(self, talla: str) -> None:
        self.talla = talla


def _orden(tallas: list[str]) -> list[str]:
    return [v.talla for v in sorted((_V(t) for t in tallas), key=_talla_sort_key)]


class TallaOrdenTests(unittest.TestCase):
    def test_rangos_numericos_por_primer_numero(self) -> None:
        # El bug: "13-18" salía antes de "9-12". Debe ir por el primer número.
        entrada = ["13-18", "0-2", "9-12", "6-8", "0-0", "3-5"]
        self.assertEqual(
            _orden(entrada), ["0-0", "0-2", "3-5", "6-8", "9-12", "13-18"]
        )

    def test_numericas_puras(self) -> None:
        self.assertEqual(_orden(["12", "2", "8", "10", "4", "6"]),
                         ["2", "4", "6", "8", "10", "12"])

    def test_letras_al_final_en_su_orden(self) -> None:
        self.assertEqual(_orden(["GD", "CH", "EXG", "MD"]), ["CH", "MD", "GD", "EXG"])

    def test_mezcla_rangos_y_letras(self) -> None:
        # Numéricos/rangos primero; letras y rangos con letra al final.
        entrada = ["CH-MD", "9-12", "13-18", "GD-EXG", "6-8"]
        self.assertEqual(
            _orden(entrada), ["6-8", "9-12", "13-18", "CH-MD", "GD-EXG"]
        )


if __name__ == "__main__":
    unittest.main()
