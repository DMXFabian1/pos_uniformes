from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.layaway_detail_service import (
    LayawayDetailLineSnapshot,
    LayawayDetailSnapshot,
    LayawayPaymentLineSnapshot,
    load_layaway_detail_snapshot,
)


class LayawayDetailServiceTests(unittest.TestCase):
    def test_load_layaway_detail_snapshot_maps_selected_layaway(self) -> None:
        layaway = SimpleNamespace(
            folio="AP-001",
            estado=SimpleNamespace(value="ENTREGADO"),
            cliente=SimpleNamespace(codigo_cliente="C001"),
            cliente_nombre="Maria",
            cliente_telefono="555",
            total=Decimal("500.00"),
            total_abonado=Decimal("500.00"),
            saldo_pendiente=Decimal("0.00"),
            fecha_compromiso=datetime(2026, 3, 20, 15, 0),
            observacion="Observacion",
            detalles=[
                SimpleNamespace(
                    variante=SimpleNamespace(
                        sku="SKU-1",
                        producto=SimpleNamespace(nombre="Playera Deportiva | Patria | Deportivo | Playera #4"),
                    ),
                    cantidad=2,
                    precio_unitario=Decimal("250.00"),
                    subtotal_linea=Decimal("500.00"),
                )
            ],
            abonos=[
                SimpleNamespace(
                    created_at=datetime(2026, 3, 19, 10, 30),
                    monto=Decimal("500.00"),
                    referencia="REF-1",
                    usuario=SimpleNamespace(username="admin"),
                )
            ],
        )
        fake_apartado_service = SimpleNamespace(obtener_apartado=lambda session, layaway_id: layaway)
        fake_estado_apartado = SimpleNamespace(ENTREGADO=layaway.estado)
        fake_rol_usuario = SimpleNamespace(ADMIN="ADMIN", CAJERO="CAJERO")

        with patch(
            "pos_uniformes.services.layaway_detail_service._resolve_layaway_detail_dependencies",
            return_value=(fake_apartado_service, fake_estado_apartado, fake_rol_usuario),
        ):
            snapshot = load_layaway_detail_snapshot(
                SimpleNamespace(),
                layaway_id=10,
                current_role="ADMIN",
                classify_due=lambda fecha, estado: ("Vence 2026-03-20", "warning"),
            )

        self.assertEqual(
            snapshot,
            LayawayDetailSnapshot(
                folio="AP-001",
                estado="ENTREGADO",
                customer_code="C001",
                customer_name="Maria",
                customer_phone="555",
                total=Decimal("500.00"),
                total_paid=Decimal("500.00"),
                balance_due=Decimal("0.00"),
                commitment_label="2026-03-20",
                due_text="Vence 2026-03-20",
                due_tone="warning",
                notes_text="Observacion",
                detail_rows=(
                    LayawayDetailLineSnapshot(
                        sku="SKU-1",
                        product_name="Playera Deportiva | Patria | Deportivo | Playera",
                        quantity=2,
                        unit_price=Decimal("250.00"),
                        subtotal=Decimal("500.00"),
                    ),
                ),
                payment_rows=(
                    LayawayPaymentLineSnapshot(
                        created_at_label="2026-03-19 10:30",
                        amount=Decimal("500.00"),
                        reference="REF-1",
                        username="admin",
                    ),
                ),
                sale_ticket_enabled=True,
                whatsapp_enabled=True,
            ),
        )


if __name__ == "__main__":
    unittest.main()
