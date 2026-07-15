"""Navegación de secciones del kiosko con Ctrl+←/→.

Se prueba con un stub de los botones del sidebar (no se construye la ventana
completa, que necesita base de datos): los métodos solo dependen de los botones
de navegación y de `_set_page`.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

_BOTONES = (
    ("kiosk", "nav_kiosk_button"),
    ("quicksale", "nav_quicksale_button"),
    ("catalog", "nav_catalog_button"),
    ("guided", "nav_guided_button"),
    ("quote", "nav_quote_button"),
    ("search", "nav_search_button"),
    ("tariff", "nav_tariff_button"),
    ("conteos", "nav_conteos_button"),
)
# Las que hoy están ocultas en el sidebar real.
_OCULTAS = ("catalog", "quote", "search")


class SeccionNavTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _stub(self, ocultas=_OCULTAS):
        stub = SimpleNamespace()
        # Padre real: así isHidden() refleja solo el ocultamiento explícito.
        stub._padre = QWidget()
        for key, attr in _BOTONES:
            boton = QPushButton(stub._padre)
            if key in ocultas:
                boton.setVisible(False)
            setattr(stub, attr, boton)
        stub.current_page_key = "kiosk"
        stub._SECCIONES_NAV = QuoteSatelliteWindow._SECCIONES_NAV
        stub._set_page = lambda k: setattr(stub, "current_page_key", k)
        stub._secciones_visibles = lambda: QuoteSatelliteWindow._secciones_visibles(stub)
        stub._navegar_seccion = lambda d: QuoteSatelliteWindow._navegar_seccion(stub, d)
        return stub

    def test_secciones_visibles_saltan_las_ocultas(self) -> None:
        s = self._stub()
        self.assertEqual(
            s._secciones_visibles(), ["kiosk", "quicksale", "guided", "tariff", "conteos"]
        )

    def test_avanza_y_retrocede_saltando_ocultas(self) -> None:
        s = self._stub()
        s._navegar_seccion(1)
        self.assertEqual(s.current_page_key, "quicksale")
        s._navegar_seccion(1)  # se salta "catalog" (oculta)
        self.assertEqual(s.current_page_key, "guided")
        s._navegar_seccion(-1)
        self.assertEqual(s.current_page_key, "quicksale")

    def test_se_detiene_en_los_extremos(self) -> None:
        s = self._stub()
        s.current_page_key = "kiosk"
        s._navegar_seccion(-1)  # primera: no cicla
        self.assertEqual(s.current_page_key, "kiosk")
        s.current_page_key = "conteos"
        s._navegar_seccion(1)  # última: no cicla
        self.assertEqual(s.current_page_key, "conteos")

    def test_pagina_fuera_del_sidebar_va_a_la_primera(self) -> None:
        s = self._stub()
        s.current_page_key = "share"  # no está en el sidebar
        s._navegar_seccion(1)
        self.assertEqual(s.current_page_key, "kiosk")

    def test_si_se_muestra_catalogo_entra_a_la_navegacion(self) -> None:
        # Al desocultar una sección, se navega sola (no hay lista hardcodeada).
        s = self._stub(ocultas=("quote", "search"))
        self.assertIn("catalog", s._secciones_visibles())
        s.current_page_key = "quicksale"
        s._navegar_seccion(1)
        self.assertEqual(s.current_page_key, "catalog")


if __name__ == "__main__":
    unittest.main()
