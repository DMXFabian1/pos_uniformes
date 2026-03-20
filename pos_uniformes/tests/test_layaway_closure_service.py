from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.layaway_closure_service import (
    LayawayDeliveryConfirmation,
    LayawayDeliveryResult,
    cancel_layaway,
    deliver_layaway,
    load_layaway_delivery_confirmation,
    settle_and_deliver_layaway,
)
from pos_uniformes.services.layaway_payment_service import LayawayPaymentInput


class LayawayClosureServiceTests(unittest.TestCase):
    def test_load_layaway_delivery_confirmation_builds_summary(self) -> None:
        apartado = SimpleNamespace(
            id=10,
            folio="AP-001",
            cliente=SimpleNamespace(codigo_cliente="CLI-001"),
            cliente_nombre="Maria",
            detalles=[
                SimpleNamespace(cantidad=2),
                SimpleNamespace(cantidad=1),
            ],
            total="439.50",
            total_abonado="439.50",
            saldo_pendiente="0.00",
        )
        fake_apartado_service = SimpleNamespace(
            obtener_apartado=lambda _session, layaway_id: apartado if layaway_id == 10 else None,
        )

        with patch(
            "pos_uniformes.services.layaway_closure_service._resolve_layaway_closure_dependencies",
            return_value=(fake_apartado_service, object(), object()),
        ):
            result = load_layaway_delivery_confirmation(object(), layaway_id=10)

        self.assertEqual(
            result,
            LayawayDeliveryConfirmation(
                layaway_id=10,
                layaway_folio="AP-001",
                customer_label="CLI-001 · Maria",
                items_count=2,
                pieces_count=3,
                total=result.total,
                total_paid=result.total_paid,
                balance_due=result.balance_due,
            ),
        )
        self.assertEqual(str(result.total), "439.50")
        self.assertEqual(str(result.total_paid), "439.50")
        self.assertEqual(str(result.balance_due), "0.00")

    def test_deliver_layaway_creates_sale_and_marks_delivered(self) -> None:
        usuario = object()
        apartado = SimpleNamespace(
            folio="AP-001",
            cliente=SimpleNamespace(codigo_cliente="CLI-001"),
            cliente_nombre="Maria",
            detalles=[SimpleNamespace(cantidad=2)],
            total="439.50",
        )
        sale = SimpleNamespace(folio="ENT-AP-001")
        session = SimpleNamespace(get=lambda model, item_id: usuario if item_id == 7 else None)
        fake_apartado_service = SimpleNamespace(
            obtener_apartado=lambda _session, layaway_id: apartado if layaway_id == 10 else None,
            entregar_apartado=lambda *args, **kwargs: None,
        )
        fake_venta_service = SimpleNamespace(crear_confirmada_desde_apartado=lambda **kwargs: sale)

        with patch(
            "pos_uniformes.services.layaway_closure_service._resolve_layaway_closure_dependencies",
            return_value=(fake_apartado_service, object(), fake_venta_service),
        ):
            result = deliver_layaway(SimpleNamespace(get=session.get), layaway_id=10, user_id=7)

        self.assertEqual(
            result,
            LayawayDeliveryResult(
                layaway_folio="AP-001",
                sale_folio="ENT-AP-001",
                customer_label="CLI-001 · Maria",
                items_count=1,
                pieces_count=2,
                total=result.total,
                payment_registered_amount=result.payment_registered_amount,
            ),
        )
        self.assertEqual(str(result.total), "439.50")
        self.assertEqual(str(result.payment_registered_amount), "0.00")

    def test_settle_and_deliver_layaway_registers_final_payment(self) -> None:
        usuario = object()
        apartado = SimpleNamespace(
            folio="AP-001",
            cliente=SimpleNamespace(codigo_cliente="CLI-001"),
            cliente_nombre="Maria",
            detalles=[SimpleNamespace(cantidad=2)],
            total="439.50",
        )
        sale = SimpleNamespace(folio="ENT-AP-001")
        session = SimpleNamespace(get=lambda model, item_id: usuario if item_id == 7 else None)
        registered_payments: list[object] = []

        def _registrar_abono(**kwargs):
            registered_payments.append(kwargs)

        fake_apartado_service = SimpleNamespace(
            obtener_apartado=lambda _session, layaway_id: apartado if layaway_id == 10 else None,
            registrar_abono=_registrar_abono,
            entregar_apartado=lambda *args, **kwargs: None,
        )
        fake_venta_service = SimpleNamespace(crear_confirmada_desde_apartado=lambda **kwargs: sale)

        with patch(
            "pos_uniformes.services.layaway_closure_service._resolve_layaway_closure_dependencies",
            return_value=(fake_apartado_service, object(), fake_venta_service),
        ):
            result = settle_and_deliver_layaway(
                SimpleNamespace(get=session.get),
                layaway_id=10,
                user_id=7,
                payment_input=LayawayPaymentInput(
                    amount="87.80",
                    payment_method="Efectivo",
                    cash_amount="87.80",
                    reference="",
                    notes="Liquidacion final",
                ),
            )

        self.assertEqual(len(registered_payments), 1)
        self.assertEqual(str(result.payment_registered_amount), "87.80")

    def test_cancel_layaway_uses_apartado_service(self) -> None:
        usuario = object()
        apartado = object()
        session = SimpleNamespace(get=lambda model, item_id: usuario if item_id == 7 else None)
        fake_apartado_service = SimpleNamespace(
            obtener_apartado=lambda _session, layaway_id: apartado if layaway_id == 10 else None,
            cancelar_apartado=lambda **kwargs: None,
        )

        with patch(
            "pos_uniformes.services.layaway_closure_service._resolve_layaway_closure_dependencies",
            return_value=(fake_apartado_service, object(), object()),
        ):
            cancel_layaway(SimpleNamespace(get=session.get), layaway_id=10, user_id=7, note="Motivo")


if __name__ == "__main__":
    unittest.main()
