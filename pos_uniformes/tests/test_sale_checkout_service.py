from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.sale_checkout_service import (
    SaleClientCheckoutSnapshot,
    load_sale_client_checkout_snapshot,
    resolve_sale_loyalty_transition_notice,
)


class SaleCheckoutServiceTests(unittest.TestCase):
    def test_load_sale_client_checkout_snapshot_returns_empty_without_client(self) -> None:
        snapshot = load_sale_client_checkout_snapshot(SimpleNamespace(get=lambda *_args: None), selected_client_id=None)

        self.assertIsNone(snapshot.client)
        self.assertEqual(snapshot.client_name_for_notice, "")

    def test_load_sale_client_checkout_snapshot_raises_when_client_missing(self) -> None:
        fake_loyalty = SimpleNamespace(
            coerce_level=lambda level: level,
            visual_spec=lambda level: SimpleNamespace(label=str(level)),
        )
        with patch(
            "pos_uniformes.services.sale_checkout_service._resolve_sale_checkout_dependencies",
            return_value=(object(), fake_loyalty),
        ):
            with self.assertRaisesRegex(ValueError, "No se pudo cargar el cliente seleccionado"):
                load_sale_client_checkout_snapshot(SimpleNamespace(get=lambda *_args: None), selected_client_id=14)

    def test_load_sale_client_checkout_snapshot_loads_previous_loyalty_state(self) -> None:
        client = SimpleNamespace(nombre="Maria", nivel_lealtad="LEAL", descuento_preferente=Decimal("10.00"))
        session = SimpleNamespace(get=lambda *_args: client)
        fake_loyalty = SimpleNamespace(
            coerce_level=lambda level: "LEAL",
            visual_spec=lambda level: SimpleNamespace(label="Leal"),
        )

        with patch(
            "pos_uniformes.services.sale_checkout_service._resolve_sale_checkout_dependencies",
            return_value=(object(), fake_loyalty),
        ):
            snapshot = load_sale_client_checkout_snapshot(session, selected_client_id=5)

        self.assertIs(snapshot.client, client)
        self.assertEqual(snapshot.previous_level, "LEAL")
        self.assertEqual(snapshot.previous_discount, Decimal("10.00"))
        self.assertEqual(snapshot.previous_level_label, "Leal")
        self.assertEqual(snapshot.client_name_for_notice, "Maria")

    def test_resolve_sale_loyalty_transition_notice_returns_empty_when_unchanged(self) -> None:
        client = SimpleNamespace(nombre="Maria", nivel_lealtad="LEAL", descuento_preferente=Decimal("10.00"))
        snapshot = SaleClientCheckoutSnapshot(
            client=client,
            previous_level="LEAL",
            previous_discount=Decimal("10.00"),
            previous_level_label="Leal",
            client_name_for_notice="Maria",
        )
        fake_loyalty = SimpleNamespace(
            coerce_level=lambda level: "LEAL",
            visual_spec=lambda level: SimpleNamespace(label="Leal"),
        )

        with patch(
            "pos_uniformes.services.sale_checkout_service._resolve_sale_checkout_dependencies",
            return_value=(object(), fake_loyalty),
        ):
            notice = resolve_sale_loyalty_transition_notice(
                snapshot,
                build_notice=lambda *_args: "should not happen",
            )

        self.assertEqual(notice, "")

    def test_resolve_sale_loyalty_transition_notice_builds_notice_when_changed(self) -> None:
        client = SimpleNamespace(nombre="Maria", nivel_lealtad="PRO", descuento_preferente=Decimal("15.00"))
        snapshot = SaleClientCheckoutSnapshot(
            client=client,
            previous_level="LEAL",
            previous_discount=Decimal("10.00"),
            previous_level_label="Leal",
            client_name_for_notice="Maria",
        )
        fake_loyalty = SimpleNamespace(
            coerce_level=lambda level: "PRO",
            visual_spec=lambda level: SimpleNamespace(label="Profesor"),
        )

        with patch(
            "pos_uniformes.services.sale_checkout_service._resolve_sale_checkout_dependencies",
            return_value=(object(), fake_loyalty),
        ):
            notice = resolve_sale_loyalty_transition_notice(
                snapshot,
                build_notice=lambda client_name, previous_label, new_label, new_discount: (
                    f"{client_name}:{previous_label}:{new_label}:{new_discount}"
                ),
            )

        self.assertEqual(notice, "Maria:Leal:Profesor:15.00")


if __name__ == "__main__":
    unittest.main()
