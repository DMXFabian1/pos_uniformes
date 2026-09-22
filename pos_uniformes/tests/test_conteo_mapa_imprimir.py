"""El botón 🖨 de una prenda en «Cómo va la tienda».

Estás viendo que a esa prenda le faltan tallas: el atajo es sacar **esa** hoja
ahí mismo, sin pasar por el selector de escuela ni por el de destino (Daniel,
2026-09-22). Una sola prenda va en tira; varias siguen preguntando.
"""

from __future__ import annotations

import unittest

from PyQt6.QtWidgets import QApplication, QPushButton

from pos_uniformes.ui.dialogs.conteo_mapa_dialog import ConteoMapaWidget
from pos_uniformes.ui.helpers.conteo_mapa_widgets import CapaDetalle, Prenda

_app = QApplication.instance() or QApplication([])


def _prenda(nombre="Pants 2pz", *, al_dia=0, viejas=0, nunca=0):
    total = al_dia + viejas + nunca
    return {
        "nombre": nombre, "tipo_pieza": "Pants 2pz", "tallas": total,
        "al_dia": al_dia, "viejas": viejas, "nunca": nunca,
        "pct_al_dia": 0, "ultimo_dias": None, "estado": "nunca", "en_rojo": 0,
        "tallas_detalle": [],
    }


def _botones(w) -> list[QPushButton]:
    return [b for b in w.findChildren(QPushButton) if "Imprimir" in b.text()]


class BotonDeLaPrendaTest(unittest.TestCase):
    def test_aparece_cuando_le_faltan_tallas(self):
        w = Prenda(_prenda(al_dia=2, nunca=6))
        self.assertEqual(len(_botones(w)), 1)

    def test_no_aparece_si_ya_esta_al_dia(self):
        # Nada que contar: el botón solo estorbaría.
        w = Prenda(_prenda(al_dia=8))
        self.assertEqual(_botones(w), [])

    def test_dice_cuantas_faltan(self):
        self.assertIn("6 tallas por contar", _botones(Prenda(_prenda(al_dia=2, nunca=6)))[0].toolTip())
        self.assertIn("una talla por contar", _botones(Prenda(_prenda(al_dia=7, nunca=1)))[0].toolTip())

    def test_al_tocarlo_avisa_con_el_nombre_de_la_prenda(self):
        w = Prenda(_prenda("Playera Blanca", nunca=3))
        visto = []
        w.imprimir.connect(visto.append)
        _botones(w)[0].click()
        self.assertEqual(visto, ["Playera Blanca"])

    def test_el_boton_no_despliega_las_tallas(self):
        # El clic se queda en el botón: si desplegara, cada impresión movería
        # la pantalla debajo del dedo.
        w = Prenda(_prenda(nunca=3))
        antes = w._tallas.isVisible()
        _botones(w)[0].click()
        self.assertEqual(w._tallas.isVisible(), antes)


class AlcanceTest(unittest.TestCase):
    """El mapa tiene que decir de qué escuela o tipo de básicos es la prenda."""

    def _widget(self, capa: str) -> ConteoMapaWidget:
        w = ConteoMapaWidget(auto=False, scroll_propio=False)
        w._capa = capa
        return w

    def test_desde_una_escuela_manda_su_id(self):
        w = self._widget("e19")
        visto = []
        w.imprimir_prenda.connect(lambda e, t, p: visto.append((e, t, p)))
        w._pedir_hoja("Pants 2pz")
        self.assertEqual(visto, [(19, "", "Pants 2pz")])

    def test_desde_basicos_manda_el_tipo_y_sin_escuela(self):
        w = self._widget("bPantalón")
        visto = []
        w.imprimir_prenda.connect(lambda e, t, p: visto.append((e, t, p)))
        w._pedir_hoja("Pantalón Vestir Gris")
        self.assertEqual(visto, [(None, "Pantalón", "Pantalón Vestir Gris")])

    def test_desde_el_mapa_no_manda_nada(self):
        w = self._widget("mapa")
        visto = []
        w.imprimir_prenda.connect(lambda *a: visto.append(a))
        w._pedir_hoja("lo que sea")
        self.assertEqual(visto, [], "sin escuela ni tipo no hay hoja que sacar")


class CapaDetalleTest(unittest.TestCase):
    def test_reenvia_el_boton_de_cada_prenda(self):
        capa = CapaDetalle({
            "titulo": "Justo Sierra", "tallas": 10, "al_dia": 2, "viejas": 0, "nunca": 8,
            "pct_al_dia": 20, "ultimo_dias": None, "estado": "nunca", "en_rojo": 0,
            "prendas": [_prenda("Playera", nunca=4), _prenda("Pants", al_dia=6)],
        })
        visto = []
        capa.imprimir_prenda.connect(visto.append)
        for b in _botones(capa):
            b.click()
        self.assertEqual(visto, ["Playera"], "solo la que tiene tallas pendientes")


if __name__ == "__main__":
    unittest.main()
