"""Test del helper de paginación de escuelas del flujo guiado."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.ui.quote_satellite_window import _GUIDED_SCHOOLS_PER_PAGE, _paginate


class PaginateTests(unittest.TestCase):
    def test_lista_vacia(self) -> None:
        page_items, page, total = _paginate([], 0, 9)
        self.assertEqual(page_items, [])
        self.assertEqual(page, 0)
        self.assertEqual(total, 1)

    def test_una_pagina_exacta(self) -> None:
        items = list(range(9))
        page_items, page, total = _paginate(items, 0, 9)
        self.assertEqual(page_items, items)
        self.assertEqual(total, 1)

    def test_varias_paginas(self) -> None:
        items = list(range(20))  # 20 -> 3 páginas de 9
        p0, page, total = _paginate(items, 0, 9)
        self.assertEqual((page, total), (0, 3))
        self.assertEqual(p0, list(range(9)))
        p2, page, total = _paginate(items, 2, 9)
        self.assertEqual((page, total), (2, 3))
        self.assertEqual(p2, [18, 19])  # última página, resto

    def test_pagina_fuera_de_rango_se_acota(self) -> None:
        items = list(range(10))  # 2 páginas
        page_items, page, total = _paginate(items, 99, 9)
        self.assertEqual(page, 1)  # acotada a la última
        self.assertEqual(total, 2)
        self.assertEqual(page_items, [9])

    def test_pagina_negativa_se_acota_a_cero(self) -> None:
        items = list(range(10))
        _items, page, _total = _paginate(items, -5, 9)
        self.assertEqual(page, 0)

    def test_constante_por_defecto(self) -> None:
        self.assertGreaterEqual(_GUIDED_SCHOOLS_PER_PAGE, 1)


if __name__ == "__main__":
    unittest.main()
