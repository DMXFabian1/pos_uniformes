"""Tipos de escocés como catálogo del programa (Daniel, 2026-11-07: «mejorar
la visualización y funciones dentro de tipos de escocés»)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from pos_uniformes.ui.dialogs import visor_escoces_dialog as ve  # noqa: E402

_APP = QApplication.instance() or QApplication([])


class DatosTests(unittest.TestCase):
    def setUp(self):
        self.telas = ve.cargar_telas()

    def test_vienen_las_37_con_su_foto(self):
        self.assertEqual(len(self.telas), 37)
        self.assertEqual(self.telas[0].codigo, "ESC-01")
        for t in self.telas:
            self.assertTrue(t.foto.is_file(), t.codigo)
            self.assertLess(t.foto.stat().st_size, 400_000, t.codigo)   # ligeras, no las de 3 MB

    def test_buscar_por_numero(self):
        for texto in ("12", "esc-12", "ESC 12", " 012 "):
            self.assertEqual([t.codigo for t in ve.filtrar(self.telas, texto)], ["ESC-12"], texto)

    def test_buscar_por_palabras_sin_acentos(self):
        self.assertTrue(all("verde" in f"{t.nombre} {t.familia}".lower() for t in ve.filtrar(self.telas, "VERDE")))
        stewart = [t.codigo for t in ve.filtrar(self.telas, "stewart")]
        self.assertIn("ESC-16", stewart)                       # Royal Stewart
        self.assertEqual(len(ve.filtrar(self.telas, "gales")), 3)
        self.assertEqual(ve.filtrar(self.telas, "tartan inexistente"), [])

    def test_familia_y_texto_juntos(self):
        rojos = ve.filtrar(self.telas, "", "Rojos")
        self.assertEqual(len(rojos), 8)
        self.assertTrue(all(t.familia == "Rojos" for t in ve.filtrar(self.telas, "marino", "Rojos")))

    def test_familias_en_orden_con_cuantas(self):
        fam = ve.familias(self.telas)
        self.assertEqual(fam[0], ("Marinos", 8))
        self.assertEqual(sum(n for _, n in fam), 37)


class VentanaTests(unittest.TestCase):
    def setUp(self):
        self.v = ve.VisorEscoces()
        self.addCleanup(self.v.close)

    def test_arranca_con_la_primera_elegida(self):
        self.assertEqual(self.v.rejilla.count(), 37)
        self.assertEqual(self.v.codigo.text(), "ESC-01")
        self.assertFalse(self.v.anterior.isEnabled())
        self.assertTrue(self.v.siguiente.isEnabled())

    def test_buscar_filtra_y_la_ficha_sigue(self):
        self.v.busca.setText("17")
        self.assertEqual(self.v.rejilla.count(), 1)
        self.assertEqual(self.v.codigo.text(), "ESC-17")
        self.assertEqual(self.v.tartan.text(), "Tartán: Black Watch")

    def test_sin_resultados_no_enseña_una_ficha_vieja(self):
        self.v.show()
        self.v.busca.setText("zzz")
        self.assertTrue(self.v.vacio.isVisible())
        self.assertFalse(self.v.ficha.isVisible())
        self.assertIn("zzz", self.v.vacio.text())

    def test_chip_de_familia(self):
        self.v.chips["Gales"].click()
        self.assertEqual(self.v.rejilla.count(), 3)
        self.assertTrue(self.v.chips["Gales"].isChecked())
        self.assertFalse(self.v.chips[""].isChecked())

    def test_siguiente_y_parecidas(self):
        self.v.siguiente.click()
        self.assertEqual(self.v.codigo.text(), "ESC-02")
        self.assertEqual(self.v.parecidas.count() - 1, 6)        # 6 marinos más (y el estirón)
        self.v.chips["Rojos"].click()
        self.v.ir_a("ESC-01")                                    # escondida por el chip: se quita el filtro
        self.assertEqual(self.v.codigo.text(), "ESC-01")
        self.assertTrue(self.v.chips[""].isChecked())

    def test_se_desliza_con_el_dedo(self):
        """Kiosko con pantalla táctil (Daniel, 2026-11-07)."""
        from PyQt6.QtWidgets import QScroller

        self.assertTrue(QScroller.hasScroller(self.v.rejilla.viewport()) or
                        QScroller.grabbedGesture(self.v.rejilla.viewport()) != 0)

    def test_botones_del_tamano_de_un_dedo(self):
        self.v.show()
        _APP.processEvents()
        for b in (self.v.anterior, self.v.siguiente, self.v.copiar, *self.v.chips.values()):
            self.assertGreaterEqual(b.height(), 40, b.text())

    def test_copiar_codigo(self):
        self.v.busca.setText("12")
        self.v.copiar_codigo()
        self.assertEqual(QApplication.clipboard().text(), "ESC-12")
        self.assertIn("copiado", self.v.copiar.text())

    def test_la_ficha_se_dibuja(self):
        from PyQt6.QtGui import QColor, QPainter, QPixmap

        px = QPixmap(300, 450)
        px.fill(QColor("white"))
        p = QPainter(px)
        self.v.pintar_ficha(p, 300, 450)
        p.end()
        img = px.toImage()
        self.assertNotEqual(img.pixelColor(150, 200).name(), "#ffffff")   # la muestra está


class AtajoTests(unittest.TestCase):
    def test_el_atajo_abre_el_catalogo_y_no_el_pdf(self):
        from pos_uniformes.ui.helpers import abrir_consultas as ac

        with patch.object(ve, "mostrar_escoces") as escoces, \
                patch("pos_uniformes.ui.dialogs.visor_consulta_dialog.mostrar_pdf") as pdf:
            ac.abrir_tipos_escoces(None)
        escoces.assert_called_once()
        pdf.assert_not_called()

    def test_sin_catalogo_queda_el_pdf(self):
        from pos_uniformes.ui.helpers import abrir_consultas as ac

        with patch.object(ve, "hay_catalogo", return_value=False), \
                patch("pos_uniformes.ui.dialogs.visor_consulta_dialog.mostrar_pdf") as pdf:
            ac.abrir_tipos_escoces(None)
        pdf.assert_called_once()

    def test_entran_al_ejecutable(self):
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent / "packaging" / "windows"
        for spec in ("pos_uniformes_windows.spec", "presupuestos_satelite_windows.spec"):
            fuente = (raiz / spec).read_text(encoding="utf-8")
            self.assertIn("visor_escoces_dialog", fuente)
            self.assertIn("avisos_bonitos", fuente)


if __name__ == "__main__":
    unittest.main()
