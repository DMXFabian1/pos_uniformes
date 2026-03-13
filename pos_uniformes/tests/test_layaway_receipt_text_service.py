from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.layaway_receipt_text_service import build_layaway_receipt_text


def _build_layaway(*, with_client: bool, with_payments: bool) -> SimpleNamespace:
    cliente = SimpleNamespace(codigo_cliente="CLI-123") if with_client else None
    producto = SimpleNamespace(nombre="Playera")
    variante = SimpleNamespace(sku="SKU-001", producto=producto)
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

        self.assertIn("Comprobante de apartado: APA-001", receipt)
        self.assertIn("Cliente: Maria Fernanda", receipt)
        self.assertIn("Codigo cliente: CLI-123", receipt)
        self.assertIn("Abonos:", receipt)
        self.assertIn("ABN-01", receipt)
        self.assertIn("Notas: Entrega sabado", receipt)
        self.assertIn("Copias configuradas: 2", receipt)

    def test_builds_receipt_text_without_client(self) -> None:
        layaway = _build_layaway(with_client=False, with_payments=False)

        receipt = build_layaway_receipt_text(
            layaway=layaway,
            business_name="POS Uniformes",
        )

        self.assertIn("Codigo cliente: Manual / sin cliente", receipt)
        self.assertNotIn("Abonos:", receipt)


if __name__ == "__main__":
    unittest.main()
