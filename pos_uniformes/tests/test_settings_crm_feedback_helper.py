from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.settings_crm_feedback_helper import (
    SettingsCrmFeedbackView,
    build_settings_client_guard_feedback,
    build_settings_client_result_feedback,
    build_settings_employee_result_feedback,
    build_settings_marketing_guard_feedback,
    build_settings_marketing_result_feedback,
    build_settings_supplier_guard_feedback,
    build_settings_supplier_result_feedback,
)


class SettingsCrmFeedbackHelperTests(unittest.TestCase):
    def test_supplier_feedback(self) -> None:
        self.assertEqual(
            build_settings_supplier_guard_feedback("create_supplier", is_admin=False, has_selection=False),
            SettingsCrmFeedbackView("Sin permisos", "Solo ADMIN puede crear proveedores."),
        )
        self.assertEqual(
            build_settings_supplier_result_feedback("toggle_supplier", supplier_name="Acme", status_text="activado"),
            SettingsCrmFeedbackView("Proveedor actualizado", "Proveedor 'Acme' activado correctamente."),
        )

    def test_client_feedback(self) -> None:
        self.assertEqual(
            build_settings_client_guard_feedback("create_client", is_admin=False, has_selection=False),
            SettingsCrmFeedbackView("Sin permisos", "Solo ADMIN puede crear clientes."),
        )
        self.assertEqual(
            build_settings_client_result_feedback(
                "generate_client_qr",
                client_name="Ana",
                client_code="CLI-001",
                asset_path="/tmp/qr.png",
            ),
            SettingsCrmFeedbackView(
                "QR generado",
                "QR del cliente 'CLI-001' guardado en:\n/tmp/qr.png",
            ),
        )

    def test_employee_feedback(self) -> None:
        self.assertEqual(
            build_settings_employee_result_feedback(
                "generate_employee_qr",
                employee_name="Lupita Gomez",
                employee_code="VEND-1",
                asset_path="/tmp/employee_qr.png",
            ),
            SettingsCrmFeedbackView(
                "QR generado",
                "QR de la empleada 'VEND-1' guardado en:\n/tmp/employee_qr.png",
            ),
        )
        self.assertEqual(
            build_settings_employee_result_feedback(
                "generate_employee_card",
                employee_name="Lupita Gomez",
                employee_code="VEND-1",
                asset_path="/tmp/employee_card.png",
            ),
            SettingsCrmFeedbackView(
                "Credencial generada",
                "Credencial de staff 'VEND-1' guardada en:\n/tmp/employee_card.png",
            ),
        )
        self.assertEqual(
            build_settings_employee_result_feedback(
                "set_employee_pin",
                employee_name="Lupita Gomez",
                employee_code="VEND-1",
            ),
            SettingsCrmFeedbackView(
                "PIN actualizado",
                "PIN de la empleada 'Lupita Gomez' configurado correctamente.",
            ),
        )

    def test_marketing_feedback(self) -> None:
        self.assertEqual(
            build_settings_marketing_guard_feedback("open_history", is_admin=False),
            SettingsCrmFeedbackView("Sin permisos", "Solo ADMIN puede consultar este historial."),
        )
        self.assertEqual(
            build_settings_marketing_result_feedback(total=10, changed=4),
            SettingsCrmFeedbackView(
                "Recalculo completado",
                "Niveles revisados: 10\nClientes con cambio aplicado: 4",
            ),
        )


if __name__ == "__main__":
    unittest.main()
