"""Precio sugerido leído de la base: el que más se repite por pieza, nivel y talla."""

from __future__ import annotations

import unittest
from decimal import Decimal

from sqlalchemy import create_engine

from pos_uniformes.services import precio_sugerido_service as ps
from tests._ayuda_mini_caja import MiniCaja


class PreciosDeLaBaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.caja = MiniCaja(create_engine("sqlite://"))
        self.s = self.caja.s

    def test_moda_por_talla_del_nivel(self) -> None:
        pieza = self.caja.pieza["Pants Suelto"].id
        conteos = ps.precios_de_la_base(self.s, pieza, self.caja.nivel["Primaria"].id)
        self.assertEqual(conteos["4"][Decimal("245")], 4)
        self.assertEqual(conteos["EXG"][Decimal("305")], 1)
        # La secundaria no se mezcla.
        self.assertNotIn(Decimal("265"), conteos.get("12", {}))

    def test_sugerir_con_la_base(self) -> None:
        pieza = self.caja.pieza["Pants Suelto"].id
        nivel = self.caja.nivel["Primaria"].id
        filas = ps.sugerir(self.s, pieza, nivel, ["4", "GD", "EXG"])
        self.assertEqual([(f.talla, f.precio, f.origen) for f in filas], [
            ("4", Decimal("245.00"), "como las demás"),
            ("GD", Decimal("295.00"), "como las demás"),
            ("EXG", Decimal("305.00"), "como las demás"),
        ])

    def test_sin_contar_la_escuela_que_lo_recibe(self) -> None:
        bj = self.caja.escuelas["Benito Juárez"]
        pieza = self.caja.pieza["Pants Suelto"].id
        conteos = ps.precios_de_la_base(self.s, pieza, self.caja.nivel["Primaria"].id, excluir_escuela_id=bj.id)
        self.assertNotIn("EXG", conteos)


if __name__ == "__main__":
    unittest.main()
