from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.settings_cash_history_movements_helper import (
    build_settings_cash_history_movements_view,
)


class SettingsCashHistoryMovementsHelperTests(unittest.TestCase):
    def test_builds_empty_selection_view(self) -> None:
        view = build_settings_cash_history_movements_view(
            cash_session_id=None,
            movements=[],
        )

        self.assertEqual(view.status_label, "Selecciona un corte para ver sus movimientos.")
        self.assertEqual(view.rows, ())

    def test_builds_rows_and_status_for_selected_session(self) -> None:
        view = build_settings_cash_history_movements_view(
            cash_session_id=15,
            movements=[
                {
                    "fecha": "2026-03-18 10:30",
                    "tipo": "INGRESO",
                    "monto": Decimal("100.00"),
                    "usuario": "Admin Uno",
                    "concepto": "Fondo extra",
                },
                {
                    "fecha": "2026-03-18 10:40",
                    "tipo": "RETIRO",
                    "monto": Decimal("50.00"),
                    "usuario": "Admin Uno",
                    "concepto": "",
                },
            ],
        )

        self.assertEqual(view.status_label, "Movimientos registrados en la sesion #15: 2")
        self.assertEqual(len(view.rows), 2)
        self.assertEqual(view.rows[0].values, ("2026-03-18 10:30", "INGRESO", "$100.00", "Admin Uno", "Fondo extra"))
        self.assertEqual(view.rows[0].type_tone, "warning")
        self.assertEqual(view.rows[1].values, ("2026-03-18 10:40", "RETIRO", "$50.00", "Admin Uno", "-"))
        self.assertEqual(view.rows[1].type_tone, "danger")

    def test_builds_empty_status_for_session_without_movements(self) -> None:
        view = build_settings_cash_history_movements_view(
            cash_session_id=8,
            movements=[],
        )

        self.assertEqual(
            view.status_label,
            "La sesion #8 no tiene movimientos manuales registrados.",
        )


if __name__ == "__main__":
    unittest.main()
