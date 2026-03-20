from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.analytics_export_helper import (
    build_analytics_layaway_export_rows,
    build_analytics_summary_export_rows,
    build_table_export_rows,
)


class _FakeItem:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class _FakeTable:
    def __init__(self, rows: list[list[str | None]]) -> None:
        self._rows = rows

    def rowCount(self) -> int:
        return len(self._rows)

    def item(self, row: int, column: int):
        value = self._rows[row][column]
        if value is None:
            return None
        return _FakeItem(value)


class AnalyticsExportHelperTests(unittest.TestCase):
    def test_build_table_export_rows_reads_table_cells(self) -> None:
        table = _FakeTable(
            [
                ["SKU-1", "Playera", "7", "$840.00"],
                ["SKU-2", None, "3", "$450.00"],
            ]
        )

        rows = build_table_export_rows(
            table,
            (
                ("sku", 0),
                ("producto", 1),
                ("unidades_vendidas", 2),
                ("ingreso", 3),
            ),
        )

        self.assertEqual(
            rows,
            [
                {"sku": "SKU-1", "producto": "Playera", "unidades_vendidas": "7", "ingreso": "$840.00"},
                {"sku": "SKU-2", "producto": "", "unidades_vendidas": "3", "ingreso": "$450.00"},
            ],
        )

    def test_build_analytics_layaway_export_rows_returns_single_summary_row(self) -> None:
        rows = build_analytics_layaway_export_rows(
            active_text="Apartados activos\n5",
            pending_balance_text="Saldo pendiente\n$980.50",
            overdue_text="Vencidos\n2",
            delivered_text="Entregados periodo\n4",
        )

        self.assertEqual(
            rows,
            [
                {
                    "activos": "Apartados activos\n5",
                    "saldo_pendiente": "Saldo pendiente\n$980.50",
                    "vencidos": "Vencidos\n2",
                    "entregados_periodo": "Entregados periodo\n4",
                }
            ],
        )

    def test_build_analytics_summary_export_rows(self) -> None:
        rows = build_analytics_summary_export_rows(
            period_label="Hoy",
            client_label="todos",
            total_sales="$351.50",
            total_tickets="1",
            average_ticket="$351.50",
            total_units="1",
        )

        self.assertEqual(
            rows,
            [
                {
                    "periodo": "Hoy",
                    "cliente": "todos",
                    "ingreso_periodo": "$351.50",
                    "tickets": "1",
                    "promedio_venta": "$351.50",
                    "unidades_vendidas": "1",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
