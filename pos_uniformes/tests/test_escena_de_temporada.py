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
        self.assertIn("from pos_uniformes.ui.helpers.pantalla_de_gafete import", codigo)
        # La pantalla de gafete ya no se arma aquí: es una sola para las tres.
        self.assertNotIn('setObjectName("gateCard")', codigo)


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
        from pos_uniformes.ui.views.quick_sale_view import mezclar_colores

        self.assertEqual(mezclar_colores("#102030", "#a0b0c0", 0.0), "#102030")
        self.assertEqual(mezclar_colores("#102030", "#a0b0c0", 1.0), "#a0b0c0")

    def test_un_color_que_no_existe_no_tumba_la_pantalla(self) -> None:
        from pos_uniformes.ui.views.quick_sale_view import mezclar_colores

        self.assertEqual(mezclar_colores("#102030", "no-es-un-color", 0.5), "#102030")


class LasTresPantallasDeGafeteSonLaMismaTests(unittest.TestCase):
    """«en libreta y conteos aplica lo mismo» (Daniel, 07/10).

    Eran tres copias calcadas a mano —la de Libreta lo decía: «réplica
    exacta»— y compartían solo la hoja de estilos. Teñir las tres arreglaba
    ese día y se volvía a romper al siguiente adorno, así que se quedó una
    sola pantalla. Estos tests son lo que impide que vuelvan a separarse.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        # En setUpClass NO: el ajuste se aísla por test, y lo que se guarde
        # antes del primero se escribe en otra carpeta y no lo ve nadie.
        temp.guardar_ajuste(temp.FIJA, "halloween")

    def _gates(self):
        """Las tres pantallas, construidas como las construye la aplicación."""
        from unittest.mock import MagicMock

        from PyQt6.QtWidgets import QWidget

        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        venta = QuickSaleWidget.__new__(QuickSaleWidget)
        QWidget.__init__(venta)
        hechas = {"Venta rapida": venta._build_gate()}

        from pos_uniformes.ui.helpers.pantalla_de_gafete import construir_gate
        from pos_uniformes.ui.views.quick_sale_view import _GATE_STYLE

        for titulo, ayuda in (("Libreta", "Escanea tu gafete para abrir tu libreta"),
                              ("Conteos", "Escanea tu gafete para contar")):
            hechas[titulo] = construir_gate(
                emoji="📒", titulo=titulo, ayuda=ayuda, hoja=_GATE_STYLE,
                al_escanear=MagicMock(),
            ).raiz
        return hechas

    def test_las_tres_pintan_la_escena(self) -> None:
        for nombre, gate in self._gates().items():
            with self.subTest(pantalla=nombre):
                self.assertTrue(gate.tiene_escena)

    def test_las_tres_tinen_su_titulo(self) -> None:
        from PyQt6.QtGui import QColor
        from PyQt6.QtWidgets import QLabel

        esperado = QColor(temp.temporada_de_archivo("halloween").color)
        for nombre, gate in self._gates().items():
            with self.subTest(pantalla=nombre):
                titulo = next(
                    l for l in gate.findChildren(QLabel)
                    if l.objectName() == "gateTitle"
                )
                titulo.ensurePolished()
                self.assertEqual(
                    titulo.palette().color(titulo.foregroundRole()), esperado
                )

    def test_ninguna_pagina_arma_su_propia_copia(self) -> None:
        """Lo que vuelve a separarlas es escribir `gateCard` a mano."""
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[1]
        for archivo in ("ui/quote_satellite_window.py", "ui/views/quick_sale_view.py"):
            with self.subTest(archivo=archivo):
                codigo = raiz.joinpath(archivo).read_text(encoding="utf-8")
                self.assertNotIn('setObjectName("gateCard")', codigo)

    def test_las_tres_conservan_sus_textos(self) -> None:
        """Compartir la pantalla no es volverlas iguales: cada una dice lo suyo."""
        from PyQt6.QtWidgets import QLabel

        titulos = set()
        for gate in self._gates().values():
            titulos.add(next(
                l.text() for l in gate.findChildren(QLabel)
                if l.objectName() == "gateTitle"
            ))
        self.assertEqual(titulos, {"Venta rapida", "Libreta", "Conteos"})


class LosDibujosDeDanielTests(unittest.TestCase):
    """«lo hice yo» (07/10): el murciélago y después la bruja.

    Los dibujos son suyos y entran tal cual. Lo único que se les hace es
    pasarlos de puntos a contorno: pegados como PNG se verían pixeleados en
    una pantalla grande, porque la escena se estira a la que toque.
    """

    def _carpeta(self):
        from pathlib import Path

        return Path(__file__).resolve().parents[1] / "assets" / "escenas"

    def test_los_dibujos_originales_se_quedan_en_el_repositorio(self) -> None:
        """Sin el PNG, el contorno es un montón de números sin origen.

        Guardarlos es lo que permite re-trazarlos si Daniel cambia un dibujo.
        """
        from pos_uniformes.scripts.trazar_silueta import SILUETAS

        for nombre in SILUETAS:
            with self.subTest(dibujo=nombre):
                self.assertTrue((self._carpeta() / f"{nombre}.png").exists())

    def test_cada_trazo_sale_de_su_dibujo_y_no_de_otra_parte(self) -> None:
        from pos_uniformes.scripts.trazar_silueta import SILUETAS, trazar

        carpeta = self._carpeta()
        for nombre in SILUETAS:
            with self.subTest(dibujo=nombre):
                self.assertEqual(
                    (carpeta / f"{nombre}.path").read_text(encoding="utf-8"),
                    trazar(carpeta / f"{nombre}.png"),
                )

    def test_los_contornos_vienen_cerrados_y_normalizados(self) -> None:
        from pos_uniformes.scripts.trazar_silueta import SILUETAS

        for nombre in SILUETAS:
            with self.subTest(dibujo=nombre):
                razon, d = (self._carpeta() / f"{nombre}.path").read_text(
                    encoding="utf-8"
                ).split("\n", 1)
                self.assertGreater(float(razon), 0)
                self.assertTrue(d.strip().startswith("M"))
                # Sin cerrar, el relleno sangra fuera de la figura.
                self.assertTrue(d.strip().endswith("Z"))

    def test_la_escena_usa_los_dibujos_de_daniel(self) -> None:
        from pos_uniformes.scripts.trazar_silueta import SILUETAS

        svg = (self._carpeta() / "halloween.svg").read_text(encoding="utf-8")
        for nombre in SILUETAS:
            with self.subTest(dibujo=nombre):
                _, d = (self._carpeta() / f"{nombre}.path").read_text(
                    encoding="utf-8"
                ).split("\n", 1)
                self.assertIn(d.strip(), svg)

    def test_la_bruja_conserva_sus_huecos(self) -> None:
        """El seguidor de bordes solo da el contorno de AFUERA.

        Sin buscar los agujeros encerrados, el hueco entre la escoba y la capa
        se rellenaba y la bruja dejaba de ser la bruja (visto en pantalla el
        07/10, antes de meterla).
        """
        _, d = (self._carpeta() / "bruja_de_daniel.path").read_text(
            encoding="utf-8"
        ).split("\n", 1)
        self.assertGreater(d.count("M"), 1)

    def test_los_huecos_se_dibujan_como_huecos(self) -> None:
        """Con varios contornos y sin `evenodd`, el hueco se rellena igual."""
        svg = (self._carpeta() / "halloween.svg").read_text(encoding="utf-8")
        self.assertIn('fill-rule="evenodd"', svg)

    def test_una_mota_del_borde_no_cuenta_como_hueco(self) -> None:
        """El borde suavizado deja pixeles sueltos; no son agujeros."""
        from pos_uniformes.scripts.trazar_silueta import HUECO_MINIMO, _huecos

        # Un cuadro lleno con un solo pixel claro en medio.
        m = [[True] * 9 for _ in range(9)]
        m[4][4] = False
        self.assertGreater(HUECO_MINIMO, 1)
        self.assertEqual(_huecos(m, 9, 9), [])

    def test_la_bandada_no_sale_toda_del_mismo_tamano(self) -> None:
        """Todos iguales parecen calcomanías pegadas a la misma distancia."""
        import re

        svg = (self._carpeta() / "halloween.svg").read_text(encoding="utf-8")
        anchos = {m for m in re.findall(r'scale\((\d+\.\d)\)" opacity', svg)}
        self.assertGreater(len(anchos), 5)

    def test_simplificar_no_se_come_las_puntas(self) -> None:
        """La tolerancia es lo que decide si las alas siguen siendo alas."""
        from pos_uniformes.scripts.trazar_silueta import TOLERANCIA, _simplificar

        self.assertLessEqual(TOLERANCIA, 2.0)
        # Un pico de 10 de alto no puede desaparecer con esa tolerancia.
        pico = [(0, 0), (5, -10), (10, 0)]
        self.assertEqual(_simplificar(pico, TOLERANCIA), pico)
