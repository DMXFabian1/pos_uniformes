"""La barra del kiosko se adorna sola según la temporada.

Daniel la pidió el 07/10: «¿puedes hacer que en esta barra haya calabazas?».

Los tests miran los PÍXELES y no los atributos. Es a propósito: un adorno que
se dibuja al fondo puede estar perfectamente configurado y no verse —o verse
tanto que tape el texto—, y eso un `assertTrue(widget.temporada)` no lo nota.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.services import temporada_service as temp
from pos_uniformes.ui.helpers import barra_de_temporada as bt


def _tinta(imagen) -> int:
    """Cuántos píxeles distintos tiene contra la misma barra sin adorno."""
    return sum(
        imagen.pixel(x, y)
        for y in range(0, imagen.height(), 3)
        for x in range(0, imagen.width(), 3)
    )


class LaBarraSeAdornaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _barra(self):
        from pos_uniformes.ui.styles.satellite_styles import (
            build_satellite_stylesheet,
        )

        c = bt.TarjetaConTemporada()
        c.setObjectName("satHeaderCard")
        c.setStyleSheet(build_satellite_stylesheet())
        c.resize(900, 96)
        return c

    def test_en_temporada_la_barra_cambia_de_verdad(self) -> None:
        temp.guardar_ajuste(temp.APAGADA)
        lisa = self._barra().grab().toImage()
        temp.guardar_ajuste(temp.FIJA, "halloween")
        con_calabazas = self._barra().grab().toImage()
        self.assertNotEqual(_tinta(lisa), _tinta(con_calabazas))

    def test_fuera_de_temporada_la_barra_sale_lisa(self) -> None:
        """Casi todo el año no hay nada, y eso es parte del diseño."""
        temp.guardar_ajuste(temp.APAGADA)
        a = self._barra().grab().toImage()
        b = self._barra().grab().toImage()
        self.assertEqual(_tinta(a), _tinta(b))

    def test_el_degradado_sigue_viendose_debajo_del_adorno(self) -> None:
        """El motivo va al fondo, no encima del fondo.

        Primero escribí este test contra el `drawPrimitive` del paintEvent, y
        pasaba igual quitándolo: medido el 07/10, un QFrame pinta su fondo de
        QSS aunque no se lo pidan, así que no probaba nada. Lo que sí se puede
        romper es que el adorno quede opaco y aplane el degradado, y eso es lo
        que se mide aquí: izquierda oscura, derecha clara.
        """
        temp.guardar_ajuste(temp.FIJA, "halloween")
        img = self._barra().grab().toImage()
        izq, der = img.pixelColor(4, 48), img.pixelColor(880, 48)
        self.assertGreater(der.red(), izq.red() + 20)

    def test_el_adorno_no_tapa_el_texto(self) -> None:
        """A plena opacidad la barra se vuelve ilegible: va al fondo, tenue."""
        self.assertLessEqual(bt.OPACIDAD, 0.3)

    def test_una_temporada_que_truena_no_borra_el_encabezado(self) -> None:
        """Es la barra de la aplicación: no puede dejar de dibujarse."""
        temp.guardar_ajuste(temp.FIJA, "halloween")
        barra = self._barra()
        with patch.object(
            bt.TarjetaConTemporada, "_pintar_motivo", side_effect=RuntimeError("boom")
        ):
            img = barra.grab().toImage()
        medio = img.pixelColor(450, 48)
        self.assertGreater(medio.red(), medio.blue() + 20)   # café, no gris

    def test_releer_cambia_la_barra_sin_reiniciar(self) -> None:
        """Es lo que hace útil el menú: se elige y se ve."""
        temp.guardar_ajuste(temp.APAGADA)
        barra = self._barra()
        antes = barra.grab().toImage()
        temp.guardar_ajuste(temp.FIJA, "navidad")
        barra.releer_temporada()
        self.assertNotEqual(_tinta(antes), _tinta(barra.grab().toImage()))


class ElKioskoUsaEstaBarraTests(unittest.TestCase):
    def test_el_encabezado_del_kiosko_es_la_tarjeta_con_temporada(self) -> None:
        from pathlib import Path

        codigo = Path(
            __file__
        ).resolve().parents[1].joinpath("ui/quote_satellite_window.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("header_card = TarjetaConTemporada()", codigo)
        self.assertIn("self.header_card = header_card", codigo)


if __name__ == "__main__":
    unittest.main()


class GuardarRepintaSinCerrarElProgramaTests(unittest.TestCase):
    """«cuando selecciono una temporada y le doy guardar tengo que cerrar el
    programa para que se vean los cambios» (Daniel, 2026-10-08).

    El menú buscaba los adornos en `dialog.window()`, y un diálogo YA es una
    ventana: devolvía el propio menú, donde no hay ningún adorno. Esto se
    prueba con una ventana de verdad y un diálogo hijo, que es el único modo
    de que el error aparezca — con un widget suelto el bug no se nota.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_se_repinta_lo_de_la_ventana_principal(self) -> None:
        from PyQt6.QtWidgets import QDialog, QMainWindow

        from pos_uniformes.ui.dialogs.satellite_admin_dialog import _repintar_adornos

        temp.guardar_ajuste(temp.APAGADA)
        ventana = QMainWindow()
        barra = bt.TarjetaConTemporada(ventana)
        ventana.setCentralWidget(barra)
        dialogo = QDialog(ventana)
        self.addCleanup(ventana.deleteLater)

        temp.guardar_ajuste(temp.FIJA, "halloween")
        _repintar_adornos(dialogo)
        self.assertIsNotNone(barra._temporada)

    def test_sin_padre_tampoco_truena(self) -> None:
        from PyQt6.QtWidgets import QDialog

        from pos_uniformes.ui.dialogs.satellite_admin_dialog import _repintar_adornos

        _repintar_adornos(QDialog())   # no debe lanzar
