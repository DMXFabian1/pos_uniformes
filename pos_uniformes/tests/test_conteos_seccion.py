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
        self.assertIn("_conteos_empezar", cuerpo)       # abre una jornada
        self.assertIn("conteos_jornadas_box", cuerpo)   # y lista las abiertas
        self.assertIn("conteos_revisar_box", cuerpo)    # y lo que el dueño revisa
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


class GafeteEnConteosTests(unittest.TestCase):
    """Paso 2: sin gafete no se cuenta, y cada conteo lleva nombre.

    Antes `contado_por` quedaba fijo en "admin (satélite)" y no había forma
    de saber quién contó qué.

    Se prueba sobre un doble, no sobre la ventana real: construir el satélite
    levanta un hilo de refresco contra la base y deja temporizadores de foco
    vivos que se metían en las pruebas de otros archivos. Es el mismo patrón
    de `test_kiosk_seccion_nav.py`.
    """

    def setUp(self) -> None:
        self._creados = []

    def tearDown(self) -> None:
        # Los widgets del doble son ventanas de nivel superior: si se quedan
        # vivas, se acumulan y le mueven el foco a las pruebas de otros
        # archivos (le pasó a `test_search_input_helper`).
        for widget in self._creados:
            widget.deleteLater()
        self._creados.clear()
        _APP.processEvents()

    def _stub(self, *, gafete_valido=True, nombre="Cristal Torres"):
        from types import SimpleNamespace

        from PyQt6.QtWidgets import QLabel, QLineEdit, QWidget

        w = SimpleNamespace()
        w._padre = QWidget()
        self._creados.append(w._padre)
        w.conteos_gate = QWidget(w._padre)
        w.conteos_work = QWidget(w._padre)
        w.conteos_gate_input = QLineEdit(w._padre)
        w.conteos_gate_error = QLabel(w._padre)
        w.conteos_quien_label = QLabel(w._padre)
        w.conteos_titulo_label = QLabel(w._padre)
        w.conteos_pendiente_label = QLabel(w._padre)
        w._conteos_code = None
        w._conteos_nombre = ""
        w.offline_mode = False
        w.estado = []
        w._set_status = lambda t: w.estado.append(t)
        w._gafete_libreta_valido = lambda c: gafete_valido
        w._nombre_de_gafete = lambda c: nombre
        w._refresh_conteos_pendiente = lambda: None
        w._refresh_conteos_vista = lambda: None
        w._refresh_conteo_banner = lambda: None
        for metodo in (
            "_on_conteos_gate_scan", "_conteos_logout",
            "_conteos_contado_por", "_open_conteo_subir",
        ):
            setattr(w, metodo, getattr(QuoteSatelliteWindow, metodo).__get__(w))
        w._conteos_logout()
        return w

    def test_la_pagina_abre_en_el_gafete(self) -> None:
        w = self._stub()
        self.assertTrue(w.conteos_gate.isVisibleTo(w._padre))
        self.assertFalse(w.conteos_work.isVisibleTo(w._padre))

    def test_un_gafete_bueno_abre_el_trabajo_y_deja_su_nombre(self) -> None:
        w = self._stub()
        w.conteos_gate_input.setText("VEND-4")
        w._on_conteos_gate_scan()

        self.assertFalse(w.conteos_gate.isVisibleTo(w._padre))
        self.assertTrue(w.conteos_work.isVisibleTo(w._padre))
        self.assertEqual(w._conteos_contado_por(), "Cristal Torres (VEND-4)")
        self.assertIn("Cristal Torres", w.conteos_titulo_label.text())   # "Hola, Cristal Torres 👋"

    def test_un_gafete_inventado_no_pasa(self) -> None:
        w = self._stub(gafete_valido=False)
        w.conteos_gate_input.setText("VEND-999")
        w._on_conteos_gate_scan()

        self.assertTrue(w.conteos_gate.isVisibleTo(w._padre))
        self.assertTrue(w.conteos_gate_error.isVisibleTo(w._padre))
        self.assertIn("VEND-999", w.conteos_gate_error.text())
        self.assertIsNone(w._conteos_contado_por())

    def test_sin_nombre_al_menos_queda_el_codigo(self) -> None:
        """Si la base no da el nombre, el conteo no puede quedar anónimo."""
        w = self._stub(nombre="")
        w.conteos_gate_input.setText("VEND-4")
        w._on_conteos_gate_scan()
        self.assertEqual(w._conteos_contado_por(), "VEND-4")

    def test_salir_cierra_la_sesion(self) -> None:
        w = self._stub()
        w.conteos_gate_input.setText("VEND-4")
        w._on_conteos_gate_scan()
        self.assertIsNotNone(w._conteos_contado_por())

        w._conteos_logout()
        self.assertIsNone(w._conteos_contado_por())
        self.assertTrue(w.conteos_gate.isVisibleTo(w._padre))

    def test_sin_gafete_no_se_abre_la_captura(self) -> None:
        from unittest.mock import patch

        w = self._stub()
        with patch(
            "pos_uniformes.ui.dialogs.conteo_subir_dialog.ConteoSubirDialog"
        ) as dialogo:
            w._open_conteo_subir()
        dialogo.assert_not_called()
        self.assertTrue(any("gafete" in t.lower() for t in w.estado))

    def test_con_gafete_la_captura_recibe_el_nombre(self) -> None:
        from unittest.mock import patch

        w = self._stub()
        w.conteos_gate_input.setText("VEND-4")
        w._on_conteos_gate_scan()
        with patch(
            "pos_uniformes.ui.dialogs.conteo_subir_dialog.ConteoSubirDialog"
        ) as dialogo:
            w._open_conteo_subir()
        self.assertEqual(
            dialogo.call_args.kwargs["contado_por"], "Cristal Torres (VEND-4)"
        )


if __name__ == "__main__":
    unittest.main()
