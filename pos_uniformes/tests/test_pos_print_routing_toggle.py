"""La caja de impresoras en la configuración del POS principal.

Antes eran dos opciones (local / enviar al satélite) y ahora es la lista de lo
que esta PC tiene cómo imprimir, que es de donde salen las dos respuestas del
ruteo. La caja es LA MISMA que la del menú admin del kiosko: tenerla copiada
dos veces hacía que guardar desde aquí borrara en silencio lo configurado del
otro lado (2026-10-07).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QCheckBox, QDialog, QPushButton

from pos_uniformes.database.models import TipoTrabajo
from pos_uniformes.services.print_routing_cache_service import (
    MODO_SATELITE,
    enviar_al_satelite_activo,
    impresoras_de_esta_pc,
    load_print_routing,
    puede_imprimir,
    save_print_routing,
)
from pos_uniformes.ui.dialogs.settings_dialogs import _build_print_routing_box

_SDD = "pos_uniformes.services.print_routing_cache_service.satellite_data_dir"


class PosRoutingToggleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _casillas(self, box):
        return {cb.text(): cb for cb in box.findChildren(QCheckBox)}

    def _guardar(self, box) -> None:
        boton = next(
            b for b in box.findChildren(QPushButton) if "Guardar" in b.text()
        )
        with patch(
            "pos_uniformes.ui.helpers.impresoras_de_la_pc_widget.QMessageBox.information"
        ):
            boton.click()

    def test_sin_configurar_aparece_todo_marcado(self) -> None:
        """Una PC que nunca tocó esto imprime todo, como siempre."""
        with tempfile.TemporaryDirectory() as d, patch(_SDD, return_value=Path(d)):
            box = _build_print_routing_box(QDialog())
            casillas = self._casillas(box)
            self.assertEqual(len(casillas), 4)
            self.assertTrue(all(cb.isChecked() for cb in casillas.values()))

    def test_desmarcar_todo_la_vuelve_estacion(self) -> None:
        with tempfile.TemporaryDirectory() as d, patch(_SDD, return_value=Path(d)):
            box = _build_print_routing_box(QDialog())
            for cb in self._casillas(box).values():
                cb.setChecked(False)
            self._guardar(box)
            self.assertTrue(enviar_al_satelite_activo())
            self.assertEqual(load_print_routing()[0], MODO_SATELITE)

    def test_se_puede_dejar_solo_lo_que_hay_enchufado(self) -> None:
        """El caso de la PC principal: impresora de tickets, sin las Brother."""
        with tempfile.TemporaryDirectory() as d, patch(_SDD, return_value=Path(d)):
            box = _build_print_routing_box(QDialog())
            casillas = self._casillas(box)
            for texto, cb in casillas.items():
                cb.setChecked("Tickets" in texto or "conteo" in texto)
            self._guardar(box)
            self.assertTrue(puede_imprimir(TipoTrabajo.TICKET))
            self.assertFalse(puede_imprimir(TipoTrabajo.ETIQUETA))

    def test_refleja_lo_que_estaba_guardado(self) -> None:
        with tempfile.TemporaryDirectory() as d, patch(_SDD, return_value=Path(d)):
            save_print_routing(MODO_SATELITE, "kiosko")
            box = _build_print_routing_box(QDialog())
            self.assertFalse(any(cb.isChecked() for cb in self._casillas(box).values()))
            self.assertEqual(impresoras_de_esta_pc(), [])

    def test_el_resumen_dice_que_va_a_pasar(self) -> None:
        from PyQt6.QtWidgets import QLabel

        with tempfile.TemporaryDirectory() as d, patch(_SDD, return_value=Path(d)):
            box = _build_print_routing_box(QDialog())
            for texto, cb in self._casillas(box).items():
                cb.setChecked("Tickets" in texto)
            textos = " ".join(l.text() for l in box.findChildren(QLabel))
            self.assertIn("Imprime aquí", textos)
            self.assertIn("Se va a la cola", textos)
            self.assertIn("Etiquetas", textos.split("Se va a la cola")[1])


if __name__ == "__main__":
    unittest.main()
