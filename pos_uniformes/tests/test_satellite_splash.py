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
