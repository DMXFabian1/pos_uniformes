from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.quote_text_service import build_quote_text


def _flatten(text: str) -> str:
    """Une las lineas del ticket (quitando bordes) para poder buscar frases
    que el render parte en varias lineas por el ancho del ticket."""
    stripped = (line.strip("│ ").strip() for line in text.splitlines())
    return " ".join(part for part in stripped if part)


class QuoteTextServiceTests(unittest.TestCase):
    def test_build_quote_text_renders_operational_summary(self) -> None:
        quote = SimpleNamespace(
            folio="PRE-001",
            estado=SimpleNamespace(value="EMITIDO"),
            cliente_nombre="Maria Lopez",
            cliente_telefono="5551234567",
            cliente=None,
            created_at=datetime(2026, 3, 19, 12, 30),
            vigencia_hasta=datetime(2026, 3, 31, 0, 0),
            total=Decimal("449.50"),
            observacion="Entregar impreso.",
            detalles=[
                SimpleNamespace(
                    descripcion_snapshot="Playera deportiva CH azul",
                    sku_snapshot="SKU-001",
                    talla_snapshot="CH",
                    cantidad=2,
                    precio_unitario=Decimal("149.50"),
                    subtotal_linea=Decimal("299.00"),
                    variante=SimpleNamespace(
                        producto=SimpleNamespace(tipo_pieza=SimpleNamespace(nombre="Playera")),
                    ),
                ),
                SimpleNamespace(
                    descripcion_snapshot="Pants deportivo CH azul",
                    sku_snapshot="SKU-002",
                    talla_snapshot="CH",
                    cantidad=1,
                    precio_unitario=Decimal("150.50"),
                    subtotal_linea=Decimal("150.50"),
                    variante=SimpleNamespace(
                        producto=SimpleNamespace(tipo_pieza=SimpleNamespace(nombre="Pants")),
                    ),
                ),
            ],
        )

        text = build_quote_text(
            quote=quote,
            business_name="POS Uniformes",
            business_phone="5550000000",
            business_address="Centro",
            ticket_footer="",
        )

        self.assertIn("POS Uniformes", text)
        self.assertIn("Presupuesto", text)
        self.assertIn("PRE-001", text)
        self.assertIn("EMITIDO", text)
        self.assertIn("Maria Lopez", text)
        self.assertIn("5551234567", text)
        self.assertIn("19/03/2026 12:30", text)
        self.assertIn("31/03/2026", text)
        self.assertIn("Playera deportiva CH azul", text)
        self.assertIn("Talla: CH", text)
        self.assertIn("$299.00", text)
        self.assertIn("PRESUPUESTO ESTIMADO", text)
        self.assertIn("$449.50", text)
        self.assertIn("Observaciones", text)
        self.assertIn("Entregar impreso.", text)
        self.assertIn("Terminos y condiciones", text)
        self.assertIn("1. Validez del Presupuesto", text)
        self.assertIn("Los precios son vigentes al momento de emision", _flatten(text))
        self.assertIn("2. Condiciones de Pago", text)
        self.assertIn("3. Promociones", text)
        self.assertNotIn("Gracias por tu compra.", text)
        self.assertNotIn("Gracias por tu preferencia.", text)

    def test_build_quote_text_keeps_three_piece_description_visible(self) -> None:
        quote = SimpleNamespace(
            folio="PRE-002",
            estado=SimpleNamespace(value="EMITIDO"),
            cliente_nombre="Mostrador",
            cliente_telefono="",
            cliente=None,
            created_at=None,
            vigencia_hasta=None,
            total=Decimal("450.00"),
            observacion="",
            detalles=[
                SimpleNamespace(
                    descripcion_snapshot="Playera deportiva azul (Conjunto deportivo 3pz - Patria)",
                    sku_snapshot="PLY-001",
                    talla_snapshot="",
                    cantidad=1,
                    precio_unitario=Decimal("100.00"),
                    subtotal_linea=Decimal("100.00"),
                    variante=None,
                ),
                SimpleNamespace(
                    descripcion_snapshot="Pants deportivo azul 2pz",
                    sku_snapshot="P2-001",
                    talla_snapshot="",
                    cantidad=1,
                    precio_unitario=Decimal("350.00"),
                    subtotal_linea=Decimal("350.00"),
                    variante=None,
                ),
            ],
        )

        text = build_quote_text(quote=quote)

        self.assertIn("Playera deportiva azul (Conjunto deportivo 3pz - Patria)", _flatten(text))
        self.assertIn("$100.00", text)


if __name__ == "__main__":
    unittest.main()
