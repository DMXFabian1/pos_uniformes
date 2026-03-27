from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.quote_feedback_helper import (
    QuoteFeedbackView,
    build_quote_guard_feedback,
    build_quote_result_feedback,
)


class QuoteFeedbackHelperTests(unittest.TestCase):
    def test_build_quote_guard_feedback(self) -> None:
        self.assertEqual(
            build_quote_guard_feedback("create_client", can_operate=False),
            QuoteFeedbackView("Sin permisos", "Tu usuario no puede crear clientes desde Presupuestos."),
        )
        self.assertEqual(
            build_quote_guard_feedback("save_quote", has_items=False),
            QuoteFeedbackView("Presupuesto vacio", "Agrega al menos una linea al presupuesto."),
        )
        self.assertEqual(
            build_quote_guard_feedback("cancel_quote", has_selection=False),
            QuoteFeedbackView("Sin seleccion", "Selecciona un presupuesto para cancelarlo."),
        )

    def test_build_quote_result_feedback(self) -> None:
        self.assertEqual(
            build_quote_result_feedback("save_quote", item_label="PRE-001"),
            QuoteFeedbackView("Presupuesto emitido", "Presupuesto PRE-001 emitido correctamente."),
        )
        self.assertEqual(
            build_quote_result_feedback("cancel_quote"),
            QuoteFeedbackView("Presupuesto cancelado", "El presupuesto se marco como cancelado."),
        )


if __name__ == "__main__":
    unittest.main()
