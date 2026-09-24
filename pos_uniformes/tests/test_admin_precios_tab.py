"""La pestaña 💲 Precios del admin del kiosko (Ctrl+Shift+A).

No es una puerta trasera: es la puerta que ya existe, que pide PIN de
administrador. Lo que se cuida aquí es que quede detrás de ese PIN, que use las
mismas funciones que la consola, y que no cambie nada sin confirmar.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_FUENTE = (
    Path(__file__).resolve().parent.parent / "ui" / "dialogs" / "satellite_admin_dialog.py"
).read_text(encoding="utf-8")


class DetrasDelPinTest(unittest.TestCase):
    def test_la_pestana_vive_en_el_dialogo_con_pin(self) -> None:
        # El diálogo entero pide PIN antes de abrir; no hay atajo aparte.
        self.assertIn("_prompt_pin", _FUENTE)
        self.assertIn('"💲  Precios"', _FUENTE)

    def test_no_hay_un_atajo_que_se_salte_el_pin(self) -> None:
        ventana = (
            Path(__file__).resolve().parent.parent / "ui" / "quote_satellite_window.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("_build_precios_box", ventana, "solo se llega por el admin")


class UnaSolaReglaTest(unittest.TestCase):
    def test_usa_las_mismas_funciones_que_la_consola(self) -> None:
        # Si la ventana buscara por su cuenta, podría encontrar otra prenda que
        # el script: la misma pregunta tiene que dar la misma respuesta.
        self.assertIn("from pos_uniformes.scripts.cambiar_precio import buscar_prendas, tallas_de", _FUENTE)
        self.assertIn("from pos_uniformes.scripts.cambiar_precio import tallas_de", _FUENTE)


class CuidadosTest(unittest.TestCase):
    def test_confirma_antes_de_cambiar(self) -> None:
        self.assertIn("QMessageBox.question", _FUENTE)
        self.assertIn("StandardButton.Yes", _FUENTE)

    def test_avisa_si_no_hay_servidor(self) -> None:
        # Los precios viven en la PC principal; sin ella no hay nada que tocar.
        self.assertIn("_sin_conexion", _FUENTE)
        self.assertIn("probe_database_host", _FUENTE)

    def test_rechaza_lo_que_no_es_un_precio(self) -> None:
        self.assertIn("InvalidOperation", _FUENTE)
        self.assertIn("no puede ser negativo", _FUENTE)

    def test_recuerda_que_hay_que_re_indexar(self) -> None:
        self.assertIn("Sincronizar", _FUENTE)

    def test_con_varias_prendas_que_empatan_no_deja_aplicar(self) -> None:
        self.assertIn("Sé más específico", _FUENTE)


class VivaTest(unittest.TestCase):
    """Que de verdad se arme, no solo que el texto esté."""

    def test_la_caja_se_construye_con_sus_partes(self) -> None:
        from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton, QTableWidget, QWidget

        _app = QApplication.instance() or QApplication([])
        from pos_uniformes.ui.dialogs.satellite_admin_dialog import _build_precios_box

        box = _build_precios_box(QWidget())
        self.assertEqual(
            [b.text() for b in box.findChildren(QPushButton)],
            ["Buscar", "Aplicar a todas sus tallas"],
        )
        self.assertTrue(box.findChildren(QTableWidget))
        self.assertEqual(len(box.findChildren(QLineEdit)), 2)   # prenda y precio

    def test_aplicar_nace_apagado(self) -> None:
        from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

        _app = QApplication.instance() or QApplication([])
        from pos_uniformes.ui.dialogs.satellite_admin_dialog import _build_precios_box

        box = _build_precios_box(QWidget())
        aplicar = [b for b in box.findChildren(QPushButton) if "Aplicar" in b.text()][0]
        self.assertFalse(aplicar.isEnabled(), "sin prenda elegida no hay nada que aplicar")


if __name__ == "__main__":
    unittest.main()
