from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.ui.helpers.layaway_detail_helper import (
    build_empty_layaway_detail_view,
    build_error_layaway_detail_view,
    build_layaway_detail_view,
)


class LayawayDetailHelperTests(unittest.TestCase):
    def test_builds_empty_view(self) -> None:
        view = build_empty_layaway_detail_view()

        self.assertEqual(view.summary_label, "Selecciona un apartado")
        self.assertEqual(view.customer_label, "Sin detalle.")
        self.assertEqual(view.breakdown_label, "")
        self.assertEqual(view.due_badge.text, "Sin detalle")
        self.assertEqual(view.due_badge.tone, "neutral")
        self.assertEqual(view.detail_rows, ())
        self.assertEqual(view.payment_rows, ())
        self.assertFalse(view.sale_ticket_enabled)
        self.assertFalse(view.whatsapp_enabled)

    def test_builds_error_view(self) -> None:
        view = build_error_layaway_detail_view("Apartado no encontrado.")

        self.assertEqual(view.summary_label, "No se pudo cargar el apartado")
        self.assertEqual(view.customer_label, "Apartado no encontrado.")
        self.assertEqual(view.breakdown_label, "")
        self.assertEqual(view.due_badge.text, "Sin detalle")
        self.assertEqual(view.payment_rows, ())

    def test_builds_detail_view(self) -> None:
        view = build_layaway_detail_view(
            folio="APT-001",
            estado="LIQUIDADO",
            customer_code="CLI-001",
            customer_name="Maria Lopez",
            customer_phone="5551234567",
            subtotal=Decimal("499.00"),
            rounding_adjustment=Decimal("0.00"),
            total=Decimal("499.00"),
            total_paid=Decimal("300.00"),
            balance_due=Decimal("199.00"),
            commitment_label="2026-03-28",
            due_text="Vence 2026-03-28",
            due_tone="warning",
            notes_text="Cliente pasa el sabado.",
            detail_rows=[
                {
                    "sku": "SKU-001",
                    "product_name": "Playera deportiva",
                    "quantity": 2,
                    "unit_price": Decimal("149.50"),
                    "subtotal": Decimal("299.00"),
                }
            ],
            payment_rows=[
                {
                    "created_at": "2026-03-18 10:30",
                    "amount": Decimal("300.00"),
                    "reference": "REF-01",
                    "username": "admin",
                }
            ],
            sale_ticket_enabled=False,
            whatsapp_enabled=True,
        )

        self.assertEqual(view.summary_label, "APT-001 | LIQUIDADO")
        self.assertEqual(view.customer_label, "CLI-001 | Maria Lopez | 5551234567")
        self.assertEqual(view.balance_label, "Total $499.00 | Saldo $199.00")
        self.assertEqual(view.breakdown_label, "Subtotal $499.00 | Abonado $300.00")
        self.assertEqual(view.commitment_label, "Vencimiento: 2026-03-28")
        self.assertEqual(view.due_badge.text, "Vence 2026-03-28")
        self.assertEqual(view.due_badge.tone, "warning")
        self.assertEqual(view.notes_label, "Cliente pasa el sabado.")
        self.assertEqual(view.detail_rows[0].values, ("SKU-001", "Playera deportiva", 2, Decimal("149.50"), Decimal("299.00")))
        self.assertEqual(view.payment_rows[0].values, ("2026-03-18 10:30", Decimal("300.00"), "REF-01", "admin"))
        self.assertFalse(view.sale_ticket_enabled)
        self.assertTrue(view.whatsapp_enabled)

    def test_builds_detail_view_with_rounding_adjustment(self) -> None:
        view = build_layaway_detail_view(
            folio="APT-002",
            estado="ACTIVO",
            customer_code="CLI-001",
            customer_name="Maria Lopez",
            customer_phone="5551234567",
            subtotal=Decimal("351.20"),
            rounding_adjustment=Decimal("0.30"),
            total=Decimal("351.50"),
            total_paid=Decimal("100.00"),
            balance_due=Decimal("251.50"),
            commitment_label="2026-04-04",
            due_text="Vence 2026-04-04",
            due_tone="warning",
            notes_text="Creado desde Caja.",
            detail_rows=[],
            payment_rows=[],
            sale_ticket_enabled=False,
            whatsapp_enabled=True,
        )

        self.assertEqual(
            view.balance_label,
            "Total $351.50 | Saldo $251.50",
        )
        self.assertEqual(
            view.breakdown_label,
            "Subtotal $351.20 | Ajuste $0.30 | Abonado $100.00",
        )
        self.assertEqual(
            view.detail_rows[-1].values,
            ("", "Ajuste redondeo", "", "", Decimal("0.30")),
        )
        self.assertEqual(view.detail_rows[-1].tone, "warning")


if __name__ == "__main__":
    unittest.main()
