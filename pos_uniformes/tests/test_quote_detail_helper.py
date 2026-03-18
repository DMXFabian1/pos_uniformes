from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.quote_detail_helper import (
    build_empty_quote_detail_view,
    build_error_quote_detail_view,
    build_quote_detail_view,
)


class QuoteDetailHelperTests(unittest.TestCase):
    def test_builds_empty_detail_view(self) -> None:
        view = build_empty_quote_detail_view()

        self.assertEqual(view.customer_label, "Sin detalle.")
        self.assertEqual(view.meta_label, "")
        self.assertEqual(view.notes_label, "")
        self.assertEqual(view.detail_rows, [])

    def test_builds_error_detail_view(self) -> None:
        view = build_error_quote_detail_view("Presupuesto no encontrado.")

        self.assertEqual(view.customer_label, "No se pudo cargar el presupuesto")
        self.assertEqual(view.meta_label, "Presupuesto no encontrado.")
        self.assertEqual(view.notes_label, "")
        self.assertEqual(view.detail_rows, [])

    def test_builds_complete_detail_view(self) -> None:
        view = build_quote_detail_view(
            folio="P-001",
            client_name="Maria Lopez",
            status_label="EMITIDO",
            phone_text="5551234567",
            total=Decimal("449.5"),
            validity_label="2026-03-31",
            user_label="admin",
            notes_text="Entregar cotizacion impresa.",
            detail_rows=[
                {
                    "sku": "SKU-001",
                    "description": "Playera deportiva CH azul",
                    "quantity": 2,
                    "unit_price": Decimal("149.50"),
                    "subtotal": Decimal("299.00"),
                },
                {
                    "sku": "SKU-002",
                    "description": "Pants deportivo CH azul",
                    "quantity": 1,
                    "unit_price": Decimal("150.50"),
                    "subtotal": Decimal("150.50"),
                },
            ],
        )

        self.assertEqual(view.customer_label, "P-001 | Maria Lopez")
        self.assertEqual(
            view.meta_label,
            "Estado EMITIDO | Telefono 5551234567 | Total $449.50 | Vigencia 2026-03-31 | Usuario admin",
        )
        self.assertEqual(view.notes_label, "Entregar cotizacion impresa.")
        self.assertEqual(len(view.detail_rows), 2)
        self.assertEqual(view.detail_rows[0].sku, "SKU-001")
        self.assertEqual(view.detail_rows[0].description, "Playera deportiva CH azul")
        self.assertEqual(view.detail_rows[0].quantity, 2)
        self.assertEqual(view.detail_rows[0].unit_price, Decimal("149.50"))
        self.assertEqual(view.detail_rows[0].subtotal, Decimal("299.00"))


if __name__ == "__main__":
    unittest.main()
