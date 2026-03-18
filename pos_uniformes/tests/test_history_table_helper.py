from __future__ import annotations

from datetime import datetime, timedelta
import unittest

from pos_uniformes.ui.helpers.history_table_helper import build_history_table_rows


class HistoryTableHelperTests(unittest.TestCase):
    def test_builds_sorted_history_rows_with_tones(self) -> None:
        rows = build_history_table_rows(
            [
                {
                    "fecha": datetime(2026, 3, 17, 10, 0),
                    "origen": "Catalogo",
                    "registro": "Producto X",
                    "tipo": "CREACION · nombre",
                    "cambio": "—",
                    "resultado": "Nuevo",
                    "usuario": "admin",
                    "detalle": "Alta",
                },
                {
                    "fecha": datetime(2026, 3, 18, 9, 30),
                    "origen": "Inventario",
                    "registro": "SKU-01",
                    "tipo": "SALIDA",
                    "cambio": -2,
                    "resultado": 5,
                    "usuario": "caja1",
                    "detalle": "Venta",
                },
            ]
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].values[0], "2026-03-18 09:30")
        self.assertEqual(rows[0].source_tone, "positive")
        self.assertEqual(rows[0].type_tone, "danger")
        self.assertEqual(rows[1].source_tone, "warning")
        self.assertEqual(rows[1].type_tone, "positive")

    def test_caps_history_rows_at_two_hundred(self) -> None:
        rows = build_history_table_rows(
            [
                {
                    "fecha": datetime(2026, 3, 18, 0, 0) + timedelta(minutes=minute),
                    "origen": "Inventario",
                    "registro": f"SKU-{minute}",
                    "tipo": "ENTRADA",
                    "cambio": 1,
                    "resultado": minute,
                    "usuario": "admin",
                    "detalle": "",
                }
                for minute in range(205)
            ]
        )

        self.assertEqual(len(rows), 200)
        self.assertEqual(rows[0].values[2], "SKU-204")
        self.assertEqual(rows[-1].values[2], "SKU-5")


if __name__ == "__main__":
    unittest.main()
