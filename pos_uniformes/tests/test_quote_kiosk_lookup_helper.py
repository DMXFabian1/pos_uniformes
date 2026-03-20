from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.quote_kiosk_lookup_service import QuoteKioskLookupSnapshot
from pos_uniformes.ui.helpers.quote_kiosk_lookup_helper import (
    build_quote_kiosk_lookup_view,
    build_quote_kiosk_recent_scan_rows,
    build_empty_quote_kiosk_lookup_view,
    push_quote_kiosk_recent_scan,
)


class QuoteKioskLookupHelperTests(unittest.TestCase):
    def test_build_quote_kiosk_lookup_view_formats_price_without_exposing_stock(self) -> None:
        view = build_quote_kiosk_lookup_view(
            QuoteKioskLookupSnapshot(
                sku="SKU-001",
                product_name="Pantalon Escolar",
                school_name="Colegio Mexico",
                garment_type_name="Pantalon",
                piece_type_name="Uniforme",
                size_label="32",
                color_label="Azul",
                price=Decimal("249.9"),
                stock_actual=2,
                location_label="Pasillo A",
                description_text="Tela reforzada.",
                origin_label="Catalogo actual",
            )
        )

        self.assertEqual(view.sku_label, "SKU-001")
        self.assertEqual(view.price_label, "$249.90")
        self.assertEqual(view.status_badge.text, "Listo para cotizar")
        self.assertEqual(view.status_badge.tone, "positive")
        self.assertIn("Colegio Mexico", view.context_label)

    def test_push_quote_kiosk_recent_scan_moves_last_scan_to_top(self) -> None:
        first = QuoteKioskLookupSnapshot(
            sku="SKU-001",
            product_name="Polo",
            school_name="General",
            garment_type_name="Playera",
            piece_type_name="Diario",
            size_label="M",
            color_label="Blanco",
            price=Decimal("100.00"),
            stock_actual=4,
            location_label="Rack 1",
            description_text="",
            origin_label="Catalogo actual",
        )
        second = QuoteKioskLookupSnapshot(
            sku="SKU-002",
            product_name="Pants",
            school_name="General",
            garment_type_name="Pants",
            piece_type_name="Deportivo",
            size_label="G",
            color_label="Azul",
            price=Decimal("200.00"),
            stock_actual=1,
            location_label="Rack 2",
            description_text="",
            origin_label="Catalogo actual",
        )

        history = push_quote_kiosk_recent_scan([], first)
        history = push_quote_kiosk_recent_scan(history, second)
        history = push_quote_kiosk_recent_scan(history, first)
        rows = build_quote_kiosk_recent_scan_rows(history)

        self.assertEqual([entry.sku for entry in history], ["SKU-001", "SKU-002"])
        self.assertEqual(rows[0].values[2], "$100.00")

    def test_build_empty_quote_kiosk_lookup_view(self) -> None:
        view = build_empty_quote_kiosk_lookup_view()

        self.assertEqual(view.price_label, "$0.00")
        self.assertEqual(view.status_badge.text, "Sin consulta")


if __name__ == "__main__":
    unittest.main()
