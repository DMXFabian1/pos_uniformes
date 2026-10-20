"""El nombre a «Título» respeta códigos de proveedor y siglas (2026-10-20)."""

from __future__ import annotations

import unittest

from pos_uniformes.services.catalog_service import CatalogService as C


class TituloTests(unittest.TestCase):
    def test_lo_normal_va_a_titulo(self) -> None:
        self.assertEqual(C._title_case("playera deportiva de niño"), "Playera Deportiva de Niño")

    def test_un_codigo_de_proveedor_no_se_toca(self) -> None:
        # Antes «KY357H» salía «Ky357h» y había que corregirlo a mano.
        self.assertEqual(C._title_case("sudadera KY357H"), "Sudadera KY357H")
        self.assertEqual(C._title_case("pants 3pz azul"), "Pants 3pz Azul")

    def test_las_siglas_se_quedan(self) -> None:
        self.assertEqual(C._title_case("camisa CBTIS 148"), "Camisa CBTIS 148")
        self.assertEqual(C._title_case("pants deportivo SABES"), "Pants Deportivo SABES")

    def test_todo_en_mayusculas_no_son_siglas(self) -> None:
        self.assertEqual(C._title_case("PLAYERA DEPORTIVA"), "Playera Deportiva")


if __name__ == "__main__":
    unittest.main()
