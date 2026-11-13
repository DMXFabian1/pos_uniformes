from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.ui.helpers.inventory_toggle_helper import (
    confirmacion_desactivar_prenda,
    confirmacion_desactivar_talla,
    contar_tallas_de_prenda,
    etiqueta_boton_prenda,
    etiqueta_boton_talla,
    preguntar,
)


class BotonesTests(unittest.TestCase):
    def test_dicen_lo_que_hacen(self) -> None:
        self.assertEqual(etiqueta_boton_talla(True), "Desactivar esta talla")
        self.assertEqual(etiqueta_boton_talla(False), "Activar esta talla")
        self.assertEqual(etiqueta_boton_prenda(True), "Desactivar toda la prenda")
        self.assertEqual(etiqueta_boton_prenda(False), "Activar toda la prenda")


class ConfirmacionTests(unittest.TestCase):
    def test_talla(self) -> None:
        c = confirmacion_desactivar_talla("Pants 2pz Colegio Muestra", "10", "Azul marino")
        self.assertEqual(
            c.texto,
            "¿Desactivar la talla 10 de Pants 2pz Colegio Muestra (Azul marino)?\n\n"
            "No se borra, deja de venderse. La puedes volver a activar desde su ficha.",
        )
        self.assertEqual(c.boton_si, "Desactivar talla")

    def test_talla_sin_color(self) -> None:
        self.assertIn("la talla UNI de Calceta?", confirmacion_desactivar_talla("Calceta", "UNI").texto)

    def test_prenda_con_tallas(self) -> None:
        c = confirmacion_desactivar_prenda("Pants 2pz Colegio Muestra", 8)
        self.assertTrue(c.texto.startswith("¿Desactivar toda la prenda Pants 2pz Colegio Muestra?"))
        self.assertIn("Sus 8 tallas dejan de venderse. No se borra", c.texto)

    def test_prenda_una_o_sin_saber(self) -> None:
        self.assertIn("Su única talla", confirmacion_desactivar_prenda("Gorra", 1).texto)
        self.assertIn("Todas sus tallas", confirmacion_desactivar_prenda("Gorra", None).texto)

    def test_contar_tallas(self) -> None:
        filas = [{"producto_id": 1}, {"producto_id": 1}, {"producto_id": 2}, {"producto_id": None}]
        self.assertEqual(contar_tallas_de_prenda(filas, 1), 2)
        self.assertIsNone(contar_tallas_de_prenda(filas, 9))
        self.assertIsNone(contar_tallas_de_prenda(filas, None))


class PreguntarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _responder(self, boton: str) -> bool:
        from PyQt6.QtWidgets import QMessageBox

        def exec_(caja):
            caja._prueba_texto = caja.text()
            for b in caja.buttons():
                if b.text() == boton:
                    b.click()
            return 0

        with patch.object(QMessageBox, "exec", exec_):
            return preguntar(None, confirmacion_desactivar_talla("Pants", "10", "Azul"))

    def test_si(self) -> None:
        self.assertTrue(self._responder("Desactivar talla"))

    def test_cancelar(self) -> None:
        self.assertFalse(self._responder("Cancelar"))


if __name__ == "__main__":
    unittest.main()
