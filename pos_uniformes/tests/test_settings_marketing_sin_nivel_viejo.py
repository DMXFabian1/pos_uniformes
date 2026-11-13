"""Configuración de Marketing sin el nivel viejo.

2026-11-12: «el nivel viejo retíralo» (Daniel). El diálogo de Marketing ya no
ofrece «Compras minimas para LEAL», «Monto acumulado por frecuencia», los
«Descuentos por nivel» ni «Recalcular niveles». Guardar ya no escribe esas
columnas (se quedan en la base). La ventana y el monto para subir a Leal
siguen, porque los usa `subida_leal_service` (Maximoda Leal).
"""

from __future__ import annotations

import dataclasses
import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDoubleSpinBox, QLabel, QPushButton, QSpinBox, QWidget

from pos_uniformes.database.models import RolUsuario
from pos_uniformes.services.business_settings_service import BusinessSettingsInput, BusinessSettingsService
from pos_uniformes.services.settings_business_action_service import SettingsBusinessFormSnapshot
from pos_uniformes.ui.dialogs.settings_dialogs import build_marketing_settings_dialog

CAMPOS_RETIRADOS = (
    "leal_purchase_count_threshold",
    "leal_purchase_sum_threshold",
    "discount_basico",
    "discount_leal",
    "discount_profesor",
    "discount_mayorista",
)


class _VentanaFalsa(QWidget):
    """Lo mínimo que el diálogo de Marketing toma de MainWindow."""

    def __init__(self) -> None:
        super().__init__()
        self.settings_marketing_status_label = QLabel()
        self.settings_marketing_summary_label = QLabel()
        self.settings_marketing_review_days_spin = QSpinBox()
        self.settings_marketing_leal_spend_spin = QDoubleSpinBox()
        self.settings_marketing_save_button = QPushButton("Guardar")
        self.settings_marketing_history_button = QPushButton("Historial")

    def _handle_save_marketing_settings(self) -> None:
        pass

    def _handle_open_marketing_history(self) -> None:
        pass


class DialogoMarketingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _abrir(self):
        ventana = _VentanaFalsa()
        dialogo = build_marketing_settings_dialog(ventana)
        dialogo.show()
        self.app.processEvents()
        self._vivos = getattr(self, "_vivos", []) + [ventana, dialogo]
        self.addCleanup(ventana.close)
        self.addCleanup(dialogo.close)
        return ventana, dialogo

    def test_abre_sin_los_campos_retirados(self) -> None:
        # La ventana falsa no trae los spins viejos: si el diálogo los pidiera,
        # fallaría con AttributeError.
        _ventana, dialogo = self._abrir()
        textos = " ".join(l.text() for l in dialogo.findChildren(QLabel))
        for retirado in ("Compras minimas", "Monto acumulado por frecuencia", "Descuentos por nivel", "BASICO", "MAYORISTA"):
            self.assertNotIn(retirado, textos)
        botones = [b.text() for b in dialogo.findChildren(QPushButton) if b.isVisible()]
        self.assertNotIn("Recalcular niveles", botones)
        self.assertIn("Guardar", botones)
        self.assertIn("Historial", botones)

    def test_conserva_ventana_y_monto_de_leal(self) -> None:
        ventana, dialogo = self._abrir()
        spins = dialogo.findChildren(QSpinBox) + dialogo.findChildren(QDoubleSpinBox)
        self.assertIn(ventana.settings_marketing_review_days_spin, spins)
        self.assertIn(ventana.settings_marketing_leal_spend_spin, spins)
        self.assertEqual(len(spins), 2)

    def test_main_window_ya_no_tiene_lo_retirado(self) -> None:
        from pos_uniformes.ui.main_window import MainWindow

        self.assertFalse(hasattr(MainWindow, "_handle_recalculate_loyalty_levels"))
        self.assertFalse(hasattr(MainWindow, "_build_sale_loyalty_transition_notice"))


class GuardarConfiguracionTests(unittest.TestCase):
    def test_entrada_y_snapshot_sin_campos_retirados(self) -> None:
        entrada = {f.name for f in dataclasses.fields(BusinessSettingsInput)}
        snapshot = {f.name for f in dataclasses.fields(SettingsBusinessFormSnapshot)}
        for campo in CAMPOS_RETIRADOS:
            self.assertNotIn(campo, entrada)
            self.assertNotIn(campo, snapshot)
        self.assertIn("leal_spend_threshold", entrada)
        self.assertIn("loyalty_review_window_days", entrada)

    def test_guardar_no_toca_las_columnas_retiradas(self) -> None:
        config = SimpleNamespace(
            nombre_negocio="Maximoda",
            logo_path=None,
            loyalty_review_window_days=365,
            leal_spend_threshold=Decimal("3000.00"),
            leal_purchase_count_threshold=3,
            leal_purchase_sum_threshold=Decimal("2000.00"),
            discount_basico=Decimal("5.00"),
            discount_leal=Decimal("10.00"),
            discount_profesor=Decimal("15.00"),
            discount_mayorista=Decimal("20.00"),
        )
        payload = BusinessSettingsInput(
            nombre_negocio="Maximoda",
            logo_path=None,
            loyalty_review_window_days=180,
            leal_spend_threshold=Decimal("3500.00"),
            telefono=None,
            direccion=None,
            pie_ticket=None,
            transferencia_banco=None,
            transferencia_beneficiario=None,
            transferencia_clabe=None,
            transferencia_instrucciones=None,
            whatsapp_apartado_recordatorio=None,
            whatsapp_apartado_liquidado=None,
            whatsapp_cliente_promocion=None,
            whatsapp_cliente_seguimiento=None,
            whatsapp_cliente_saludo=None,
            impresora_preferida=None,
            impresora_tickets=None,
            copias_ticket=1,
        )
        admin = SimpleNamespace(activo=True, rol=RolUsuario.ADMIN)
        session = SimpleNamespace(add=lambda _o: None)
        auditado: list = []
        with patch.object(BusinessSettingsService, "get_or_create", return_value=config), patch(
            "pos_uniformes.services.business_settings_service.ManualPromoService.update_authorization_code"
        ), patch(
            "pos_uniformes.services.business_settings_service.MarketingAuditService.log_field_changes",
            side_effect=lambda _s, actor_user, fields: auditado.extend(fields),
        ):
            BusinessSettingsService.update_settings(session, admin, payload)

        self.assertEqual(config.loyalty_review_window_days, 180)
        self.assertEqual(config.leal_spend_threshold, Decimal("3500.00"))
        self.assertEqual(config.leal_purchase_count_threshold, 3)
        self.assertEqual(config.leal_purchase_sum_threshold, Decimal("2000.00"))
        self.assertEqual(
            (config.discount_basico, config.discount_leal, config.discount_profesor, config.discount_mayorista),
            (Decimal("5.00"), Decimal("10.00"), Decimal("15.00"), Decimal("20.00")),
        )
        self.assertEqual(
            {f.field_key for f in auditado}, {"loyalty_review_window_days", "leal_spend_threshold"}
        )


if __name__ == "__main__":
    unittest.main()
