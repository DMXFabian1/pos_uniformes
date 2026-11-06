"""La pantalla de arranque del kiosko dice qué hace y qué pasa si no resulta.

Daniel, 2026-11-05: «mejoremos esta ventana» — un rectángulo crema con
«Esperando a la PC principal… (53s)» en chiquito al pie.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.helpers import satellite_splash as mod


class SplashDelKioskoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_lleva_la_marca_sobre_la_banda(self) -> None:
        fondo = mod.construir_fondo("2026.11.11").toImage()
        self.assertEqual((fondo.width(), fondo.height()), (mod.ANCHO, mod.ALTO))
        self.assertEqual(fondo.pixelColor(0, 0).alpha(), 0)                 # esquinas redondas
        banda = fondo.pixelColor(30, 60)
        self.assertLess(banda.lightness(), 90)                              # vino, no crema
        # El logotipo está pintado: hay blanco dentro de la banda.
        blancos = sum(
            1 for x in range(140, 500, 2) for y in range(50, 100, 2)
            if fondo.pixelColor(x, y).lightness() > 230
        )
        self.assertGreater(blancos, 50)
        self.assertGreater(fondo.pixelColor(mod.ANCHO // 2, mod.ALTO - 60).lightness(), 220)   # cuerpo claro

    def test_decir_guarda_mensaje_detalle_y_avance_acotado(self) -> None:
        s = mod.SplashDelKiosko("1.0")
        s.decir("Esperando a la PC principal…", "Si en 53 s no aparece, abro con el catálogo guardado.", 1.7)
        self.assertEqual(s.mensaje, "Esperando a la PC principal…")
        self.assertIn("catálogo guardado", s.detalle)
        self.assertEqual(s.avance, 1.0)
        s.decir("Cargando", avance=None)
        self.assertIsNone(s.avance)
        s.close()

    def test_la_barra_avanza_en_pantalla(self) -> None:
        s = mod.SplashDelKiosko()
        s.show()
        y = mod.ALTO_BANDA + 126

        def terracota_en(x: int) -> bool:
            c: QColor = s.grab().toImage().pixelColor(x, y)
            return c.red() > 140 and c.green() < 110

        s.decir("Uno", avance=0.1)
        self.assertTrue(terracota_en(110))
        self.assertFalse(terracota_en(500))
        s.decir("Dos", avance=1.0)
        self.assertTrue(terracota_en(500))
        s.close()


if __name__ == "__main__":
    unittest.main()


class ArranqueDeVerdadTests(unittest.TestCase):
    """2026-11-06: al abrir el kiosko de verdad tronó dos veces — `drawContents`
    mezclaba AlignmentFlag con TextFlag (TypeError al pintar) y las llamadas a
    `_show_splash_message` pasaban el detalle donde iba la app. Las pruebas de
    antes pintaban el fondo y nunca el texto, ni llamaban a la función."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_pinta_el_mensaje_el_detalle_y_la_barra_sin_tronar(self) -> None:
        from PyQt6.QtGui import QPainter, QPixmap

        s = mod.SplashDelKiosko("6 nov · abc1234")
        s.decir("Esperando a la PC principal…",
                "Todavía no contesta. Si en 53 s no aparece, abro con el catálogo guardado.", 0.4)
        lienzo = QPixmap(mod.ANCHO, mod.ALTO)
        lienzo.fill(QColor("#f7f0e3"))
        p = QPainter(lienzo)
        s.drawContents(p)          # el TypeError salía aquí
        p.end()
        img = lienzo.toImage()
        oscuros = sum(
            1 for x in range(60, mod.ANCHO - 60, 2) for y in range(mod.ALTO_BANDA + 30, mod.ALTO_BANDA + 104, 2)
            if img.pixelColor(x, y).lightness() < 150
        )
        self.assertGreater(oscuros, 100)   # hay letras: mensaje y detalle

    def test_las_llamadas_del_arranque_le_hablan_bien_a_la_funcion(self) -> None:
        import ast
        import inspect

        from pos_uniformes import presupuestos_satelite_main as entrada

        dichos = []

        class _Falso:
            def decir(self, mensaje, detalle="", avance=None):
                dichos.append((mensaje, detalle, avance))

        entrada._show_splash_message(_Falso(), "Buscando…", "detalle", 0.05)
        self.assertEqual(dichos, [("Buscando…", "detalle", 0.05)])

        # Y cada llamada del archivo: el detalle es texto y el avance, número.
        arbol = ast.parse(inspect.getsource(entrada))
        llamadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call)
                    and getattr(n.func, "id", "") == "_show_splash_message"]
        self.assertGreaterEqual(len(llamadas), 5)
        for n in llamadas:
            self.assertLessEqual(len(n.args), 4, ast.unparse(n))
            if len(n.args) >= 3:
                self.assertIsInstance(n.args[2], (ast.Constant, ast.JoinedStr), ast.unparse(n))
