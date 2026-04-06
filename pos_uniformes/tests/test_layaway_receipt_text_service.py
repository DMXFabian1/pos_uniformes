from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.layaway_receipt_text_service import build_layaway_receipt_text


def _build_layaway(*, with_client: bool, with_payments: bool) -> SimpleNamespace:
    cliente = SimpleNamespace(codigo_cliente="CLI-123") if with_client else None
    producto = SimpleNamespace(nombre="Playera")
    variante = SimpleNamespace(sku="SKU-001", talla="14", color="Azul Marino", producto=producto)
    detalle = SimpleNamespace(
        variante=variante,
        cantidad=2,
        precio_unitario=Decimal("199.00"),
        subtotal_linea=Decimal("398.00"),
    )
    abonos = []
    if with_payments:
        abonos = [
            SimpleNamespace(
                created_at=datetime(2026, 3, 13, 10, 15),
                monto=Decimal("100.00"),
                referencia="ABN-01",
                usuario=SimpleNamespace(username="cajero"),
            )
        ]
    return SimpleNamespace(
        folio="APA-001",
        estado=SimpleNamespace(value="ACTIVO"),
        cliente=cliente,
        cliente_nombre="Maria Fernanda",
        cliente_telefono="5550001111",
        created_at=datetime(2026, 3, 13, 9, 30),
        fecha_compromiso=datetime(2026, 3, 20),
        detalles=[detalle],
        total=Decimal("398.00"),
        total_abonado=Decimal("100.00"),
        saldo_pendiente=Decimal("298.00"),
        abonos=abonos,
        observacion="Entrega sabado",
    )


class LayawayReceiptTextServiceTests(unittest.TestCase):
    def test_builds_receipt_text_with_client_and_payments(self) -> None:
        layaway = _build_layaway(with_client=True, with_payments=True)

        receipt = build_layaway_receipt_text(
            layaway=layaway,
            business_name="POS Uniformes",
            business_phone="5551234567",
            business_address="Centro",
            ticket_footer="Gracias por tu preferencia.",
            preferred_printer="Caja 1",
            ticket_copies=2,
        )

        self.assertIn("Comprobante de apartado", receipt)
        self.assertIn("Folio: APA-001", receipt)
        self.assertIn("Fecha: 13/03/2026 09:30", receipt)
        self.assertIn("Vencimiento: 20/03/2026", receipt)
        self.assertIn("Cliente: Maria Fernanda", receipt)
        self.assertIn("Productos", receipt)
        self.assertIn("- Playera | Talla 14 | Color Azul Marino | 2 x 199.00 = 398.00", receipt)
        self.assertIn("Total: 398.00", receipt)
        self.assertIn("Abonado: 100.00", receipt)
        self.assertIn("Saldo pendiente: 298.00", receipt)
        self.assertIn("Abonos:", receipt)
        self.assertIn("- 13/03/2026 10:15 | 100.00 | ABN-01", receipt)
        self.assertIn("Notas: Entrega sabado", receipt)
        self.assertNotIn("Codigo cliente:", receipt)
        self.assertNotIn("Estado:", receipt)
        self.assertNotIn("Telefono:", receipt)
        self.assertNotIn("SKU-001", receipt)
        self.assertNotIn("Copias configuradas:", receipt)
        self.assertNotIn("Impresora preferida:", receipt)

    def test_builds_receipt_text_without_client(self) -> None:
        layaway = _build_layaway(with_client=False, with_payments=False)

        receipt = build_layaway_receipt_text(
            layaway=layaway,
            business_name="POS Uniformes",
        )

        self.assertIn("Cliente: Maria Fernanda", receipt)
        self.assertNotIn("Abonos:", receipt)
        self.assertNotIn("Codigo cliente:", receipt)

    def test_filters_internal_layaway_notes_from_customer_receipt(self) -> None:
        layaway = _build_layaway(with_client=True, with_payments=False)
        layaway.observacion = "Creado desde Caja. | Ambiente de pruebas | Entrega sabado | Interno: nota"

        receipt = build_layaway_receipt_text(
            layaway=layaway,
            business_name="POS Uniformes",
        )

        self.assertIn("Notas: Entrega sabado", receipt)
        self.assertNotIn("Creado desde Caja", receipt)
        self.assertNotIn("Ambiente de pruebas", receipt)
        self.assertNotIn("Interno:", receipt)


if __name__ == "__main__":
    unittest.main()
