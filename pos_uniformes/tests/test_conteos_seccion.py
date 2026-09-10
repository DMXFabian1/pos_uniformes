"""La sección Conteos: Calendario es para mirar, Conteos es donde se trabaja.

Paso 1 del plan (2026-09-10). Antes las dos cosas vivían en una sola página
llamada "Calendario", con los botones de trabajo escondidos en el encabezado.
"""

from __future__ import annotations

import unittest

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow  # noqa: E402

_APP = QApplication.instance() or QApplication([])


class SeccionesTests(unittest.TestCase):
    def test_las_dos_secciones_existen_y_van_en_ese_orden(self) -> None:
        secciones = QuoteSatelliteWindow._SECCIONES_NAV
        self.assertIn("calendario", secciones)
        self.assertIn("conteos", secciones)
        self.assertLess(secciones.index("calendario"), secciones.index("conteos"))

    def test_calendario_no_lleva_botones_de_trabajo(self) -> None:
        """Se ve qué toca; imprimir y capturar viven en Conteos."""
        import inspect

        cuerpo = inspect.getsource(QuoteSatelliteWindow._build_calendario_page)
        self.assertNotIn("_open_conteo_subir", cuerpo)
        self.assertNotIn("_open_conteo_orden", cuerpo)
        self.assertIn("ConteoCalendarioMesPanel", cuerpo)

    def test_conteos_recoge_el_trabajo(self) -> None:
        import inspect

        cuerpo = inspect.getsource(QuoteSatelliteWindow._build_conteos_page)
        self.assertIn("_open_conteo_orden", cuerpo)
        self.assertIn("_open_conteo_subir", cuerpo)
        # Y avisa que nada se aplica solo.
        self.assertIn("no cambia el inventario solo", cuerpo)


class CamarasTests(unittest.TestCase):
    def test_el_boton_de_camaras_queda_oculto(self) -> None:
        import inspect

        cuerpo = inspect.getsource(QuoteSatelliteWindow)
        self.assertIn("self.nav_camaras_button.setVisible(False)", cuerpo)

    def test_pero_el_visor_sigue_a_la_mano(self) -> None:
        """Ocultar el botón no puede dejar sin cámaras: queda Ctrl+Shift+C."""
        import inspect

        cuerpo = inspect.getsource(QuoteSatelliteWindow)
        self.assertIn('QKeySequence("Ctrl+Shift+C")', cuerpo)
        self.assertTrue(hasattr(QuoteSatelliteWindow, "_open_camera_wall"))


if __name__ == "__main__":
    unittest.main()
