"""El tema de temporada: misma interfaz, diferente ambientación.

Daniel (2026-10-10) pidió que la temporada vistiera la pantalla —paleta del
encabezado, acentos del menú, saludo— sin mover nada de lugar. Lo que se cuida
aquí es sobre todo lo que NO debe pasar: que fuera de temporada cambie un
pixel, que un botón de acción cambie de color, o que un tema desplace un campo.
"""

from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.services import temporada_service as temp
from pos_uniformes.ui.styles.satellite_styles import build_satellite_stylesheet

_HALLOWEEN = temp.temporada_de_archivo("halloween")
_MUERTOS = temp.temporada_de_archivo("dia_de_muertos")


class ElCatalogoDeTemasTests(unittest.TestCase):
    def test_fuera_de_temporada_el_tema_es_maximoda(self) -> None:
        with patch.object(temp, "actual", return_value=None):
            tema = temp.tema_activo()
        self.assertEqual(tema, temp.TEMA_MAXIMODA)
        self.assertEqual(tema.saludo, "Bienvenido a Maximoda")

    def test_con_los_adornos_apagados_no_saluda(self) -> None:
        temp.guardar_ajuste(temp.APAGADA)
        tema = temp.tema_activo()
        self.assertEqual(tema.color_barra, temp.TEMA_MAXIMODA.color_barra)
        self.assertEqual(tema.saludo, "")

    def test_cada_temporada_trae_su_paleta_y_su_mensaje(self) -> None:
        vistos = set()
        for t in temp.TEMPORADAS:
            with self.subTest(temporada=t.nombre):
                tema = temp.tema_de(t)
                self.assertEqual(tema.saludo, t.saludo)
                self.assertRegex(tema.color_barra, r"^#[0-9a-f]{6}$")
                self.assertRegex(tema.color_barra_claro, r"^#[0-9a-f]{6}$")
                self.assertRegex(tema.color_barra_oscuro, r"^#[0-9a-f]{6}$")
                # Identidad propia: dos temporadas no comparten barra.
                self.assertNotIn(tema.color_barra, vistos)
                vistos.add(tema.color_barra)

    def test_el_tema_de_hoy_es_el_de_la_temporada(self) -> None:
        with patch.object(temp, "actual", return_value=_HALLOWEEN):
            self.assertEqual(temp.tema_activo().nombre, "Halloween")

    def test_si_el_servicio_truena_hay_tema_igual(self) -> None:
        with patch.object(temp, "actual", side_effect=RuntimeError("boom")):
            self.assertEqual(temp.tema_activo(), temp.TEMA_MAXIMODA)


class LaFechaEligeElTemaTests(unittest.TestCase):
    def test_un_dia_cualquiera_no_hay_temporada(self) -> None:
        self.assertIsNone(temp.actual(date(2026, 3, 20)))

    def test_el_14_de_febrero_es_san_valentin(self) -> None:
        self.assertEqual(temp.actual(date(2026, 2, 14)).nombre, "San Valentín")

    def test_la_fecha_es_la_de_mexico(self) -> None:
        from zoneinfo import ZoneInfo
        from datetime import datetime

        esperado = datetime.now(ZoneInfo("America/Mexico_City")).date()
        self.assertEqual(temp.hoy_en_mexico(), esperado)

    def test_si_se_empalman_gana_la_prioridad(self) -> None:
        """Regreso a clases es la temporada de la tienda: si un año se empalma
        con una fiesta, el uniforme es lo que trae a la gente."""
        with patch.object(temp, "fechas_configuradas",
                          return_value={"independencia": {"desde": "09-01"}}):
            # 5 de septiembre: regreso a clases (hasta 09-10) e independencia
            # (movida al 09-01) coinciden.
            self.assertEqual(temp.actual(date(2026, 9, 5)).nombre, "Regreso a clases")

    def test_a_igual_prioridad_gana_la_primera_de_la_lista(self) -> None:
        with patch.object(temp, "fechas_configuradas", return_value={
            "halloween": {"hasta": "11-02", "prioridad": 1},
        }):
            # 1 de noviembre: Halloween alargado y Día de Muertos, ambos con 1.
            self.assertEqual(temp.actual(date(2026, 11, 1)).nombre, "Halloween")

    def test_las_fechas_configuradas_mueven_la_temporada(self) -> None:
        with patch.object(temp, "fechas_configuradas",
                          return_value={"halloween": {"desde": "10-01"}}):
            self.assertEqual(temp.actual(date(2026, 10, 5)).nombre, "Halloween")
        self.assertIsNone(temp.actual(date(2026, 10, 5)))

    def test_una_fecha_mal_escrita_no_se_guarda(self) -> None:
        with self.assertRaises(ValueError):
            temp.validar_fechas({"halloween": {"desde": "31-10"}})
        with self.assertRaises(ValueError):
            temp.validar_fechas({"pascua": {"desde": "04-01"}})

    def test_lo_guardado_se_lee_de_vuelta_sin_base(self) -> None:
        temp.guardar_fechas({"navidad": {"desde": "11/20", "prioridad": "3"}})
        self.assertEqual(
            temp.fechas_configuradas(), {"navidad": {"desde": "11-20", "prioridad": 3}}
        )
        navidad = next(t for t in temp.temporadas_vigentes() if t.nombre == "Navidad")
        self.assertEqual((navidad.desde, navidad.prioridad), ((11, 20), 3))


class LaHojaDeEstilosTests(unittest.TestCase):
    def test_sin_tema_la_hoja_es_la_de_siempre_pixel_por_pixel(self) -> None:
        self.assertEqual(build_satellite_stylesheet(), build_satellite_stylesheet(temp.TEMA_MAXIMODA))
        self.assertIn("stop:0 #6f331d, stop:0.55 #a84f2d, stop:1 #c96a35", build_satellite_stylesheet())

    def test_el_encabezado_toma_la_paleta_de_la_temporada(self) -> None:
        tema = temp.tema_de(_HALLOWEEN)
        hoja = build_satellite_stylesheet(tema)
        self.assertIn(f"stop:0 {tema.color_barra_oscuro}, stop:0.55 {tema.color_barra}, stop:1 {tema.color_barra_claro}", hoja)
        self.assertIn(f"QPushButton#navButton:checked {{\n    background: {tema.color_barra};", hoja)

    def test_los_botones_funcionales_no_cambian_de_color(self) -> None:
        """Un botón rojo que un día sale verde deja de decir «cuidado»."""
        base = build_satellite_stylesheet()
        for t in temp.TEMPORADAS:
            with self.subTest(temporada=t.nombre):
                hoja = build_satellite_stylesheet(temp.tema_de(t))
                for regla in (
                    "QPushButton#primaryButton {\n    background: #87492c;",
                    "QPushButton#dangerButton {\n    background: #b65246;",
                    "QPushButton:disabled {\n    background: #efe9de;",
                ):
                    self.assertIn(regla, base)
                    self.assertIn(regla, hoja)

    def test_la_hoja_sigue_siendo_valida_para_qt(self) -> None:
        from PyQt6.QtWidgets import QWidget

        # Guardada en la clase: una QApplication sin referencia se recoge y
        # Qt aborta el proceso entero.
        type(self)._app = QApplication.instance() or QApplication([])
        for t in temp.TEMPORADAS:
            with self.subTest(temporada=t.nombre):
                w = QWidget()
                w.setStyleSheet(build_satellite_stylesheet(temp.tema_de(t)))
                w.ensurePolished()


class LaVentanaSeVisteSinMoverseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self, temporada):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        with patch.object(temp, "actual", return_value=temporada):
            w = QuoteSatelliteWindow(user_id=1)
            w.resize(1360, 850)
            w.show()
            self.app.processEvents()
        return w

    def test_releer_temporada_cambia_la_hoja_de_la_ventana(self) -> None:
        w = self._ventana(None)
        try:
            hoja_antes = w.styleSheet()
            with patch.object(temp, "actual", return_value=_HALLOWEEN):
                w.releer_temporada()
            self.assertNotEqual(w.styleSheet(), hoja_antes)
            self.assertIn(temp.tema_de(_HALLOWEEN).color_barra, w.styleSheet())
            with patch.object(temp, "actual", return_value=None):
                w.releer_temporada()
            self.assertEqual(w.styleSheet(), hoja_antes)
        finally:
            w.close()

    def test_la_marca_del_menu_cambia_con_la_temporada(self) -> None:
        from PyQt6.QtWidgets import QLabel

        with patch.object(temp, "actual", return_value=_HALLOWEEN):
            marca = type(self)._marca()
        with patch.object(temp, "actual", return_value=_MUERTOS):
            marca.releer_temporada()
        textos = [x.text() for x in marca.findChildren(QLabel)]
        self.assertTrue(any(_MUERTOS.saludo in t for t in textos), textos)

    @staticmethod
    def _marca():
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        return QuoteSatelliteWindow._marca_de_temporada()

    def test_cambiar_de_tema_no_mueve_nada(self) -> None:
        """Antes y después con la misma ventana: solo cambian colores."""
        from PyQt6.QtWidgets import QLineEdit, QPushButton

        def geometrias(w):
            botones = {b.objectName() + b.text(): b.geometry().getRect()
                       for b in w.findChildren(QPushButton) if b.objectName() == "navButton"}
            entradas = {e.objectName(): e.geometry().getRect()
                        for e in w.findChildren(QLineEdit) if e.objectName() == "gateInput"}
            return botones, entradas, w.header_card.geometry().getRect()

        w = self._ventana(None)
        try:
            antes = geometrias(w)
            with patch.object(temp, "actual", return_value=_HALLOWEEN):
                w._repintar_si_cambio_la_temporada("Halloween")
                self.app.processEvents()
            despues = geometrias(w)
        finally:
            w.close()
        self.assertEqual(antes, despues)
        self.assertGreater(len(antes[0]), 3)


class ElGateSaludaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _gate(self):
        from unittest.mock import MagicMock

        from pos_uniformes.ui.helpers.pantalla_de_gafete import construir_gate
        from pos_uniformes.ui.views.quick_sale_view import _GATE_STYLE

        return construir_gate(
            emoji="📒", titulo="Libreta", ayuda="Escanea tu gafete",
            hoja=_GATE_STYLE, al_escanear=MagicMock(),
        ).raiz

    def _saludo(self, raiz):
        from PyQt6.QtWidgets import QLabel

        return next(l for l in raiz.findChildren(QLabel) if l.objectName() == "gateTemporada")

    def test_fuera_de_temporada_da_la_bienvenida_a_maximoda(self) -> None:
        temp.guardar_ajuste(temp.AUTO)
        with patch.object(temp, "actual", return_value=None):
            raiz = self._gate()
        saludo = self._saludo(raiz)
        self.assertFalse(saludo.isHidden())
        self.assertEqual(saludo.text(), "Bienvenido a Maximoda")

    def test_la_instruccion_de_escaneo_no_se_sustituye(self) -> None:
        from PyQt6.QtWidgets import QLabel

        for temporada in (None, _HALLOWEEN):
            with self.subTest(temporada=temporada and temporada.nombre):
                with patch.object(temp, "actual", return_value=temporada):
                    raiz = self._gate()
                textos = [l.text() for l in raiz.findChildren(QLabel)]
                self.assertIn("Escanea tu gafete", textos)
                self.assertIn("Libreta", textos)

    def test_el_saludo_cabe_en_un_renglon(self) -> None:
        """Un saludo que se parte mueve el campo de entrada hacia abajo."""
        for t in temp.TEMPORADAS:
            with self.subTest(temporada=t.nombre):
                with patch.object(temp, "actual", return_value=t):
                    raiz = self._gate()
                saludo = self._saludo(raiz)
                self.assertLessEqual(
                    saludo.fontMetrics().horizontalAdvance(saludo.text()), 320
                )


if __name__ == "__main__":
    unittest.main()


# ── Sección 14: control, ciclo de vida, mensajes, accesibilidad, bitácora ──


class PrevisualizarSinTocarLaTiendaTests(unittest.TestCase):
    def test_la_prueba_manda_sobre_el_ajuste_y_vence_sola(self) -> None:
        temp.guardar_ajuste(temp.APAGADA)
        self.assertIsNone(temp.actual())
        temp.forzar("navidad", horas=2)
        self.assertEqual(temp.actual().nombre, "Navidad")
        temp.forzar("navidad", horas=-1)      # ya vencida
        self.assertIsNone(temp.actual())

    def test_volver_a_lo_normal_quita_la_prueba(self) -> None:
        temp.guardar_ajuste(temp.AUTO)
        temp.forzar("navidad")
        self.assertTrue(temp.quitar_forzada())
        self.assertEqual(temp.actual(date(2026, 3, 20)), None)

    def test_la_prueba_ensena_un_borrador_pero_no_lo_archivado(self) -> None:
        temp.guardar_ajuste(temp.AUTO)
        with patch.object(temp, "fechas_configuradas", return_value={
            "navidad": {"estado": temp.BORRADOR}, "halloween": {"estado": temp.ARCHIVADO},
        }):
            temp.forzar("navidad")
            self.assertEqual(temp.actual().nombre, "Navidad")
            temp.forzar("halloween")
            self.assertIsNone(temp.actual())
        temp.quitar_forzada()


class CicloDeVidaTests(unittest.TestCase):
    def test_de_fabrica_todas_estan_aprobadas(self) -> None:
        for t in temp.TEMPORADAS:
            self.assertEqual(temp.estado_guardado(t), temp.APROBADO)

    def test_un_borrador_no_sale_al_publico(self) -> None:
        temp.guardar_ajuste(temp.AUTO)
        with patch.object(temp, "fechas_configuradas", return_value={"halloween": {"estado": temp.BORRADOR}}):
            self.assertIsNone(temp.actual(date(2026, 10, 25)))
            temp.guardar_ajuste(temp.FIJA, "halloween")
            self.assertIsNone(temp.actual(date(2026, 3, 1)))
        temp.guardar_ajuste(temp.AUTO)

    def test_programado_y_activo_se_deducen_de_la_fecha(self) -> None:
        temp.guardar_ajuste(temp.AUTO)
        self.assertEqual(temp.estado_de(_HALLOWEEN, date(2026, 10, 25)), temp.ACTIVO)
        self.assertEqual(temp.estado_de(_HALLOWEEN, date(2026, 3, 1)), temp.PROGRAMADO)
        with patch.object(temp, "fechas_configuradas", return_value={"halloween": {"estado": temp.EN_REVISION}}):
            self.assertEqual(temp.estado_de(_HALLOWEEN, date(2026, 10, 25)), temp.EN_REVISION)

    def test_un_estado_inventado_no_se_guarda(self) -> None:
        with self.assertRaises(ValueError):
            temp.validar_fechas({"navidad": {"estado": "publicado"}})


class MensajesCentralizadosTests(unittest.TestCase):
    def test_el_saludo_y_el_secundario_se_pueden_cambiar_sin_codigo(self) -> None:
        temp.guardar_fechas({"navidad": {"saludo": "¡Felices fiestas!", "secundario": "Gracias por su preferencia"}})
        navidad = temp.temporada_de_archivo("navidad")
        self.assertEqual(navidad.saludo, "¡Felices fiestas!")
        self.assertEqual(navidad.mensaje_secundario, "Gracias por su preferencia")
        self.assertEqual(temp.tema_de(navidad).secundario, "Gracias por su preferencia")

    def test_un_saludo_demasiado_largo_no_se_guarda(self) -> None:
        with self.assertRaises(ValueError):
            temp.validar_fechas({"navidad": {"saludo": "x" * 61}})

    def test_el_mensaje_alternativo_es_el_de_maximoda(self) -> None:
        with patch.object(temp, "actual", return_value=None):
            self.assertEqual(temp.tema_activo().saludo, "Bienvenido a Maximoda")

    def test_el_secundario_sale_en_el_pie_del_menu(self) -> None:
        from dataclasses import replace

        from PyQt6.QtWidgets import QLabel

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        QApplication.instance() or QApplication([])
        con_extra = replace(_HALLOWEEN, mensaje_secundario="Dulce o truco")
        with patch.object(temp, "actual", return_value=con_extra):
            marca = QuoteSatelliteWindow._marca_de_temporada()
        textos = [l.text() for l in marca.findChildren(QLabel)]
        self.assertIn("Dulce o truco", textos)


class ContrasteTests(unittest.TestCase):
    @staticmethod
    def _contraste(a: str, b: str) -> float:
        def lum(h):
            h = h.lstrip("#")
            r, g, b_ = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
            f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b_)
        la, lb = lum(a), lum(b)
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

    def test_el_texto_blanco_del_encabezado_se_lee_en_todas(self) -> None:
        for t in [None, *temp.TEMPORADAS]:
            tema = temp.tema_de(t)
            with self.subTest(tema=tema.nombre):
                self.assertGreaterEqual(self._contraste("#ffffff", tema.color_barra), 4.5)
                self.assertGreaterEqual(self._contraste("#ffffff", tema.color_barra_oscuro), 4.5)
                # El extremo claro lleva texto grande en negritas: 3:1.
                self.assertGreaterEqual(self._contraste("#ffffff", tema.color_barra_claro), 3.0)

    def test_el_titulo_del_gate_se_lee_sobre_la_tarjeta(self) -> None:
        for t in [None, *temp.TEMPORADAS]:
            tema = temp.tema_de(t)
            with self.subTest(tema=tema.nombre):
                self.assertGreaterEqual(self._contraste(tema.color, "#ffffff"), 3.0)


class LaDecoracionNoEstorbaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_sin_el_archivo_de_la_escena_el_kiosko_abre_con_el_crema(self) -> None:
        import tempfile
        from pathlib import Path

        from pos_uniformes.ui.helpers.escena_de_temporada import FondoDeTemporada

        with tempfile.TemporaryDirectory() as vacio, \
             patch.object(temp, "carpeta_escenas", lambda: Path(vacio)), \
             patch.object(temp, "actual", return_value=_HALLOWEEN):
            w = FondoDeTemporada()
            self.assertFalse(w.tiene_escena)
            w.resize(300, 200)
            w.grab()            # pinta sin tronar

    def test_el_fondo_no_roba_el_foco_ni_el_teclado(self) -> None:
        from PyQt6.QtCore import Qt
        from unittest.mock import MagicMock

        from pos_uniformes.ui.helpers.pantalla_de_gafete import construir_gate
        from pos_uniformes.ui.views.quick_sale_view import _GATE_STYLE

        with patch.object(temp, "actual", return_value=_HALLOWEEN):
            gate = construir_gate(emoji="📒", titulo="Libreta", ayuda="Escanea",
                                  hoja=_GATE_STYLE, al_escanear=MagicMock())
        self.assertEqual(gate.raiz.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertNotEqual(gate.entrada.focusPolicy(), Qt.FocusPolicy.NoFocus)

    def test_el_banner_de_desconexion_no_cambia_con_el_tema(self) -> None:
        """Los estados de error y desconexión se ven igual en octubre que en marzo."""
        from pathlib import Path

        codigo = Path(__file__).resolve().parents[1].joinpath(
            "ui/quote_satellite_window.py"
        ).read_text(encoding="utf-8")
        trozo = codigo[codigo.index("def _set_db_connectivity_banner"):][:2500]
        for color in ("#a84f2d", "#c96a35", "#6f331d"):
            self.assertNotIn(color, trozo)

    def test_no_hay_animaciones_en_la_decoracion(self) -> None:
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[1] / "ui" / "helpers"
        for nombre in ("escena_de_temporada.py", "barra_de_temporada.py", "pantalla_de_gafete.py"):
            codigo = (raiz / nombre).read_text(encoding="utf-8")
            self.assertNotIn("QPropertyAnimation", codigo)
            self.assertNotIn("QTimer", codigo)


class BitacoraTests(unittest.TestCase):
    def test_los_cambios_dejan_renglon(self) -> None:
        temp.guardar_ajuste(temp.FIJA, "halloween")
        temp.guardar_fechas({"navidad": {"desde": "11-20"}})
        temp.forzar("navidad")
        temp.quitar_forzada()
        eventos = [r["evento"] for r in temp.bitacora()]
        self.assertEqual(eventos[-4:], ["ajuste", "fechas", "prueba", "prueba_quitada"])
        self.assertTrue(all("cuando" in r for r in temp.bitacora()))

    def test_la_bitacora_se_recorta_sola(self) -> None:
        for i in range(temp.MAX_RENGLONES_BITACORA + 20):
            temp.anotar("x", i=i)
        self.assertEqual(len(temp.bitacora(10_000)), temp.MAX_RENGLONES_BITACORA)

    def test_anotar_nunca_truena(self) -> None:
        with patch.object(temp, "ruta_bitacora", side_effect=OSError("disco")):
            temp.anotar("x")


class GeometriaEnVariasResolucionesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_cambiar_de_tema_no_mueve_nada_en_tres_tamanos(self) -> None:
        from PyQt6.QtWidgets import QWidget

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        def geometrias(w):
            return {
                (x.objectName(), x.__class__.__name__): x.geometry().getRect()
                for x in w.findChildren(QWidget)
                if x.isVisible() and x.objectName() and "Temporada" not in x.objectName()
            }

        for ancho, alto in ((1680, 1050), (1280, 800), (1024, 700)):
            with self.subTest(ancho=ancho, alto=alto):
                with patch.object(temp, "actual", return_value=None):
                    w = QuoteSatelliteWindow(user_id=1)
                    w.resize(ancho, alto)
                    w.show()
                    self.app.processEvents()
                try:
                    # La primera re-aplicación de CUALQUIER hoja (aunque sea la
                    # misma) hace que Qt vuelva a pulir y asiente 2 px en el
                    # campo del kiosko; eso es Qt, no el tema. El «antes» se
                    # toma ya asentado, y de ahí en adelante nada se mueve.
                    w.setStyleSheet(w.styleSheet())
                    self.app.processEvents()
                    antes = geometrias(w)
                    for t in (_HALLOWEEN, _MUERTOS, None):
                        with patch.object(temp, "actual", return_value=t):
                            w._repintar_si_cambio_la_temporada(t.nombre if t else "")
                            self.app.processEvents()
                        self.assertEqual(geometrias(w), antes)
                    self.assertGreater(len(antes), 20)
                finally:
                    w.close()
