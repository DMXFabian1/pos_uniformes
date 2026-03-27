from __future__ import annotations

from datetime import datetime
import unittest

from pos_uniformes.ui.helpers.history_export_helper import (
    build_history_export_dir_name,
    build_history_export_rows,
)


class HistoryExportHelperTests(unittest.TestCase):
    def test_build_history_export_rows_normalizes_fields(self) -> None:
        rows = build_history_export_rows(
            [
                {
                    "fecha": datetime(2026, 3, 20, 11, 8),
                    "origen": "Inventario",
                    "entidad": "PRESENTACION",
                    "registro": "SKU000001",
                    "tipo": "APARTADO_RESERVA",
                    "cambio": -1,
                    "resultado": 4,
                    "usuario": "admin",
                    "detalle": "Bata",
                }
            ]
        )

        self.assertEqual(rows[0]["fecha"], "20/03/2026 11:08")
        self.assertEqual(rows[0]["registro"], "SKU000001")
        self.assertEqual(rows[0]["cambio"], -1)

    def test_build_history_export_dir_name_uses_timestamp(self) -> None:
        name = build_history_export_dir_name(datetime(2026, 3, 20, 11, 8, 59))
        self.assertEqual(name, "20260320_110859")


if __name__ == "__main__":
    unittest.main()
