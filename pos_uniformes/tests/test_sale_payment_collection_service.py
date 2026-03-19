from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.sale_payment_collection_service import (
    SalePaymentBusinessSnapshot,
    build_sale_payment_dialog_request,
    load_sale_payment_business_snapshot,
)


class SalePaymentCollectionServiceTests(unittest.TestCase):
    def test_build_sale_payment_dialog_request_returns_cash_without_business_snapshot(self) -> None:
        request = build_sale_payment_dialog_request("Efectivo")

        self.assertEqual(request.dialog_key, "cash")
        self.assertIsNone(request.business)

    def test_build_sale_payment_dialog_request_loads_business_snapshot_for_transfer(self) -> None:
        business = SalePaymentBusinessSnapshot(
            business_name="POS Uniformes",
            transfer_bank="Banco",
            transfer_beneficiary="Uniformes",
            transfer_clabe="123",
            transfer_instructions="Avisar en caja",
        )

        with patch(
            "pos_uniformes.services.sale_payment_collection_service.load_sale_payment_business_snapshot",
            return_value=business,
        ):
            request = build_sale_payment_dialog_request("Transferencia")

        self.assertEqual(request.dialog_key, "transfer")
        self.assertEqual(request.business, business)

    def test_build_sale_payment_dialog_request_loads_business_snapshot_for_mixed(self) -> None:
        business = SalePaymentBusinessSnapshot(
            business_name="POS Uniformes",
            transfer_bank="Banco",
            transfer_beneficiary="Uniformes",
            transfer_clabe="123",
            transfer_instructions="Avisar en caja",
        )

        with patch(
            "pos_uniformes.services.sale_payment_collection_service.load_sale_payment_business_snapshot",
            return_value=business,
        ):
            request = build_sale_payment_dialog_request("Mixto")

        self.assertEqual(request.dialog_key, "mixed")
        self.assertEqual(request.business, business)

    def test_load_sale_payment_business_snapshot_uses_defaults_when_loading_fails(self) -> None:
        with patch(
            "pos_uniformes.services.sale_payment_collection_service._resolve_sale_payment_collection_dependencies",
            side_effect=RuntimeError("sin base"),
        ):
            snapshot = load_sale_payment_business_snapshot()

        self.assertEqual(snapshot.business_name, "POS Uniformes")
        self.assertEqual(snapshot.transfer_clabe, "")

    def test_load_sale_payment_business_snapshot_maps_loaded_snapshot(self) -> None:
        class _SessionContext:
            def __enter__(self):
                return "session"

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch(
            "pos_uniformes.services.sale_payment_collection_service._resolve_sale_payment_collection_dependencies",
            return_value=(
                lambda: _SessionContext(),
                lambda session: SimpleNamespace(
                    business_name="Colegio",
                    transfer_bank="Bancomer",
                    transfer_beneficiary="Tienda",
                    transfer_clabe="999",
                    transfer_instructions="Compartir captura",
                ),
            ),
        ):
            snapshot = load_sale_payment_business_snapshot()

        self.assertEqual(snapshot.business_name, "Colegio")
        self.assertEqual(snapshot.transfer_bank, "Bancomer")
        self.assertEqual(snapshot.transfer_beneficiary, "Tienda")
        self.assertEqual(snapshot.transfer_clabe, "999")
        self.assertEqual(snapshot.transfer_instructions, "Compartir captura")


if __name__ == "__main__":
    unittest.main()
