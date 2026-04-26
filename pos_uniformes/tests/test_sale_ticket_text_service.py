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
    variante = SimpleNamespace(sku="SKU0001", producto=producto, talla="CH", color="Azul")
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
        self.assertIn("12/03/2026 18:35", ticket)
        self.assertIn("Efectivo", ticket)
        self.assertIn("Maria Fernanda", ticket)
        self.assertIn("CLI-001", ticket)
        self.assertNotIn("Telefono", ticket)
        self.assertNotIn("Usuario:", ticket)
        self.assertNotIn("Estado:", ticket)
        self.assertIn("ARTICULOS", ticket)
        self.assertIn("Playera deportiva", ticket)
        self.assertIn("SKU0001", ticket)
        self.assertIn("Talla CH", ticket)
        self.assertIn("$199.00", ticket)
        self.assertIn("Subtotal:", ticket)
        self.assertIn("Descuento 10.00%:", ticket)
        self.assertIn("-$19.90", ticket)
        self.assertIn("TOTAL A PAGAR:", ticket)
        self.assertIn("$179.10", ticket)
        self.assertIn("Promo autorizada", ticket)
        self.assertNotIn("Metodo de pago:", ticket)
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

        self.assertNotIn("Maria Fernanda", ticket)
        self.assertNotIn("CLI-001", ticket)
        self.assertIn("Subtotal:", ticket)
        self.assertIn("$199.00", ticket)
        self.assertIn("Descuento 15.00%:", ticket)
        self.assertIn("-$29.85", ticket)
        self.assertIn("$169.15", ticket)

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

        self.assertIn("Subtotal:", ticket)
        self.assertIn("$199.00", ticket)
        self.assertIn("TOTAL A PAGAR:", ticket)
        self.assertNotIn("Descuento", ticket)
        self.assertNotIn("Notas:", ticket)
        self.assertNotIn("Maria Fernanda", ticket)

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

        self.assertIn("Efectivo", ticket)
        self.assertIn("Beneficio: Lealtad Profesor 15%", ticket)
        self.assertIn("Recibido: 200.00", ticket)
        self.assertIn("Cambio: 30.85", ticket)
        self.assertNotIn("Lealtad Profesor: 15%", ticket)
        self.assertNotIn("Descuento aplicado: 29.85", ticket)
        self.assertNotIn("Sin referencia", ticket)

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

        self.assertIn("Descuento 15.00%:", ticket)
        self.assertIn("-$29.85", ticket)
        self.assertIn("Ajuste:", ticket)
        self.assertIn("-0.15", ticket)
        self.assertIn("$169.00", ticket)
        self.assertIn("Cambio: 31.00", ticket)
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

        self.assertIn("Descuento 15.00%:", ticket)
        self.assertIn("-$29.85", ticket)
        self.assertIn("Ajuste:", ticket)
        self.assertIn("-0.15", ticket)
        self.assertIn("$169.00", ticket)

    def test_omits_internal_operational_notes_from_customer_ticket(self) -> None:
        sale = _build_sale(
            with_client=False,
            stored_discount_percent="0.00",
            stored_discount_amount="0.00",
            total="199.00",
            observacion=(
                "Metodo de pago: Efectivo | Cambio: 1.00 | "
                "Interno: Maqueta prueba deportivo 3pz: P2-001 + PLY-001"
            ),
        )

        ticket = build_sale_ticket_text(
            sale=sale,
            business_name="POS Uniformes",
        )

        self.assertIn("Cambio: 1.00", ticket)
        self.assertNotIn("Interno:", ticket)

    def test_uses_snapshots_for_manual_sale_lines_without_variant(self) -> None:
        sale = SimpleNamespace(
            folio="VTA-009",
            created_at=datetime(2026, 4, 10, 14, 20),
            usuario=SimpleNamespace(username="admin"),
            estado=SimpleNamespace(value="CONFIRMADA"),
            cliente=None,
            detalles=[
                SimpleNamespace(
                    variante=None,
                    sku_snapshot="SIN-CODIGO",
                    descripcion_snapshot="Venta manual",
                    cantidad=1,
                    precio_unitario=Decimal("75.00"),
                    subtotal_linea=Decimal("75.00"),
                )
            ],
            subtotal=Decimal("75.00"),
            descuento_porcentaje=Decimal("0.00"),
            descuento_monto=Decimal("0.00"),
            total=Decimal("75.00"),
            observacion="Metodo de pago: Efectivo",
        )

        ticket = build_sale_ticket_text(
            sale=sale,
            business_name="POS Uniformes",
        )

        self.assertIn("Venta manual", ticket)
        self.assertIn("SIN-CODIGO", ticket)
        self.assertIn("$75.00", ticket)


if __name__ == "__main__":
    unittest.main()
