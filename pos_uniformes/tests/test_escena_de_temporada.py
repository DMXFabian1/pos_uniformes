"""La escena de pantalla completa del kiosko en temporada.

Daniel la pidió el 07/10 mirando la pantalla de «Escanea tu QR»: «motivos de
halloween aquí, igual con degradado, a modo El extraño mundo de Jack». La
película es de Disney, así que la escena se dibuja original —noche, luna,
árboles pelones, cerca, calabazas—, que es el género y no la película.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.services import temporada_service as temp
from pos_uniformes.ui.helpers.escena_de_temporada import FondoDeTemporada


class LaEscenaExisteTests(unittest.TestCase):
    def test_halloween_tiene_escena(self) -> None:
        self.assertIsNotNone(temp.escena_de(temp.temporada_de_archivo("halloween")))

    def test_las_demas_temporadas_siguen_sin_escena(self) -> None:
        """Dibujar una escena es trabajo de ilustración, no de calendario.

        Si esto empieza a fallar es porque alguien agregó una escena nueva:
        bienvenida sea, pero que sea a propósito y no por copiar un archivo.
        """
        con_escena = [t.nombre for t in temp.TEMPORADAS if temp.escena_de(t)]
        self.assertEqual(con_escena, ["Halloween"])

    def test_sin_temporada_no_hay_escena(self) -> None:
        self.assertIsNone(temp.escena_de(None))

    def test_el_svg_se_puede_dibujar(self) -> None:
        """Un SVG mal cerrado se guarda igual y no se ve hasta abrir el kiosko."""
        from PyQt6.QtSvg import QSvgRenderer

        ruta = temp.escena_de(temp.temporada_de_archivo("halloween"))
        self.assertTrue(QSvgRenderer(str(ruta)).isValid())

    def test_el_generador_reproduce_el_mismo_archivo(self) -> None:
        """La escena del repositorio es la que sale del script, no una versión
        suelta que alguien editó a mano y ya nadie puede regenerar."""
        from pos_uniformes.scripts.generar_escena_halloween import construir

        ruta = temp.escena_de(temp.temporada_de_archivo("halloween"))
        self.assertEqual(ruta.read_text(encoding="utf-8"), construir())


class ElFondoDelKioskoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _fondo(self, ancho=1000, alto=700):
        w = FondoDeTemporada()
        w.setObjectName("gateRoot")
        w.setStyleSheet("QWidget#gateRoot { background: #fdf8f3; }")
        w.resize(ancho, alto)
        return w

    def test_en_halloween_se_pinta_la_escena(self) -> None:
        temp.guardar_ajuste(temp.FIJA, "halloween")
        w = self._fondo()
        self.assertTrue(w.tiene_escena)
        cielo = w.grab().toImage().pixelColor(500, 40)
        self.assertLess(cielo.red(), 90)       # noche, no el crema de siempre
        self.assertGreater(cielo.blue(), cielo.green())

    def test_fuera_de_temporada_queda_el_fondo_de_siempre(self) -> None:
        temp.guardar_ajuste(temp.APAGADA)
        w = self._fondo()
        self.assertFalse(w.tiene_escena)
        c = w.grab().toImage().pixelColor(500, 40)
        self.assertGreater(c.red(), 200)       # el crema del kiosko

    def test_la_escena_cubre_sin_deformar(self) -> None:
        """Estirarla ovalaría la luna; encogerla dejaría franjas de fondo.

        Se comprueba en una ventana muy ancha y en una muy angosta: en las dos
        la esquina de abajo tiene que ser suelo pintado, no fondo del kiosko.
        """
        temp.guardar_ajuste(temp.FIJA, "halloween")
        for ancho, alto in ((1800, 500), (520, 900)):
            with self.subTest(ancho=ancho, alto=alto):
                img = self._fondo(ancho, alto).grab().toImage()
                for x in (3, ancho - 4):
                    c = img.pixelColor(x, alto - 3)
                    self.assertLess(c.red(), 90, f"x={x}")

    def test_la_cerca_y_las_calabazas_nunca_se_recortan(self) -> None:
        """Se ancla abajo: lo que sobra es cielo, y el cielo es lo que se va."""
        from pathlib import Path

        codigo = Path(
            __file__
        ).resolve().parents[1].joinpath(
            "ui/helpers/escena_de_temporada.py"
        ).read_text(encoding="utf-8")
        self.assertIn("h - eh", codigo)

    def test_releer_cambia_el_fondo_sin_reiniciar(self) -> None:
        temp.guardar_ajuste(temp.APAGADA)
        w = self._fondo()
        self.assertFalse(w.tiene_escena)
        temp.guardar_ajuste(temp.FIJA, "halloween")
        w.releer_temporada()
        self.assertTrue(w.tiene_escena)


class ElKioskoUsaLaEscenaTests(unittest.TestCase):
    def test_la_pantalla_de_escaneo_usa_el_fondo_de_temporada(self) -> None:
        from pathlib import Path

        codigo = Path(
            __file__
        ).resolve().parents[1].joinpath(
            "ui/views/quick_sale_view.py"
        ).read_text(encoding="utf-8")
        self.assertIn("wrapper = FondoDeTemporada()", codigo)
        # Con una calabaza del tamaño de la pantalla, el emoji suelto sobra.
        self.assertIn("if not wrapper.tiene_escena:", codigo)


if __name__ == "__main__":
    unittest.main()


class ElTextoDeLaTarjetaSeTineTests(unittest.TestCase):
    """«la fuente del programa la puedes cambiar de color?» (Daniel, 07/10).

    Acordado: SOLO la tarjeta de escaneo. En las pantallas de venta se leen
    precios y tallas ocho horas al día, y el color de un adorno no tiene nada
    que hacer ahí.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _gate(self):
        from PyQt6.QtWidgets import QWidget

        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget.__new__(QuickSaleWidget)
        QWidget.__init__(w)
        return w._build_gate()

    def _color_de(self, gate, nombre):
        from PyQt6.QtWidgets import QLabel

        etiqueta = next(
            l for l in gate.findChildren(QLabel) if l.objectName() == nombre
        )
        etiqueta.ensurePolished()
        return etiqueta.palette().color(etiqueta.foregroundRole())

    def test_en_temporada_el_titulo_toma_el_color(self) -> None:
        from PyQt6.QtGui import QColor

        temp.guardar_ajuste(temp.FIJA, "halloween")
        esperado = QColor(temp.temporada_de_archivo("halloween").color)
        self.assertEqual(self._color_de(self._gate(), "gateTitle"), esperado)

    def test_fuera_de_temporada_el_titulo_se_queda_como_siempre(self) -> None:
        from PyQt6.QtGui import QColor

        from pos_uniformes.ui.views.quick_sale_view import _TEXT

        temp.guardar_ajuste(temp.APAGADA)
        self.assertEqual(self._color_de(self._gate(), "gateTitle"), QColor(_TEXT))

    def test_la_ayuda_no_va_del_mismo_color_que_el_titulo(self) -> None:
        """Tres renglones del mismo naranja se leen como un bloque.

        Si la ayuda iguala al título, deja de verse cuál manda. Va a medio
        camino: se nota la temporada y se conserva el orden.
        """
        temp.guardar_ajuste(temp.FIJA, "halloween")
        gate = self._gate()
        titulo = self._color_de(gate, "gateTitle")
        ayuda = self._color_de(gate, "gateHint")
        self.assertNotEqual(ayuda, titulo)

    def test_la_ayuda_se_tine_pero_sigue_mas_apagada(self) -> None:
        from PyQt6.QtGui import QColor

        from pos_uniformes.ui.views.quick_sale_view import _MUTED

        temp.guardar_ajuste(temp.FIJA, "halloween")
        ayuda = self._color_de(self._gate(), "gateHint")
        self.assertNotEqual(ayuda, QColor(_MUTED))          # se tiñó
        titulo = QColor(temp.temporada_de_archivo("halloween").color)
        self.assertGreater(ayuda.blue(), titulo.blue())     # pero más apagada

    def test_mezclar_respeta_los_extremos(self) -> None:
        from pos_uniformes.ui.views.quick_sale_view import _mezclar

        self.assertEqual(_mezclar("#102030", "#a0b0c0", 0.0), "#102030")
        self.assertEqual(_mezclar("#102030", "#a0b0c0", 1.0), "#a0b0c0")

    def test_un_color_que_no_existe_no_tumba_la_pantalla(self) -> None:
        from pos_uniformes.ui.views.quick_sale_view import _mezclar

        self.assertEqual(_mezclar("#102030", "no-es-un-color", 0.5), "#102030")
