from __future__ import annotations

import os
import unittest
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from pos_uniformes.database.models import TipoMovimientoCaja
from pos_uniformes.ui.dialogs.cash_session_prompt_dialogs import (
    CashCutSummaryView,
    build_cash_cut_summary_lines,
    prompt_cash_cut_data,
    prompt_cash_movement_data,
    prompt_cash_opening_correction,
    prompt_open_cash_session,
)


class CashSessionPromptDialogsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_open_cash_prompt_returns_none_when_cancelled(self) -> None:
        with patch("pos_uniformes.ui.dialogs.cash_session_prompt_dialogs.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(prompt_open_cash_session(QWidget(), suggested_amount=Decimal("150.00")))

    def test_cash_movement_prompt_returns_none_when_cancelled(self) -> None:
        with patch("pos_uniformes.ui.dialogs.cash_session_prompt_dialogs.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(
                prompt_cash_movement_data(
                    QWidget(),
                    movement_type=TipoMovimientoCaja.INGRESO,
                    target_total=None,
                )
            )

    def test_cash_opening_correction_prompt_returns_none_when_cancelled(self) -> None:
        with patch("pos_uniformes.ui.dialogs.cash_session_prompt_dialogs.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(
                prompt_cash_opening_correction(
                    QWidget(),
                    current_amount=Decimal("200.00"),
                )
            )

    def test_cash_cut_prompt_returns_none_when_cancelled(self) -> None:
        with patch("pos_uniformes.ui.dialogs.cash_session_prompt_dialogs.QDialog.exec", return_value=int(QDialog.DialogCode.Rejected)):
            self.assertIsNone(
                prompt_cash_cut_data(
                    QWidget(),
                    summary_view=CashCutSummaryView(
                        opened_at_label="2026-03-18 09:00",
                        opening_amount=Decimal("300.00"),
                        reactivo_count=1,
                        reactivo_total=Decimal("50.00"),
                        ingresos_count=1,
                        ingresos_total=Decimal("20.00"),
                        retiros_count=0,
                        retiros_total=Decimal("0.00"),
                        cash_sales_count=2,
                        cash_sales_total=Decimal("500.00"),
                        cash_payments_count=1,
                        cash_payments_total=Decimal("80.00"),
                        expected_amount=Decimal("930.00"),
                        suggested_next_reactivo=Decimal("300.00"),
                    ),
                )
            )

    def test_cash_cut_summary_lines_hide_zero_movement_breakdown(self) -> None:
        lines = build_cash_cut_summary_lines(
            CashCutSummaryView(
                opened_at_label="2026-04-08 14:40",
                opening_amount=Decimal("1000.00"),
                reactivo_count=0,
                reactivo_total=Decimal("0.00"),
                ingresos_count=0,
                ingresos_total=Decimal("0.00"),
                retiros_count=0,
                retiros_total=Decimal("0.00"),
                cash_sales_count=0,
                cash_sales_total=Decimal("0.00"),
                cash_payments_count=0,
                cash_payments_total=Decimal("0.00"),
                expected_amount=Decimal("1000.00"),
                suggested_next_reactivo=Decimal("1000.00"),
            )
        )

        self.assertEqual(
            lines,
            [
                "Apertura: 2026-04-08 14:40",
                "Reactivo inicial: $1000.00",
                "Esperado en caja: $1000.00",
            ],
        )

    def test_cash_cut_summary_lines_keep_breakdown_when_movements_exist(self) -> None:
        lines = build_cash_cut_summary_lines(
            CashCutSummaryView(
                opened_at_label="2026-04-08 14:40",
                opening_amount=Decimal("1000.00"),
                reactivo_count=1,
                reactivo_total=Decimal("200.00"),
                ingresos_count=1,
                ingresos_total=Decimal("50.00"),
                retiros_count=0,
                retiros_total=Decimal("0.00"),
                cash_sales_count=2,
                cash_sales_total=Decimal("500.00"),
                cash_payments_count=1,
                cash_payments_total=Decimal("80.00"),
                expected_amount=Decimal("1830.00"),
                suggested_next_reactivo=Decimal("1000.00"),
            )
        )

        self.assertIn("Reactivos extra: 1 | $200.00", lines)
        self.assertIn("Ingresos manuales: 1 | $50.00", lines)
        self.assertIn("Ventas con efectivo: 2", lines)
        self.assertIn("Efectivo por ventas: $500.00", lines)
        self.assertIn("Abonos con efectivo: 1", lines)
        self.assertIn("Efectivo por abonos: $80.00", lines)
        self.assertEqual(lines[-1], "Esperado en caja: $1830.00")


if __name__ == "__main__":
    unittest.main()
