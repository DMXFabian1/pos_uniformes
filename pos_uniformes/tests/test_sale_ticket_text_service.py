from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from pos_uniformes.services.sale_ticket_text_service import build_sale_ticket_text


def _build_sale(
    *,
    with_client: bool,
    stored_discount_percent: str,
    stored_discount_amount: str,
    total: str,
    observacion: str = "",
) -> SimpleNamespace:
    cliente = None
    if with_client:
        cliente = SimpleNamespace(
            nombre="Maria Fernanda",
            codigo_cliente="CLI-001",
            telefono="5512345678",
        )

    producto = SimpleNamespace(nombre="Playera deportiva")
    variante = SimpleNamespace(sku="SKU0001", producto=producto)
    detalle = SimpleNamespace(
        variante=variante,
        cantidad=1,
        precio_unitario=Decimal("199.00"),
        subtotal_linea=Decimal("199.00"),
    )
    return SimpleNamespace(
        folio="VTA-001",
        created_at=datetime(2026, 3, 12, 18, 35),
        usuario=SimpleNamespace(username="admin"),
        estado=SimpleNamespace(value="CONFIRMADA"),
        cliente=cliente,
        detalles=[detalle],
        subtotal=Decimal("199.00"),
        descuento_porcentaje=Decimal(stored_discount_percent),
        descuento_monto=Decimal(stored_discount_amount),
        total=Decimal(total),
        observacion=observacion,
    )


class SaleTicketTextServiceTests(unittest.TestCase):
    def test_builds_ticket_text_for_sale_with_client_and_stored_discount(self) -> None:
        sale = _build_sale(
            with_client=True,
            stored_discount_percent="10.00",
            stored_discount_amount="19.90",
            total="179.10",
            observacion="Metodo de pago: Efectivo | Promo autorizada",
        )

        ticket = build_sale_ticket_text(
            sale=sale,
            business_name="POS Uniformes",
            business_phone="5550000000",
            business_address="Centro",
            ticket_footer="Gracias por tu compra.",
            preferred_printer="Caja 1",
            ticket_copies=2,
        )

        self.assertIn("POS Uniformes", ticket)
        self.assertIn("Forma de pago: Efectivo", ticket)
        self.assertIn("Cliente: Maria Fernanda", ticket)
        self.assertIn("Codigo cliente: CLI-001", ticket)
        self.assertNotIn("Telefono cliente:", ticket)
        self.assertNotIn("Usuario:", ticket)
        self.assertNotIn("Estado:", ticket)
        self.assertIn("Articulos", ticket)
        self.assertIn("- Playera deportiva | SKU0001 | 1 x 199.00 = 199.00", ticket)
        self.assertIn("Subtotal: 199.00", ticket)
        self.assertIn("Descuento aplicado: 10.00% (-19.90)", ticket)
        self.assertIn("Total a pagar: 179.10", ticket)
        self.assertIn("Notas:\n- Promo autorizada", ticket)
        self.assertNotIn("Notas: Metodo de pago:", ticket)
        self.assertNotIn("Copias configuradas:", ticket)
        self.assertNotIn("Impresora preferida:", ticket)

    def test_reconstructs_discount_for_old_sale_without_client(self) -> None:
        sale = _build_sale(
            with_client=False,
            stored_discount_percent="0.00",
            stored_discount_amount="0.00",
            total="169.15",
        )

        ticket = build_sale_ticket_text(
            sale=sale,
            business_name="POS Uniformes",
        )

        self.assertNotIn("Cliente:", ticket)
        self.assertNotIn("Codigo cliente:", ticket)
        self.assertNotIn("Forma de pago:", ticket)
        self.assertIn("Subtotal: 199.00", ticket)
        self.assertIn("Descuento aplicado: 15.00% (-29.85)", ticket)
        self.assertIn("Total a pagar: 169.15", ticket)
        self.assertNotIn("Impresora preferida:", ticket)

    def test_keeps_simple_output_for_sale_without_discount_or_notes(self) -> None:
        sale = _build_sale(
            with_client=False,
            stored_discount_percent="0.00",
            stored_discount_amount="0.00",
            total="199.00",
        )

        ticket = build_sale_ticket_text(
            sale=sale,
            business_name="POS Uniformes",
            ticket_footer="Gracias por tu compra.",
        )

        self.assertIn("Subtotal: 199.00", ticket)
        self.assertIn("Descuento aplicado: 0.00% (-0.00)", ticket)
        self.assertIn("Total a pagar: 199.00", ticket)
        self.assertNotIn("Notas:", ticket)
        self.assertNotIn("Cliente:", ticket)

    def test_simplifies_operational_notes_for_customer_ticket(self) -> None:
        sale = _build_sale(
            with_client=True,
            stored_discount_percent="15.00",
            stored_discount_amount="29.85",
            total="169.15",
            observacion=(
                "Metodo de pago: Efectivo | Descuento: 15.00% | Lealtad Profesor: 15% | "
                "Beneficio aplicado: Lealtad Profesor 15% | Descuento aplicado: 29.85 | "
                "Recibido: 200.00 | Cambio: 30.85 | Referencia: Sin referencia"
            ),
        )

        ticket = build_sale_ticket_text(
            sale=sale,
            business_name="POS Uniformes",
        )

        self.assertIn("Forma de pago: Efectivo", ticket)
        self.assertIn("Notas:\n- Beneficio: Lealtad Profesor 15%\n- Recibido: 200.00\n- Cambio: 30.85", ticket)
        self.assertNotIn("Lealtad Profesor: 15%", ticket)
        self.assertNotIn("Descuento aplicado: 29.85", ticket)
        self.assertNotIn("Referencia: Sin referencia", ticket)

    def test_shows_rounding_adjustment_as_separate_line_when_present(self) -> None:
        sale = _build_sale(
            with_client=False,
            stored_discount_percent="15.00",
            stored_discount_amount="29.85",
            total="169.00",
            observacion="Metodo de pago: Efectivo | Ajuste redondeo: -0.15 | Cambio: 31.00",
        )

        ticket = build_sale_ticket_text(
            sale=sale,
            business_name="POS Uniformes",
        )

        self.assertIn("Descuento aplicado: 15.00% (-29.85)", ticket)
        self.assertIn("Ajuste: -0.15", ticket)
        self.assertIn("Total a pagar: 169.00", ticket)
        self.assertIn("Notas:\n- Cambio: 31.00", ticket)
        self.assertNotIn("Ajuste redondeo:", ticket)

    def test_reconstructs_discount_correctly_when_rounding_adjustment_is_present(self) -> None:
        sale = _build_sale(
            with_client=False,
            stored_discount_percent="0.00",
            stored_discount_amount="0.00",
            total="169.00",
            observacion="Metodo de pago: Efectivo | Ajuste redondeo: -0.15",
        )

        ticket = build_sale_ticket_text(
            sale=sale,
            business_name="POS Uniformes",
        )

        self.assertIn("Descuento aplicado: 15.00% (-29.85)", ticket)
        self.assertIn("Ajuste: -0.15", ticket)
        self.assertIn("Total a pagar: 169.00", ticket)


if __name__ == "__main__":
    unittest.main()
