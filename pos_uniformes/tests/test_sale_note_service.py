from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.sale_note_service import build_sale_note_parts
from pos_uniformes.services.sale_discount_service import format_discount_label


class SaleNoteServiceTests(unittest.TestCase):
    def test_build_sale_note_parts_keeps_expected_order(self) -> None:
        breakdown = {
            "loyalty_discount": Decimal("10.00"),
            "promo_discount": Decimal("15.00"),
            "loyalty_source": "LEAL",
            "winner_label": "Promocion manual 15%",
        }

        notes = build_sale_note_parts(
            payment_method="Tarjeta",
            discount_percent=Decimal("15.00"),
            applied_discount=Decimal("75.00"),
            breakdown=breakdown,
            format_discount_label=format_discount_label,
            extra_notes=["Autorizacion bancaria OK", "Referencia 123"],
        )

        self.assertEqual(
            notes,
            [
                "Metodo de pago: Tarjeta",
                "Descuento: 15.00%",
                "Lealtad LEAL: 10%",
                "Promocion manual: 15%",
                "Promocion manual autorizada con codigo",
                "Beneficio aplicado: Promocion manual 15%",
                "Descuento aplicado: 75.00",
                "Autorizacion bancaria OK",
                "Referencia 123",
            ],
        )

    def test_build_sale_note_parts_omits_zero_value_sections(self) -> None:
        breakdown = {
            "loyalty_discount": Decimal("0.00"),
            "promo_discount": Decimal("0.00"),
            "loyalty_source": "",
            "winner_label": "Sin descuento",
        }

        notes = build_sale_note_parts(
            payment_method="Efectivo",
            discount_percent=Decimal("0.00"),
            applied_discount=Decimal("0.00"),
            breakdown=breakdown,
            format_discount_label=format_discount_label,
            extra_notes=[],
        )

        self.assertEqual(
            notes,
            [
                "Metodo de pago: Efectivo",
                "Descuento: 0.00%",
                "Beneficio aplicado: Sin descuento",
            ],
        )

    def test_build_sale_note_parts_includes_loyalty_without_manual_promo(self) -> None:
        breakdown = {
            "loyalty_discount": Decimal("10.00"),
            "promo_discount": Decimal("0.00"),
            "loyalty_source": "Leal",
            "winner_label": "Lealtad Leal 10%",
        }

        notes = build_sale_note_parts(
            payment_method="Transferencia",
            discount_percent=Decimal("10.00"),
            applied_discount=Decimal("50.00"),
            breakdown=breakdown,
            format_discount_label=format_discount_label,
            extra_notes=["Pago conciliado"],
        )

        self.assertEqual(
            notes,
            [
                "Metodo de pago: Transferencia",
                "Descuento: 10.00%",
                "Lealtad Leal: 10%",
                "Beneficio aplicado: Lealtad Leal 10%",
                "Descuento aplicado: 50.00",
                "Pago conciliado",
            ],
        )
