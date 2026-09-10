"""El presupuesto sigue igual: anotar la falta no puede estorbar el mostrador.

Daniel preguntó lo correcto: ¿podré seguir haciendo presupuestos e imprimiendo
normal? Estas pruebas ejercitan la tarjeta de resultados real del kiosko y el
carrito de venta rápida, con la anotación activa y también rota.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication, QPushButton  # noqa: E402

from pos_uniformes.services import demanda_service as dm  # noqa: E402
from pos_uniformes.ui.helpers.quote_guided_catalog_helper import (  # noqa: E402
    esta_agotada,
    estilo_talla,
    estilo_talla_seleccionada,
    etiqueta_talla,
)

_APP = QApplication.instance() or QApplication([])

DISPONIBLE = {"sku": "SKU001573", "talla": "6", "stock_actual": 33, "precio_venta": 135.0}
AGOTADA = {"sku": "SKU001579", "talla": "18", "stock_actual": 0, "precio_venta": 155.0}


class BotonComoEnElKioskoTests(unittest.TestCase):
    """Reproduce lo que hace `_build_search_family_card` con cada talla."""

    def _boton(self, variante, precio):
        btn = QPushButton(etiqueta_talla(variante, precio))
        btn.setProperty("searchVariantSku", variante["sku"])
        btn.setProperty("estiloBase", estilo_talla(variante))
        btn.setStyleSheet(estilo_talla(variante))
        return btn

    def test_la_talla_con_stock_se_ve_y_se_comporta_como_siempre(self) -> None:
        btn = self._boton(DISPONIBLE, 135.0)
        self.assertEqual(btn.text(), "Talla 6 · $135.00")
        self.assertEqual(btn.property("searchVariantSku"), "SKU001573")
        self.assertIn("#f5f0e8", btn.styleSheet())  # el beige de siempre

    def test_hoy_la_agotada_se_ve_igual_que_las_demas(self) -> None:
        """El stock no es confiable: la empleada no ve nada distinto."""
        self.assertEqual(
            self._boton(AGOTADA, 155.0).text(), "Talla 18 · $155.00"
        )

    def test_con_el_stock_confiable_vuelve_a_su_estilo_al_deseleccionar(self) -> None:
        with patch.object(dm, "EXISTENCIA_CONFIABLE", True):
            btn = self._boton(AGOTADA, 155.0)
            base = btn.property("estiloBase")
            btn.setStyleSheet(estilo_talla_seleccionada(AGOTADA))
            self.assertIn("#2f6b2f", btn.styleSheet())
            btn.setStyleSheet(str(btn.property("estiloBase")))
            self.assertEqual(btn.styleSheet(), base)  # no regresa pintada como disponible

    def test_el_sku_para_el_presupuesto_no_cambia_por_estar_agotada(self) -> None:
        self.assertEqual(self._boton(AGOTADA, 155.0).property("searchVariantSku"), AGOTADA["sku"])
        self.assertTrue(esta_agotada(AGOTADA))
        self.assertFalse(esta_agotada(DISPONIBLE))


class NuncaEstorbaTests(unittest.TestCase):
    def test_anotar_con_el_disco_roto_no_lanza(self) -> None:
        with patch.object(dm, "_save_raw", side_effect=OSError("disco lleno")):
            dm.anotar(dm.TALLA_AGOTADA, sku="SKU001579", talla="18")  # no debe explotar

    def test_anotar_sin_carpeta_de_datos_no_lanza(self) -> None:
        with patch.object(dm, "_queue_path", side_effect=RuntimeError("sin AppData")):
            dm.anotar(dm.BUSQUEDA_VACIA, texto="chamarra sabes")

    def test_cancelar_carrito_registra_las_piezas_y_no_truena(self) -> None:
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        anotadas = []
        falso = type(
            "W",
            (),
            {
                "_items": [{"sku": "S1", "nombre": "Playera", "talla": "6", "cantidad": 2}],
                "_employee_code": "VEND-2",
                "_anotar_carrito_cancelado": QuickSaleWidget._anotar_carrito_cancelado,
            },
        )()
        with patch.object(dm, "anotar", lambda *a, **k: anotadas.append(k)):
            falso._anotar_carrito_cancelado()
        self.assertEqual(len(anotadas), 1)
        self.assertEqual(anotadas[0]["piezas"], 2)
        self.assertEqual(anotadas[0]["sku"], "S1")

    def test_si_anotar_falla_el_carrito_se_limpia_igual(self) -> None:
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        falso = type(
            "W",
            (),
            {
                "_items": [{"sku": "S1", "cantidad": 1}],
                "_employee_code": "VEND-2",
                "_anotar_carrito_cancelado": QuickSaleWidget._anotar_carrito_cancelado,
            },
        )()
        with patch.object(dm, "anotar", side_effect=RuntimeError("base caída")):
            falso._anotar_carrito_cancelado()  # se traga el error, la venta sigue


if __name__ == "__main__":
    unittest.main()
