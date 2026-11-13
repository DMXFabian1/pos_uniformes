from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.sale_client_sync_service import SaleClientSyncState
from pos_uniformes.services.sale_discount_context_service import (
    SaleDiscountContext,
    build_sale_discount_context,
    calculate_sale_discount_pricing,
    calculate_sale_discount_totals,
    clear_sale_manual_promo_snapshot,
    load_sale_discount_presets,
    resolve_sale_client_discount_ui_state,
    resolve_sale_manual_discount_transition,
    verify_sale_manual_promo_code,
)
from pos_uniformes.services.sale_discount_service import format_discount_label, normalize_discount_value


class SaleDiscountContextServiceTests(unittest.TestCase):
    def test_load_sale_discount_presets_es_lista_fija_sin_leer_configuracion(self) -> None:
        # 2026-11-12, Daniel: «el nivel viejo retíralo». Las opciones de la
        # promo manual ya no salen de discount_basico/leal/profesor/mayorista.
        presets = load_sale_discount_presets(object(), normalize_discount_value=normalize_discount_value)
        self.assertEqual(
            presets,
            [Decimal("5.00"), Decimal("10.00"), Decimal("15.00"), Decimal("20.00")],
        )
        self.assertEqual(
            load_sale_discount_presets(None, normalize_discount_value=normalize_discount_value),
            presets,
        )

    def test_load_sale_discount_presets_no_consulta_business_settings(self) -> None:
        with patch(
            "pos_uniformes.services.business_settings_service.BusinessSettingsService.get_or_create",
            side_effect=AssertionError("no debe leer configuracion_negocio"),
        ):
            presets = load_sale_discount_presets(object(), normalize_discount_value=normalize_discount_value)
        self.assertEqual(len(presets), 4)

    def test_resolve_sale_client_discount_ui_state(self) -> None:
        fake_module = SimpleNamespace(
            resolve_sale_selected_client_sync_state=lambda session, **kwargs: SaleClientSyncState(
                locked=True,
                discount_percent=Decimal("12.50"),
                source_label="Profesor",
            )
        )
        with patch(
            "pos_uniformes.services.sale_discount_context_service._resolve_sale_client_discount_ui_dependencies",
            return_value=fake_module,
        ):
            ui_state = resolve_sale_client_discount_ui_state(
                object(),
                selected_client_id=7,
                reset_manual=True,
                normalize_discount_value=normalize_discount_value,
                format_discount_label=format_discount_label,
            )

        self.assertEqual(ui_state.combo_discount_percent, Decimal("0.00"))
        self.assertTrue(ui_state.clear_manual_promo)
        self.assertTrue(ui_state.lock_state.locked)

    def test_resolve_sale_manual_discount_transition(self) -> None:
        transition = resolve_sale_manual_discount_transition(
            selected_percent=Decimal("20.00"),
            authorized=False,
            authorized_percent=Decimal("0.00"),
            format_discount_label=format_discount_label,
            authorize_manual_promo=lambda promo: promo == Decimal("20.00"),
        )
        self.assertTrue(transition.next_state.authorized)
        self.assertEqual(transition.combo_percent, Decimal("20.00"))

    def test_verify_sale_manual_promo_code_raises_on_invalid_code(self) -> None:
        fake_service = SimpleNamespace(verify_authorization_code=lambda session, code: False)
        with patch(
            "pos_uniformes.services.sale_discount_context_service._resolve_sale_manual_promo_dependencies",
            return_value=fake_service,
        ):
            with self.assertRaisesRegex(ValueError, "Codigo invalido"):
                verify_sale_manual_promo_code(object(), "bad")

    def test_build_sale_discount_context_and_calculations(self) -> None:
        context = build_sale_discount_context(
            locked_to_client=True,
            locked_discount_percent=Decimal("15.00"),
            locked_source_label="Leal",
            selected_discount_percent=Decimal("10.00"),
            manual_promo_authorized=True,
            manual_promo_authorized_percent=Decimal("10.00"),
        )

        self.assertEqual(
            context,
            SaleDiscountContext(
                loyalty_discount=Decimal("15.00"),
                promo_discount=Decimal("10.00"),
                effective_discount=Decimal("15.00"),
                breakdown=context.breakdown,
            ),
        )
        self.assertEqual(context.breakdown["winner_source"], "LEALTAD")

        cart = [
            {"precio_unitario": Decimal("100.00"), "cantidad": 2},
        ]
        totals = calculate_sale_discount_totals(
            cart,
            locked_to_client=True,
            locked_discount_percent=Decimal("15.00"),
            selected_discount_percent=Decimal("10.00"),
            manual_promo_authorized=True,
            manual_promo_authorized_percent=Decimal("10.00"),
        )
        pricing = calculate_sale_discount_pricing(
            cart,
            locked_to_client=True,
            locked_discount_percent=Decimal("15.00"),
            selected_discount_percent=Decimal("10.00"),
            manual_promo_authorized=True,
            manual_promo_authorized_percent=Decimal("10.00"),
        )

        self.assertEqual(totals[0], Decimal("200.00"))
        self.assertEqual(pricing.discount_percent, Decimal("15.00"))

    def test_clear_sale_manual_promo_snapshot(self) -> None:
        state = clear_sale_manual_promo_snapshot()
        self.assertFalse(state.authorized)
        self.assertEqual(state.authorized_percent, Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
