from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.sale_checkout_action_service import (
    SaleCheckoutResult,
    complete_sale_checkout,
)


class SaleCheckoutActionServiceTests(unittest.TestCase):
    def test_complete_sale_checkout_confirms_sale_and_logs_manual_promo(self) -> None:
        usuario = object()
        cliente = object()
        venta = SimpleNamespace(
            subtotal=None,
            descuento_porcentaje=None,
            descuento_monto=None,
            total=None,
            observacion=None,
        )
        client_snapshot = SimpleNamespace(client=cliente)
        fake_checkout = SimpleNamespace(
            load_sale_client_checkout_snapshot=lambda session, selected_client_id: client_snapshot,
            resolve_sale_loyalty_transition_notice=lambda snapshot, build_notice: "Cambio de nivel",
        )
        manual_calls: list[dict[str, object]] = []
        fake_manual = SimpleNamespace(log_authorized_promo=lambda session, **kwargs: manual_calls.append(kwargs))
        confirm_calls: list[dict[str, object]] = []
        fake_venta_service = SimpleNamespace(
            crear_borrador=lambda **kwargs: _capture_sale_creation(kwargs, venta),
            confirmar_venta=lambda session, venta, movement_observacion=None: confirm_calls.append(
                {"venta": venta, "movement_observacion": movement_observacion}
            ),
        )
        _capture_sale_creation.target_service = fake_venta_service
        fake_item_input = lambda **kwargs: kwargs
        session = SimpleNamespace(get=lambda model, item_id: usuario if item_id == 7 else None)

        with patch(
            "pos_uniformes.services.sale_checkout_action_service._resolve_sale_checkout_action_dependencies",
            return_value=(object(), fake_venta_service, fake_item_input, fake_manual, fake_checkout),
        ):
            result = complete_sale_checkout(
                session,
                user_id=7,
                folio="V-001",
                sale_cart=[
                    {
                        "sku": "SKU-1",
                        "cantidad": 2,
                        "precio_unitario": Decimal("100.00"),
                        "precio_base": Decimal("189.00"),
                        "pricing_rule_label": "Conjunto deportivo 3pz",
                    }
                ],
                subtotal=Decimal("200.00"),
                discount_percent=Decimal("10.00"),
                applied_discount=Decimal("20.00"),
                total=Decimal("180.00"),
                selected_client_id=1,
                breakdown={
                    "loyalty_discount": Decimal("5.00"),
                    "promo_discount": Decimal("10.00"),
                    "winner_source": "PROMOCION_MANUAL",
                },
                payment_method="Efectivo",
                note_parts=["nota"],
                internal_note_parts=["Maqueta prueba deportivo 3pz: P2-001 + PLY-001"],
                build_notice=lambda *args: "Cambio de nivel",
            )

        self.assertEqual(
            result,
            SaleCheckoutResult(
                folio="V-001",
                total=Decimal("180.00"),
                payment_method="Efectivo",
                loyalty_transition_notice="Cambio de nivel",
            ),
        )
        self.assertEqual(venta.total, Decimal("180.00"))
        self.assertEqual(
            venta.observacion,
            "nota | Interno: Maqueta prueba deportivo 3pz: P2-001 + PLY-001",
        )
        self.assertEqual(
            confirm_calls,
            [
                {
                    "venta": venta,
                    "movement_observacion": "Maqueta prueba deportivo 3pz: P2-001 + PLY-001",
                }
            ],
        )
        self.assertEqual(len(manual_calls), 1)
        self.assertEqual(
            fake_venta_service.crear_borrador_kwargs["items"],
            [
                {
                    "sku": "SKU-1",
                    "cantidad": 2,
                    "precio_unitario": Decimal("100.00"),
                    "precio_base": Decimal("189.00"),
                    "pricing_rule_label": "Conjunto deportivo 3pz",
                }
            ],
        )


def _capture_sale_creation(kwargs: dict[str, object], venta: SimpleNamespace) -> SimpleNamespace:
    venta.observacion = kwargs.get("observacion")
    _capture_sale_creation.target_service.crear_borrador_kwargs = kwargs
    return venta


if __name__ == "__main__":
    unittest.main()
