"""Tests del alto de página dinámico para tickets/hojas de conteo.

Antes la página era fija de 600 mm y el driver cortaba a destiempo (hojas
largas se partían a la mitad). Ahora el alto de página = alto real del
contenido + un colchón para la cuchilla, así el corte cae justo al final.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.dialogs.printable_text_dialog import (
    TICKET_BOTTOM_FEED_MM,
    _ticket_page_height_mm,
)


class TicketDynamicPageHeightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_incluye_colchon_de_corte(self) -> None:
        # Incluso un ticket de una línea deja el avance para la cuchilla.
        alto = _ticket_page_height_mm("Una línea")
        self.assertGreaterEqual(alto, TICKET_BOTTOM_FEED_MM)

    def test_escala_con_el_contenido(self) -> None:
        corto = _ticket_page_height_mm("linea 1\nlinea 2\nlinea 3")
        largo = _ticket_page_height_mm("\n".join(f"linea {i}" for i in range(60)))
        self.assertGreater(largo, corto)
        # La diferencia refleja las ~57 líneas extra (no un tamaño fijo).
        self.assertGreater(largo - corto, 50)

    def test_no_es_el_fijo_de_600(self) -> None:
        # El bug viejo: 600 mm fijos. Un ticket normal debe ser mucho menor.
        alto = _ticket_page_height_mm("HOJA DE CONTEO\nCamisa\nTalla 14\nTalla 16")
        self.assertNotEqual(alto, 600.0)
        self.assertLess(alto, 200.0)


if __name__ == "__main__":
    unittest.main()
