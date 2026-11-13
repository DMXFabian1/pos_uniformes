from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QWidget

from pos_uniformes.database.models import RolUsuario
from pos_uniformes.ui.dialogs.settings_prompt_dialogs import (
    prompt_client_data,
    prompt_create_user_data,
    prompt_role_change,
    prompt_supplier_data,
)


class SettingsPromptDialogsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_create_user_prompt_returns_none_when_cancelled(self) -> None:
        with patch("pos_uniformes.ui.dialogs.settings_prompt_dialogs.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(prompt_create_user_data(QWidget()))

    def test_role_change_prompt_returns_none_when_cancelled(self) -> None:
        with patch("pos_uniformes.ui.dialogs.settings_prompt_dialogs.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(prompt_role_change(QWidget(), RolUsuario.ADMIN))

    def test_supplier_prompt_returns_none_when_cancelled(self) -> None:
        with patch("pos_uniformes.ui.dialogs.settings_prompt_dialogs.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(
                prompt_supplier_data(
                    QWidget(),
                    title="Proveedor",
                    helper_text="Captura proveedor.",
                )
            )

    def test_client_prompt_returns_none_when_cancelled(self) -> None:
        with patch("pos_uniformes.ui.dialogs.settings_prompt_dialogs.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(
                prompt_client_data(
                    QWidget(),
                    title="Cliente",
                    helper_text="Captura cliente.",
                )
            )

    # 2026-11-12 (Daniel: «la caja antigua ya no es de utilidad»): con los
    # tipos del catálogo (`ClienteTipo`), el combo ofrece Docente e
    # Institución y devuelve `tipo_clave` (lo que se guarda en tipo_cliente_id).
    TIPOS = [("GENERAL", "General"), ("DOCENTE", "Docente"), ("MAYORISTA", "Mayorista"), ("INSTITUCION", "Institución")]

    def _abrir_con_tipos(self, elegir: str | None = None, **kw):
        visto = {}

        def ejecutar(dialog):
            combo = dialog.findChildren(QComboBox)[0]
            visto["opciones"] = [combo.itemText(i) for i in range(combo.count())]
            visto["inicial"] = combo.currentData()
            if elegir is not None:
                combo.setCurrentIndex(combo.findData(elegir))
            return int(QDialog.DialogCode.Accepted)

        with patch("pos_uniformes.ui.dialogs.settings_prompt_dialogs.QDialog.exec", ejecutar):
            datos = prompt_client_data(QWidget(), title="Cliente", helper_text="h", tipos=self.TIPOS, **kw)
        return visto, datos

    def test_client_prompt_ofrece_los_tipos_del_catalogo(self) -> None:
        visto, datos = self._abrir_con_tipos("INSTITUCION")
        self.assertEqual(visto["opciones"], ["General", "Docente", "Mayorista", "Institución"])
        self.assertEqual(datos["tipo_clave"], "INSTITUCION")
        self.assertEqual(datos["tipo_cliente"], "MAYORISTA")  # el enum viejo, coherente

    def test_client_prompt_preselecciona_el_tipo_real(self) -> None:
        actuales = {"nombre": "Rosa", "tipo_cliente": "GENERAL", "tipo_clave": "DOCENTE", "telefono": "", "notas": ""}
        visto, datos = self._abrir_con_tipos(current_values=actuales)
        self.assertEqual(visto["inicial"], "DOCENTE")
        self.assertEqual((datos["tipo_clave"], datos["tipo_cliente"]), ("DOCENTE", "PROFESOR"))


if __name__ == "__main__":
    unittest.main()
