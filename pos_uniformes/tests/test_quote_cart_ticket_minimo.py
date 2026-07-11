"""El ticket de presupuesto (Piezas agregadas) muestra el mínimo para apartar.

Pedido en piso (2026-07-08): que el ticket de presupuesto traiga el mínimo de
apartado (25%) como ya lo hace el ticket de apartado de Venta Rápida.
"""

from __future__ import annotations

import os
import unittest
from datetime import date
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.ui.quote_satellite_window import _build_cart_ticket_text


def _ticket(total: str, cart=None) -> str:
    return _build_cart_ticket_text(
        folio="P-001",
        client_name="Ana",
        cart=cart or [
            {"cantidad": 1, "precio_unitario": total, "producto_nombre": "Pants",
             "sku": "SKU1", "talla": "6", "tipo_pieza_nombre": "Pants 2pz"},
        ],
        total=Decimal(total),
        validity_date=date(2026, 7, 31),
        notes="",
    )


class CartTicketMinimoTests(unittest.TestCase):
    def test_ticket_includes_apartado_minimum_line(self) -> None:
        text = _ticket("515.00")
        self.assertIn("Apartado minimo (25%):", text)

    def test_minimum_uses_cash_rounding_rule(self) -> None:
        # 25% de 515 = 128.75 -> regla de caja -> 129.00
        self.assertIn("$129.00", _ticket("515.00"))

    def test_minimum_scales_with_total(self) -> None:
        # 25% de 1000 = 250.00 exacto
        self.assertIn("$250.00", _ticket("1000.00"))


if __name__ == "__main__":
    unittest.main()
