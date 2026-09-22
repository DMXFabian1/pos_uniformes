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
        self.assertIn("_conteos_imprimir_hoja", cuerpo)  # la hoja carta (HP)
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


class ConteoBannerTests(unittest.TestCase):
    """El banner de conteo vencido consulta la DB en un hilo, no en la UI."""

    def _stub(self):
        from unittest.mock import MagicMock

        w = QuoteSatelliteWindow.__new__(QuoteSatelliteWindow)
        w.conteo_banner = MagicMock()
        w.conteo_banner_label = MagicMock()
        w.offline_mode = False
        return w

    def test_la_consulta_va_en_hilo_y_solo_una_a_la_vez(self) -> None:
        from unittest.mock import patch

        w = self._stub()
        w._conteo_banner_running = True   # ya hay una en vuelo
        with patch("threading.Thread") as hilo:
            QuoteSatelliteWindow._refresh_conteo_banner(w)
        hilo.assert_not_called()
        w._conteo_banner_running = False
        with patch("threading.Thread") as hilo:
            QuoteSatelliteWindow._refresh_conteo_banner(w)
        hilo.assert_called_once()
        self.assertEqual(hilo.call_args.kwargs["name"], "conteo-banner")
        self.assertTrue(w._conteo_banner_running)

    def test_offline_esconde_el_banner_sin_hilo(self) -> None:
        from unittest.mock import patch

        w = self._stub()
        w.offline_mode = True
        with patch("threading.Thread") as hilo:
            QuoteSatelliteWindow._refresh_conteo_banner(w)
        hilo.assert_not_called()
        w.conteo_banner.setVisible.assert_called_with(False)

    def test_el_resultado_pinta_el_banner_en_la_ui(self) -> None:
        from types import SimpleNamespace

        w = self._stub()
        QuoteSatelliteWindow._on_conteo_banner_ready(w, None)          # no se pudo: se esconde
        w.conteo_banner.setVisible.assert_called_with(False)
        QuoteSatelliteWindow._on_conteo_banner_ready(w, [SimpleNamespace(escuela_nombre="Práxedis")])
        w.conteo_banner_label.setText.assert_called_with("⚠  Conteo pendiente: Práxedis")
        w.conteo_banner.setVisible.assert_called_with(True)
        QuoteSatelliteWindow._on_conteo_banner_ready(w, [SimpleNamespace(escuela_nombre="A"), SimpleNamespace(escuela_nombre="B")])
        w.conteo_banner_label.setText.assert_called_with("⚠  Conteo pendiente en 2 escuelas")


class RediseñoPorRolTests(unittest.TestCase):
    """La sección Conteos se acomoda a quién entró (Daniel, 2026-09-22:
    "el diseño abruma"). Se prueba con una ventana de mentiras: solo los
    widgets que toca la lógica."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self, code: str):
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        w = QWidget()
        self._vivo = w   # que no lo recoja el recolector a media prueba
        raiz = QVBoxLayout(w)
        fila = QHBoxLayout()
        cards = {}
        for key in ("por_contar", "por_revisar", "a_medias", "mias"):
            card = QFrame(); card.setObjectName("libretaCard")
            t, v, s = QLabel(key), QLabel("0"), QLabel("")
            fila.addWidget(card, 1)
            cards[key] = (card, t, v, s)
        cards_widget = QWidget(); cards_widget.setLayout(fila)
        raiz.addWidget(cards_widget)
        piezas = {}
        for nombre in ("conteos_revisar_titulo", "conteos_revisar_panel", "conteos_toca_titulo", "conteos_toca_panel"):
            widget = QLabel(nombre) if nombre.endswith("titulo") else QFrame()
            raiz.addWidget(widget)
            piezas[nombre] = widget
        fake = type("V", (), {})()
        fake._raiz = w
        fake._conteos_code = code
        fake._conteos_cards = cards
        fake.conteos_cards_row = fila
        fake.conteos_cards_widget = cards_widget
        fake.conteos_layout = raiz
        fake.conteos_calendario_btn = QPushButton()
        fake.conteos_mapa_abrir_btn = QPushButton(); fake.conteos_mapa_abrir_btn.setCheckable(True)
        fake.conteos_ver_tabla_btn = QPushButton(); fake.conteos_ver_tabla_btn.setCheckable(True)
        fake.conteos_mapa = QFrame()
        fake.conteos_mapa_titulo = QLabel()
        for nombre, widget in piezas.items():
            setattr(fake, nombre, widget)
        for metodo in ("_conteos_es_dueno", "_conteos_aplicar_rol", "_conteos_destacar_card", "_conteos_ordenar_secciones"):
            setattr(type(fake), metodo, getattr(QuoteSatelliteWindow, metodo))
        return fake, piezas

    def test_la_empleada_ve_lo_suyo_y_el_mapa_cerrado(self) -> None:
        v, piezas = self._ventana("VEND-4")
        v._raiz.show()
        v._conteos_aplicar_rol()
        self.assertFalse(v.conteos_cards_widget.isVisible())      # sin tarjetas de números
        self.assertFalse(v.conteos_calendario_btn.isVisible())    # el calendario es del dueño
        self.assertFalse(v.conteos_mapa.isVisible())              # el mapa, cerrado
        self.assertTrue(v.conteos_mapa_abrir_btn.isVisible())     # con su botón para abrirlo
        self.assertFalse(v.conteos_ver_tabla_btn.isVisible())
        self.assertEqual(v.conteos_mapa_titulo.text(), "CÓMO VA LA TIENDA")
        # y lo que le toca va antes que lo que espera revisión
        orden = [v.conteos_layout.indexOf(piezas[n]) for n in ("conteos_toca_titulo", "conteos_revisar_titulo")]
        self.assertLess(orden[0], orden[1])

    def test_el_dueno_ve_primero_lo_que_espera_su_revision(self) -> None:
        from pos_uniformes.services.conteo_jornada_service import DUENO_CODE
        v, piezas = self._ventana(DUENO_CODE)
        v._raiz.show()
        v._conteos_aplicar_rol()
        self.assertTrue(v.conteos_cards_widget.isVisible())
        self.assertTrue(v.conteos_mapa.isVisible())
        self.assertFalse(v._conteos_cards["mias"][0].isVisible())   # "mías" no le dice nada
        self.assertEqual(v.conteos_cards_row.indexOf(v._conteos_cards["por_revisar"][0]), 0)
        self.assertEqual(v._conteos_cards["por_revisar"][0].objectName(), "libretaCardDestacada")
        self.assertEqual(v._conteos_cards["por_contar"][0].objectName(), "libretaCard")
        orden = [v.conteos_layout.indexOf(piezas[n]) for n in ("conteos_revisar_titulo", "conteos_toca_titulo")]
        self.assertLess(orden[0], orden[1])

    def test_alternar_el_mapa_lo_muestra_y_lo_esconde(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow
        v, _p = self._ventana("VEND-4")
        v._raiz.show()
        v.conteos_mapa.recargar = lambda: None
        type(v)._conteos_alternar_mapa = QuoteSatelliteWindow._conteos_alternar_mapa
        v._conteos_aplicar_rol()
        v._conteos_alternar_mapa(True)
        self.assertTrue(v.conteos_mapa.isVisible())
        self.assertEqual(v.conteos_mapa_abrir_btn.text(), "Ocultar")
        v._conteos_alternar_mapa(False)
        self.assertFalse(v.conteos_mapa.isVisible())


class CargaEnHiloTests(unittest.TestCase):
    """La sección lee la base en un hilo: por Wi-Fi son ~2 s y antes
    congelaba la pantalla (2026-09-22)."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self):
        from PyQt6.QtWidgets import QLabel
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        v = type("V", (), {})()
        v._conteos_code = "VEND-4"
        v._conteos_cargando = False
        v.conteos_quien_label = QLabel()
        v.pintadas = []
        v._conteos_aplicar_rol = lambda: None
        v._conteos_pintar_toca = lambda filas: v.pintadas.append(("toca", list(filas)))
        v.conteos_mapa = None
        for metodo in ("_conteos_avisar_cargando", "_on_conteos_datos_listos"):
            setattr(type(v), metodo, getattr(QuoteSatelliteWindow, metodo))
        return v

    def test_mientras_carga_lo_dice_y_al_llegar_pinta(self) -> None:
        from unittest.mock import patch

        v = self._ventana()
        v._conteos_avisar_cargando(True)
        self.assertEqual(v.conteos_quien_label.text(), "actualizando…")
        with patch("pos_uniformes.ui.helpers.conteos_jornadas_helper.pintar_jornadas") as pintar:
            v._on_conteos_datos_listos({"code": "VEND-4", "toca": ["A", "B"], "recientes": [], "abiertas": [], "por_revisar": []})
        self.assertFalse(v._conteos_cargando)
        self.assertEqual(v.pintadas, [("toca", ["A", "B"])])
        self.assertEqual(pintar.call_count, 1)

    def test_si_cambio_de_persona_lo_que_llega_tarde_se_ignora(self) -> None:
        from unittest.mock import patch

        v = self._ventana()
        v._conteos_code = "VEND-9"      # ya entró otra
        with patch("pos_uniformes.ui.helpers.conteos_jornadas_helper.pintar_jornadas") as pintar:
            v._on_conteos_datos_listos({"code": "VEND-4", "toca": ["A"], "recientes": [], "abiertas": [], "por_revisar": []})
        pintar.assert_not_called()
        self.assertEqual(v.pintadas, [])
