"""Helpers para extraer filas exportables desde widgets de Analytics."""

from __future__ import annotations


def build_table_export_rows(table, fields: tuple[tuple[str, int], ...]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row_index in range(table.rowCount()):
        rows.append(
            {
                key: (table.item(row_index, column_index).text() if table.item(row_index, column_index) else "")
                for key, column_index in fields
            }
        )
    return rows


def build_analytics_layaway_export_rows(
    *,
    active_text: str,
    pending_balance_text: str,
    overdue_text: str,
    delivered_text: str,
) -> list[dict[str, str]]:
    return [
        {
            "activos": active_text,
            "saldo_pendiente": pending_balance_text,
            "vencidos": overdue_text,
            "entregados_periodo": delivered_text,
        }
    ]
