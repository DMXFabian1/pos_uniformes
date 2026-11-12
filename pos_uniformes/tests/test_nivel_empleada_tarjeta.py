"""La tarjeta de su descuento en la Libreta de cada empleada (Daniel, 2026-11-12).

«Para que ellas vean qué tanto descuento se van a llevar»: su % de este mes,
cuánto le queda del tope, lo que se ha ahorrado y su avance al siguiente nivel.
"""

from __future__ import annotations

import os
import unittest
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.services import incentivo_empleada_service as inc
from pos_uniformes.tests.test_e6_descuento_empleadas import NIVELES, D, N, _Db, _local


def _avance(**kw):
    base = dict(
        pct_este_mes=D("15"), restante_este_mes=D("2200.00"), comisiones_mes=200, pct_mes_siguiente=D("10"),
        siguiente=N(250, D("15")), nombre_mes_siguiente="diciembre", tope=D("3000"), usado=D("800.00"),
        ahorrado_mes=D("125.00"), niveles=tuple(NIVELES), nombre_mes="noviembre",
    )
    base.update(kw)
    return inc.AvanceEmpleada(**base)


class AhorroTests(unittest.TestCase):
    def test_ahorro_de_una_compra(self):
        detalle = [
            {"precio": "400", "cantidad": 2, "desc_empleada_pct": "15"},   # 120
            {"precio": "100", "cantidad": 1},                              # 5 (las de antes, 5 %)
            {"precio": "300", "cantidad": 1, "desc_empleada_pct": "0"},    # rebajada
        ]
        self.assertEqual(inc.ahorro_de(detalle), D("125.00"))

    def test_progreso_y_lo_que_falta(self):
        av = _avance()
        self.assertEqual(av.faltan, 50)
        self.assertAlmostEqual(av.progreso, 0.8)
        al_maximo = _avance(comisiones_mes=400, siguiente=None, pct_mes_siguiente=D("20"))
        self.assertEqual((al_maximo.faltan, al_maximo.progreso), (0, 1.0))


class AvanceConLaBaseTests(_Db):
    def test_lo_ahorrado_es_solo_suyo_y_de_este_mes(self):
        self._venta("VEND-3", 160, _local(2026, 10, 8))
        self._venta("VEND-1", 0, _local(2026, 11, 3), empleada=True, compradora="VEND-3",
                    detalle=[{"precio": "400", "cantidad": 2, "desc_empleada_pct": "10"}])     # 80
        self._venta("VEND-1", 0, _local(2026, 10, 3), empleada=True, compradora="VEND-3",
                    detalle=[{"precio": "999", "cantidad": 1, "desc_empleada_pct": "10"}])     # otro mes
        self._venta("VEND-1", 0, _local(2026, 11, 4), empleada=True, compradora="VEND-4",
                    detalle=[{"precio": "500", "cantidad": 1, "desc_empleada_pct": "10"}])     # otra
        av = inc.avance(self.s, "VEND-3", hoy=date(2026, 11, 10))
        self.assertEqual(av.ahorrado_mes, D("80.00"))
        self.assertEqual((av.tope, av.usado, av.nombre_mes), (D("3000"), D("800.00"), "noviembre"))
        self.assertEqual(av.niveles, tuple(NIVELES))


class TarjetaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _tarjeta(self, av):
        from pos_uniformes.ui.widgets.nivel_empleada_tarjeta import NivelEmpleadaTarjeta

        t = NivelEmpleadaTarjeta()
        t.mostrar(av)
        return t

    def test_con_nivel_y_tope(self):
        t = self._tarjeta(_avance())
        self.assertFalse(t.isHidden())
        self.assertEqual(t.pct.text(), "15 %")
        self.assertIn("10 % en uniforme", t.detalle_pct.text())
        self.assertIn("$2,200.00", t.quedan.text())
        self.assertIn("$125.00", t.ahorro.text())
        self.assertIn("te faltan 50 para comprar con 15 % en diciembre", t.avance.text())
        self.assertEqual(t.barra_avance.value(), 800)
        self.assertEqual(len(t.peldanos), 4)

    def test_con_el_base(self):
        t = self._tarjeta(_avance(pct_este_mes=D("5"), restante_este_mes=D("3000"), ahorrado_mes=D("0")))
        self.assertIn("5 % de siempre", t.quedan.text())
        self.assertTrue(t.barra_tope.isHidden())
        self.assertIn("Aún no compras", t.ahorro.text())

    def test_al_maximo(self):
        t = self._tarjeta(_avance(comisiones_mes=400, siguiente=None, pct_mes_siguiente=D("20")))
        self.assertIn("el máximo, 20 %", t.avance.text())
        self.assertEqual(t.barra_avance.value(), 1000)

    def test_sin_dato_no_se_ve(self):
        t = self._tarjeta(_avance())
        t.mostrar(None)
        self.assertTrue(t.isHidden())


if __name__ == "__main__":
    unittest.main()
