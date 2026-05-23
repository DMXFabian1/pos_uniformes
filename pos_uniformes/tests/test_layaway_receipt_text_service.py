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
        subtotal=Decimal("397.50"),
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
        self.assertIn("Folio:", receipt)
        self.assertIn("APA-001", receipt)
        self.assertIn("13/03/2026 09:30", receipt)
        self.assertIn("20/03/2026", receipt)
        self.assertIn("Maria Fernanda", receipt)
        self.assertIn("PRODUCTOS", receipt)
        self.assertIn("Playera", receipt)
        self.assertIn("$398.00", receipt)
        self.assertIn("$0.50", receipt)
        self.assertIn("$100.00", receipt)
        self.assertIn("SALDO PENDIENTE:", receipt)
        self.assertIn("$298.00", receipt)
        self.assertIn("Abonos registrados", receipt)
        self.assertIn("ABN-01", receipt)
        self.assertIn("Entrega sabado", receipt)
        self.assertIn("Conserve su comprobante.", receipt)
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

        self.assertIn("Maria Fernanda", receipt)
        self.assertNotIn("Abonos registrados", receipt)
        self.assertNotIn("Codigo cliente:", receipt)

    def test_filters_internal_layaway_notes_from_customer_receipt(self) -> None:
        layaway = _build_layaway(with_client=True, with_payments=False)
        layaway.observacion = "Creado desde Caja. | Ambiente de pruebas | Entrega sabado | Interno: nota"

        receipt = build_layaway_receipt_text(
            layaway=layaway,
            business_name="POS Uniformes",
        )

        self.assertIn("Notas:", receipt)
        self.assertIn("Entrega sabado", receipt)
        self.assertNotIn("Creado desde Caja", receipt)
        self.assertNotIn("Ambiente de pruebas", receipt)
        self.assertNotIn("Interno:", receipt)

    def test_marks_three_piece_playera_in_customer_receipt(self) -> None:
        layaway = _build_layaway(with_client=True, with_payments=False)
        layaway.detalles[0].precio_unitario = Decimal("100.00")
        layaway.detalles[0].subtotal_linea = Decimal("200.00")
        layaway.detalles[0].variante.producto.nombre = "Playera deportiva"
        layaway.detalles[0].variante.producto.escuela = SimpleNamespace(nombre="Patria")
        layaway.detalles[0].variante.producto.tipo_prenda = SimpleNamespace(nombre="Deportivo")
        layaway.detalles[0].variante.producto.tipo_pieza = SimpleNamespace(nombre="Playera")

        receipt = build_layaway_receipt_text(
            layaway=layaway,
            business_name="POS Uniformes",
        )

        self.assertIn("Playera deportiva (Conjunto", receipt)
        self.assertIn("deportivo 3pz - Patria)", receipt)


if __name__ == "__main__":
    unittest.main()
