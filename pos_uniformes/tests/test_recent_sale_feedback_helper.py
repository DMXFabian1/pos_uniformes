from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.recent_sale_feedback_helper import (
    RecentSaleFeedbackView,
    build_recent_sale_guard_feedback,
    build_recent_sale_permission_label,
    build_recent_sale_result_feedback,
)


class RecentSaleFeedbackHelperTests(unittest.TestCase):
    def test_build_recent_sale_permission_label(self) -> None:
        self.assertEqual(build_recent_sale_permission_label(is_admin=True), "")
        self.assertEqual(
            build_recent_sale_permission_label(is_admin=False),
            "La cancelacion de ventas esta restringida a ADMIN.",
        )

    def test_build_recent_sale_guard_feedback(self) -> None:
        self.assertEqual(
            build_recent_sale_guard_feedback("view_ticket", has_selection=False, is_admin=False),
            RecentSaleFeedbackView("Sin seleccion", "Selecciona una venta para ver su ticket."),
        )
        self.assertEqual(
            build_recent_sale_guard_feedback("cancel_sale", has_selection=True, is_admin=False),
            RecentSaleFeedbackView("Sin permisos", "Solo ADMIN puede cancelar ventas."),
        )
        self.assertIsNone(build_recent_sale_guard_feedback("cancel_sale", has_selection=True, is_admin=True))

    def test_build_recent_sale_result_feedback(self) -> None:
        self.assertEqual(
            build_recent_sale_result_feedback("cancel_sale"),
            RecentSaleFeedbackView("Venta cancelada", "Venta cancelada correctamente."),
        )


if __name__ == "__main__":
    unittest.main()
