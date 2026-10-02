"""El motivo de temporada en la pantalla, no en el ticket.

Daniel (02/10): *"que la app tuviera motivos, nada exagerado, pero sí algo
sutil"*. Lo que se cuida aquí es sobre todo lo que NO debe pasar: que no se
pinte la ventana entera, que no salga todo el año, y que un adorno no pueda
impedir que el kiosko abra.
"""

from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.services import temporada_service as temp
from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

_HALLOWEEN = next(t for t in temp.TEMPORADAS if t.nombre == "Halloween")


class LaMarcaDeTemporadaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_casi_todo_el_año_no_hay_nada(self) -> None:
        # Un adorno permanente deja de notarse, y entonces no adorna.
        with patch.object(temp, "actual", return_value=None):
            self.assertIsNone(QuoteSatelliteWindow._marca_de_temporada())

    def test_en_temporada_aparece(self) -> None:
        with patch.object(temp, "actual", return_value=_HALLOWEEN):
            marca = QuoteSatelliteWindow._marca_de_temporada()
        self.assertIsNotNone(marca)

    def test_trae_el_emoji_y_el_saludo(self) -> None:
        from PyQt6.QtWidgets import QLabel

        with patch.object(temp, "actual", return_value=_HALLOWEEN):
            marca = QuoteSatelliteWindow._marca_de_temporada()
        textos = [w.text() for w in marca.findChildren(QLabel)]
        self.assertTrue(any(_HALLOWEEN.emoji in t for t in textos), textos)
        self.assertTrue(any(_HALLOWEEN.saludo in t for t in textos), textos)

    def test_usa_el_color_de_la_temporada(self) -> None:
        from PyQt6.QtWidgets import QLabel

        with patch.object(temp, "actual", return_value=_HALLOWEEN):
            marca = QuoteSatelliteWindow._marca_de_temporada()
        hojas = [w.styleSheet() for w in marca.findChildren(QLabel)]
        self.assertTrue(any(_HALLOWEEN.color in h for h in hojas), hojas)

    def test_si_el_servicio_truena_el_kiosko_abre_igual(self) -> None:
        # Un adorno no puede impedir que se venda.
        with patch.object(temp, "actual", side_effect=RuntimeError("boom")):
            self.assertIsNone(QuoteSatelliteWindow._marca_de_temporada())

    def test_la_barra_lo_lleva_al_pie(self) -> None:
        # Al pie: donde se ve siempre y no estorba nunca.
        with patch.object(temp, "actual", return_value=_HALLOWEEN):
            w = QuoteSatelliteWindow(user_id=1)
            barra = w._build_sidebar()
        ultimo = barra.layout().itemAt(barra.layout().count() - 1).widget()
        from PyQt6.QtWidgets import QLabel

        textos = [x.text() for x in ultimo.findChildren(QLabel)]
        self.assertTrue(any(_HALLOWEEN.saludo in t for t in textos), textos)

    def test_sin_temporada_la_barra_queda_igual_que_siempre(self) -> None:
        # Ventanas distintas: llamar dos veces a _build_sidebar sobre la misma
        # reparenta los botones y Qt se lleva el layout de la primera.
        def cuantos(temporada) -> int:
            with patch.object(temp, "actual", return_value=temporada):
                self._viva = QuoteSatelliteWindow(user_id=1)   # referencia viva
                barra = self._viva._build_sidebar()
                return barra.layout().count()

        sin_temporada = cuantos(None)
        con_temporada = cuantos(_HALLOWEEN)
        self.assertEqual(con_temporada, sin_temporada + 1)


class NoSePintaLaVentanaEnteraTests(unittest.TestCase):
    """La pantalla es para vender; el adorno es un detalle, no un disfraz."""

    def test_el_motivo_vive_en_dos_lugares_y_no_mas(self) -> None:
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[1]
        ventana = (raiz / "ui" / "quote_satellite_window.py").read_text(encoding="utf-8")
        venta = (raiz / "ui" / "views" / "quick_sale_view.py").read_text(encoding="utf-8")
        # La barra del kiosko y la tarjeta del gate. Nada más.
        self.assertEqual(ventana.count("temporada_service import actual"), 1)
        self.assertEqual(venta.count("temporada_service import actual"), 1)

    def test_en_venta_rapida_solo_esta_en_el_gate(self) -> None:
        # Mientras se vende, la pantalla es para vender.
        from pathlib import Path

        venta = (
            Path(__file__).resolve().parents[1] / "ui" / "views" / "quick_sale_view.py"
        ).read_text(encoding="utf-8")
        trozo = venta[venta.index("_temporada_de_hoy()"):]
        self.assertIn("gateEmoji", trozo[:1500])


if __name__ == "__main__":
    unittest.main()
