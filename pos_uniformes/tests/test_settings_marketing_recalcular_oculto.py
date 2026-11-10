"""T-A1 (E1-A, D6): «Recalcular niveles» no se ofrece en el diálogo de Marketing.

Solo se oculta: el manejador, la acción y el servicio siguen existiendo sin
cambios.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDoubleSpinBox, QLabel, QPushButton, QSpinBox, QWidget

from pos_uniformes.ui.dialogs.settings_dialogs import build_marketing_settings_dialog


class _VentanaFalsa(QWidget):
    """Lo mínimo que el diálogo de Marketing toma de MainWindow."""

    def __init__(self) -> None:
        super().__init__()
        self.settings_marketing_status_label = QLabel()
        self.settings_marketing_summary_label = QLabel()
        self.settings_marketing_review_days_spin = QSpinBox()
        self.settings_marketing_leal_purchase_count_spin = QSpinBox()
        for nombre in (
            "leal_spend",
            "leal_purchase_sum",
            "discount_basico",
            "discount_leal",
            "discount_profesor",
            "discount_mayorista",
        ):
            setattr(self, f"settings_marketing_{nombre}_spin", QDoubleSpinBox())
        self.settings_marketing_save_button = QPushButton("Guardar")
        self.settings_marketing_recalculate_button = QPushButton("Recalcular niveles")
        self.settings_marketing_history_button = QPushButton("Historial")
        self.recalculos = 0

    def _handle_save_marketing_settings(self) -> None:
        pass

    def _handle_recalculate_loyalty_levels(self) -> None:
        self.recalculos += 1

    def _handle_open_marketing_history(self) -> None:
        pass


class RecalcularOcultoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _abrir(self, *, es_admin: bool):
        ventana = _VentanaFalsa()
        # Así lo hace MainWindow según el rol (ADMIN habilita, CAJERO no).
        ventana.settings_marketing_recalculate_button.setEnabled(es_admin)
        dialogo = build_marketing_settings_dialog(ventana)
        dialogo.show()
        self.app.processEvents()
        # El diálogo es hijo de la ventana: se guardan las dos hasta el final.
        self._vivos = getattr(self, "_vivos", []) + [ventana, dialogo]
        self.addCleanup(ventana.close)
        return ventana, dialogo

    def _assert_oculto(self, ventana, dialogo) -> None:
        boton = ventana.settings_marketing_recalculate_button
        self.assertFalse(boton.isVisible())
        textos = [b.text() for b in dialogo.findChildren(QPushButton) if b.isVisible()]
        self.assertNotIn("Recalcular niveles", textos)
        # Los demás botones siguen ahí.
        self.assertIn("Guardar", textos)
        self.assertIn("Historial", textos)

    def test_oculto_para_admin(self) -> None:
        self._assert_oculto(*self._abrir(es_admin=True))

    def test_oculto_para_cajero(self) -> None:
        self._assert_oculto(*self._abrir(es_admin=False))

    def test_la_logica_sigue_existiendo(self) -> None:
        from pos_uniformes.services.loyalty_service import LoyaltyService
        from pos_uniformes.services.settings_marketing_action_service import (
            recalculate_settings_loyalty_levels,
        )
        from pos_uniformes.ui.main_window import MainWindow

        self.assertTrue(callable(recalculate_settings_loyalty_levels))
        self.assertTrue(callable(LoyaltyService.recalculate_all_clients))
        self.assertTrue(callable(MainWindow._handle_recalculate_loyalty_levels))

        # Sigue conectado a su manejador aunque nadie lo vea.
        ventana, _ = self._abrir(es_admin=True)
        ventana.settings_marketing_recalculate_button.click()
        self.assertEqual(ventana.recalculos, 1)


if __name__ == "__main__":
    unittest.main()
