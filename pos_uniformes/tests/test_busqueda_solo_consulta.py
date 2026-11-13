"""Ctrl+S en el POS principal: buscar producto solo para consultar (2026-11-12).

Daniel: «la caja antigua ya no es de utilidad, todo lo demás corre en libreta
y kioskos y es lo único que importa, es donde vive nuestra operación».

Con la Caja antigua retirada, la búsqueda rápida ya no agrega a ningún
carrito, pero sigue sirviendo para ver precio y existencia buscando por
nombre, talla o color (Ctrl+K solo consulta por SKU).
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from pos_uniformes.ui.dialogs.quick_product_search_dialog import (  # noqa: E402
    QuickProductSearchDialog,
)
from pos_uniformes.ui.helpers import abrir_consultas as ac  # noqa: E402

_APP = QApplication.instance() or QApplication([])


def _fila(sku: str, stock: int = 3) -> dict:
    return {
        "sku": sku,
        "producto_nombre_base": "Pants UVEG",
        "talla": "10",
        "color": "Azul",
        "escuela_nombre": "UVEG",
        "tipo_prenda_nombre": "",
        "tipo_pieza_nombre": "Pants",
        "producto_activo": True,
        "variante_activo": True,
        "precio_venta": "350.00",
        "stock_actual": stock,
    }


class SoloConsultaTests(unittest.TestCase):
    def _dialogo(self, **kwargs) -> QuickProductSearchDialog:
        dialogo = QuickProductSearchDialog(catalog_rows=[_fila("PUV-10")], **kwargs)
        self.addCleanup(dialogo.deleteLater)
        dialogo._result_rows = [_fila("PUV-10", stock=0)]
        dialogo._table.setRowCount(1)
        dialogo._table.setColumnCount(max(1, dialogo._table.columnCount()))
        return dialogo

    def test_no_muestra_agregar_ni_cantidad(self) -> None:
        dialogo = self._dialogo(solo_consulta=True)
        self.assertEqual(dialogo.windowTitle(), "Consultar producto")
        self.assertTrue(dialogo._add_btn.isHidden())
        self.assertTrue(dialogo._qty_spin.isHidden())
        self.assertTrue(dialogo._qty_label.isHidden())
        self.assertTrue(dialogo._kiosk_btn.isHidden())

    def test_enter_o_doble_clic_no_agregan_ni_anotan_demanda(self) -> None:
        dialogo = self._dialogo(solo_consulta=True)
        dialogo._table.setCurrentCell(0, 0)
        self.assertEqual(dialogo._table.currentRow(), 0)
        emitidos: list = []
        dialogo.sku_selected.connect(lambda sku, qty: emitidos.append(sku))
        with patch("pos_uniformes.services.demanda_service.anotar") as anotar:
            dialogo._handle_add()
        self.assertEqual(emitidos, [])
        anotar.assert_not_called()

    def test_el_kiosko_no_cambia(self) -> None:
        dialogo = self._dialogo(kiosk_mode=True, solo_consulta=True)
        self.assertFalse(dialogo._add_btn.isHidden())
        self.assertEqual(dialogo._add_btn.text(), "Agregar a presupuesto")
        self.assertFalse(dialogo._kiosk_btn.isHidden())

    def test_sin_solo_consulta_sigue_igual(self) -> None:
        dialogo = self._dialogo()
        self.assertEqual(dialogo.windowTitle(), "Buscar producto")
        self.assertFalse(dialogo._add_btn.isHidden())
        dialogo._table.setCurrentCell(0, 0)
        emitidos: list = []
        dialogo.sku_selected.connect(lambda sku, qty: emitidos.append(sku))
        with patch("pos_uniformes.services.demanda_service.anotar"):
            dialogo._handle_add()
        self.assertEqual(emitidos, ["PUV-10"])


class AtajoTests(unittest.TestCase):
    def test_abrir_usa_solo_consulta(self) -> None:
        with patch(
            "pos_uniformes.ui.dialogs.quick_product_search_dialog.QuickProductSearchDialog"
        ) as dialogo:
            ac.abrir_busqueda_de_consulta(None)
        dialogo.assert_called_once_with(None, solo_consulta=True)
        dialogo.return_value.exec.assert_called_once()

    def test_instala_ctrl_s_y_cmd_s(self) -> None:
        from PyQt6.QtGui import QKeySequence
        from PyQt6.QtWidgets import QWidget

        ventana = QWidget()
        self.addCleanup(ventana.deleteLater)
        atajos = ac.instalar_busqueda_de_consulta(ventana)
        self.assertEqual(
            sorted(a.key().toString(QKeySequence.SequenceFormat.PortableText) for a in atajos),
            ["Ctrl+S", "Meta+S"],
        )
        with patch.object(ac, "abrir_busqueda_de_consulta") as abrir:
            atajos[0].activated.emit()
        abrir.assert_called_once_with(ventana)


if __name__ == "__main__":
    unittest.main()
