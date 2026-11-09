"""Los QMessageBox con la cara del programa (Daniel, 2026-11-07: «se ven muy
mal estéticamente»)."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox  # noqa: E402

from pos_uniformes.ui.helpers import avisos_bonitos as ab  # noqa: E402

_APP = QApplication.instance() or QApplication([])
_RAIZ = Path(__file__).resolve().parent.parent


class TextoTests(unittest.TestCase):
    def test_primer_parrafo_titulo_y_clave_valor_como_ficha(self):
        h = ab.texto_como_html("Se enviaron las etiquetas de SKU1.\n\nModo: Cuadrada\nPiezas: 28")
        self.assertIn("font-size:16px; font-weight:700", h)
        self.assertIn("<table", h)
        self.assertIn(">Modo</td>", h)
        self.assertIn(">Cuadrada</td>", h)

    def test_texto_normal_y_html_escapado(self):
        h = ab.texto_como_html("Ojo\n\nNo hay <nada> aquí.\nSegundo renglón")
        self.assertNotIn("<table", h)
        self.assertIn("&lt;nada&gt;", h)
        self.assertIn("<br>", h)

    def test_que_tipo_de_aviso(self):
        I = QMessageBox.Icon
        self.assertEqual(ab.tipo_de_aviso(I.Information, "", "Se enviaron a la impresora"), "listo")
        self.assertEqual(ab.tipo_de_aviso(I.Information, "Etiqueta enviada", "x"), "listo")
        self.assertEqual(ab.tipo_de_aviso(I.Information, "Ya está abierto", "Busca la ventana"), "info")
        self.assertEqual(ab.tipo_de_aviso(I.Warning, "", ""), "cuidado")
        self.assertEqual(ab.tipo_de_aviso(I.Critical, "", ""), "fallo")
        self.assertEqual(ab.tipo_de_aviso(I.Question, "", ""), "pregunta")
        self.assertIsNone(ab.tipo_de_aviso(I.NoIcon, "", ""))


class AvisoMostradoTests(unittest.TestCase):
    def setUp(self):
        self.filtro = ab.instalar(_APP)
        self.addCleanup(_APP.removeEventFilter, self.filtro)

    def _mostrar(self, texto, icono=QMessageBox.Icon.Information):
        caja = QMessageBox(icono, "Etiqueta enviada", texto, QMessageBox.StandardButton.Ok)
        caja.show()
        _APP.processEvents()
        self.addCleanup(caja.close)
        return caja

    def test_el_icono_ya_no_mide_320(self):
        """La hoja de estilos le ponía min-width: 320px a TODO QLabel del
        aviso, el ícono incluido: de ahí el hueco enorme."""
        caja = self._mostrar("Se enviaron las etiquetas.\n\nModo: Cuadrada")
        icono = caja.findChild(QLabel, "qt_msgboxex_icon_label")
        self.assertLess(icono.width(), 80)
        self.assertTrue(caja.textFormat() == __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.TextFormat.RichText)
        self.assertIn("<table", caja.text())

    def test_el_texto_cabe_en_la_ventana(self):
        caja = self._mostrar("Se enviaron a la impresora las etiquetas de SKU005650 con su escuela.\n\nModo: Cuadrada")
        etiqueta = caja.findChild(QLabel, "qt_msgbox_label")
        self.assertLessEqual(etiqueta.geometry().right(), caja.width())

    def test_un_texto_que_ya_es_html_no_se_toca(self):
        caja = self._mostrar("<b>Hola</b> mundo")
        self.assertEqual(caja.text(), "<b>Hola</b> mundo")

    def test_los_botones_no_quedan_cortados(self):
        """Prueba en tienda 2026-11-09: «rar (queda pendie…». La hoja de
        estilo de aquí agranda el relleno de los botones después de que la
        pantalla que abrió el aviso los midió."""
        caja = QMessageBox(QMessageBox.Icon.Warning, "Venta sin anotar", "El cliente YA PAGÓ.")
        for texto in ("Reintentar anotar", "Cerrar (queda pendiente)", "Entendido (queda pendiente)"):
            boton = caja.addButton(texto, QMessageBox.ButtonRole.AcceptRole)
            boton.ensurePolished()
            boton.setMinimumWidth(boton.sizeHint().width())  # lo que hace quick_sale_view
        caja.show()
        _APP.processEvents()
        self.addCleanup(caja.close)
        for boton in caja.buttons():
            with self.subTest(boton.text()):
                self.assertGreaterEqual(boton.width(), boton.sizeHint().width())

    def test_las_hojas_ya_no_ponen_min_width_a_todo_label(self):
        for rel in ("ui/styles/main_window_styles.py", "ui/styles/satellite_styles.py"):
            fuente = (_RAIZ / rel).read_text(encoding="utf-8")
            self.assertNotRegex(fuente, r"QMessageBox QLabel \{[^}]*min-width", rel)

    def test_se_instala_al_arrancar(self):
        for rel in ("main.py", "presupuestos_satelite_main.py"):
            self.assertIn("instalar_avisos(app)", (_RAIZ / rel).read_text(encoding="utf-8"), rel)


if __name__ == "__main__":
    unittest.main()
