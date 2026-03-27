from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.history_detail_helper import build_history_detail_view


class HistoryDetailHelperTests(unittest.TestCase):
    def test_builds_empty_history_detail_view(self) -> None:
        view = build_history_detail_view(None)

        self.assertIn("Selecciona un movimiento", view.summary_label)
        self.assertIn("Sin movimiento", view.meta_label)

    def test_builds_history_detail_view_from_row(self) -> None:
        view = build_history_detail_view(
            {
                "fecha_label": "20/03/2026 11:10",
                "origen": "Inventario",
                "registro": "SKU000001",
                "entidad": "PRESENTACION",
                "tipo": "APARTADO_RESERVA",
                "usuario": "admin",
                "cambio_label": "-1",
                "resultado_label": "4",
                "detalle": "Bata Manga Larga Blanca | APT-001",
            }
        )

        self.assertEqual(view.summary_label, "APARTADO_RESERVA | SKU000001")
        self.assertIn("20/03/2026 11:10", view.meta_label)
        self.assertIn("Cambio: -1 | Resultado: 4", view.change_label)
        self.assertIn("APT-001", view.notes_label)


if __name__ == "__main__":
    unittest.main()
