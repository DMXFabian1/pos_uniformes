from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.quote_text_service import build_quote_text


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
                    cantidad=2,
                    precio_unitario=Decimal("149.50"),
                    subtotal_linea=Decimal("299.00"),
                ),
                SimpleNamespace(
                    descripcion_snapshot="Pants deportivo CH azul",
                    sku_snapshot="SKU-002",
                    cantidad=1,
                    precio_unitario=Decimal("150.50"),
                    subtotal_linea=Decimal("150.50"),
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
        self.assertIn("Folio: PRE-001", text)
        self.assertIn("Estado: EMITIDO", text)
        self.assertIn("Cliente: Maria Lopez", text)
        self.assertIn("Telefono: 5551234567", text)
        self.assertIn("Fecha: 19/03/2026 12:30", text)
        self.assertIn("Vigencia: 31/03/2026", text)
        self.assertIn("Playera deportiva CH azul", text)
        self.assertIn("SKU-001 | 2 x 149.50 = 299.00", text)
        self.assertIn("Total estimado: 449.50", text)
        self.assertIn("Observaciones:", text)
        self.assertIn("Terminos y condiciones", text)
        self.assertIn("1. Validez del Presupuesto", text)
        self.assertIn("1.1. Los precios son vigentes al", text)
        self.assertIn("momento de emision y pueden cambiar", text)
        self.assertIn("sin previo aviso.", text)
        self.assertIn("1.2. No garantizan disponibilidad del", text)
        self.assertIn("producto.", text)
        self.assertIn("1.3. El presupuesto es valido por 7", text)
        self.assertIn("dias naturales, salvo indicacion", text)
        self.assertIn("contraria.", text)
        self.assertIn("2. Condiciones de Pago", text)
        self.assertIn("2.1. Los precios no aseguran reserva", text)
        self.assertIn("del producto.", text)
        self.assertIn("2.2. Se requiere confirmacion o", text)
        self.assertIn("anticipo para garantizar precio y", text)
        self.assertIn("disponibilidad.", text)
        self.assertIn("3. Promociones", text)
        self.assertIn("3.1. Por la alta demanda previa al", text)
        self.assertIn("inicio de clases, los padres que", text)
        self.assertIn("compren en julio de 2026 recibiran un", text)
        self.assertIn("descuento.", text)
        self.assertIn("Valido solo del 1 al 31 de julio,", text)
        self.assertIn("sujeto a disponibilidad.", text)
        self.assertNotIn("Gracias por tu compra.", text)
        self.assertNotIn("Gracias por tu preferencia.", text)


if __name__ == "__main__":
    unittest.main()
