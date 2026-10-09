"""La vista previa enseña lo que va a salir del papel.

Daniel, 2026-10-09: «la vista previa también hay que arreglarla, además,
recuerdo que teníamos un recuadro con el total». Las dos cosas eran ciertas y
ninguna era la que yo esperaba.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QTextEdit

from pos_uniformes.services import temporada_service as temp
from pos_uniformes.services.escpos_settings_cache_service import EscPosSettings
from pos_uniformes.ui.dialogs import printable_text_dialog as d


class ElRecuadroDelTotalTests(unittest.TestCase):
    """El total vive dentro del marco DOBLE y el buscador solo quitaba el
    sencillo: el recuadro del diálogo dejó de salir cuando el ticket cambió
    de marco, y nadie lo notó hasta que Daniel lo echó de menos."""

    def test_lo_encuentra_en_el_marco_doble(self) -> None:
        self.assertEqual(
            d.total_del_ticket("║ TOTAL A PAGAR:             $495.00 ║"),
            "$495.00",
        )

    def test_y_en_el_sencillo_de_siempre(self) -> None:
        self.assertEqual(
            d.total_del_ticket("│ TOTAL A PAGAR:             $309.00 │"),
            "$309.00",
        )

    def test_y_sin_marco(self) -> None:
        self.assertEqual(d.total_del_ticket("TOTAL: $617.00"), "$617.00")

    def test_el_subtotal_no_cuenta(self) -> None:
        texto = "│ Subtotal:  $495.00 │\n║ TOTAL A PAGAR:  $550.00 ║"
        self.assertEqual(d.total_del_ticket(texto), "$550.00")

    def test_un_documento_sin_total_no_inventa_uno(self) -> None:
        self.assertIsNone(d.total_del_ticket("Lista de precios\nPlayera $180"))


class LaPreviaSeParaceAlPapelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        temp.guardar_ajuste(temp.FIJA, "halloween")

    def _previa(self, texto, **ajustes):
        editor = QTextEdit()
        with patch(
            "pos_uniformes.services.escpos_settings_cache_service.load_escpos_settings",
            return_value=EscPosSettings(**ajustes),
        ):
            d.pintar_previa(editor, texto)
        return editor

    def _con_logo(self):
        from pos_uniformes.services.sale_ticket_text_service import (
            encabezado_de_ticket,
        )

        return "\n".join(encabezado_de_ticket("MAXIMODA") + ["Ticket de venta"])

    def test_con_escpos_la_previa_enseña_el_logo(self) -> None:
        """El papel lo imprime en puntos; la previa decía «MAXIMODA» escrito.
        Previa y papel diciendo cosas distintas es lo único que una previa no
        puede hacer."""
        html = self._previa(self._con_logo(), enabled=True).toHtml()
        self.assertIn("<img", html)

    def test_sin_escpos_la_previa_escribe_el_nombre(self) -> None:
        """Por el camino de Qt el papel lleva el nombre, no el logo."""
        editor = self._previa(self._con_logo(), enabled=False)
        self.assertNotIn("<img", editor.toHtml())
        self.assertIn("MAXIMODA", editor.toPlainText())

    def test_un_ticket_sin_dibujos_va_como_texto(self) -> None:
        editor = self._previa("Hola\nAdiós", enabled=True)
        self.assertNotIn("<img", editor.toHtml())
        self.assertEqual(editor.toPlainText().strip(), "Hola\nAdiós")

    def test_un_dibujo_que_falta_no_deja_el_marcador_crudo(self) -> None:
        texto = f"{temp.MARCADOR_INICIO}no_existe|MAXIMODA{temp.MARCADOR_FIN}"
        plano = self._previa(texto, enabled=True).toPlainText()
        self.assertNotIn("[[IMG:", plano)
        self.assertIn("MAXIMODA", plano)

    def test_la_previa_conserva_la_letra_monoespaciada(self) -> None:
        """Con letra proporcional los recuadros dejan de cuadrar y la previa
        deja de parecerse al papel.

        Se mira la fuente que QUEDÓ y no el CSS: Qt reescribe el HTML a su
        manera y «bold» se vuelve 700.

        Y se compara contra la que pide el sistema, no contra `fixedPitch`:
        en esta Mac la monoespaciada del sistema se llama «monospace», que no
        es una familia de verdad, y `QFontInfo` contesta que no es
        monoespaciada aunque el programa esté haciendo lo correcto. Lo que
        aquí se puede afirmar es que la previa usa la MISMA letra que usaría
        sin dibujos."""
        from PyQt6.QtGui import QFontDatabase, QTextCursor

        editor = self._previa(self._con_logo(), enabled=True)
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fuente = cursor.charFormat().font()
        esperada = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.assertEqual(fuente.family(), esperada.family())
        self.assertTrue(fuente.bold())

    def test_el_ticket_dibujado_sigue_mandando_una_sola_imagen(self) -> None:
        """Cuando la PC dibuja el ticket entero, la previa es ESA imagen."""
        html = self._previa(
            self._con_logo(), enabled=True, ticket_como_imagen=True
        ).toHtml()
        self.assertEqual(html.count("<img"), 1)


if __name__ == "__main__":
    unittest.main()
