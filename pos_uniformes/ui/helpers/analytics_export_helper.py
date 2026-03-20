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


def build_analytics_summary_export_rows(
    *,
    period_label: str,
    client_label: str,
    total_sales: str,
    total_tickets: str,
    average_ticket: str,
    total_units: str,
) -> list[dict[str, str]]:
    return [
        {
            "periodo": period_label,
            "cliente": client_label,
            "ingreso_periodo": total_sales,
            "tickets": total_tickets,
            "promedio_venta": average_ticket,
            "unidades_vendidas": total_units,
        }
    ]
