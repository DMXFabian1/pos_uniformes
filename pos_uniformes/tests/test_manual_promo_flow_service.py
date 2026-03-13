from __future__ import annotations

from decimal import Decimal
import unittest

from pos_uniformes.services.manual_promo_flow_service import (
    apply_manual_promo_authorization,
    build_manual_promo_state,
    clear_manual_promo_state,
    current_manual_promo_percent,
    decide_manual_promo_change,
    resolve_manual_promo_transition,
)


class ManualPromoFlowServiceTests(unittest.TestCase):
    def test_clear_state_resets_authorization(self) -> None:
        state = clear_manual_promo_state()
        self.assertFalse(state.authorized)
        self.assertEqual(state.authorized_percent, Decimal("0.00"))

    def test_current_manual_promo_percent_requires_matching_selected_discount(self) -> None:
        state = build_manual_promo_state(authorized=True, authorized_percent=Decimal("15.00"))

        self.assertEqual(
            current_manual_promo_percent(selected_percent=Decimal("15.00"), state=state),
            Decimal("15.00"),
        )
        self.assertEqual(
            current_manual_promo_percent(selected_percent=Decimal("10.00"), state=state),
            Decimal("0.00"),
        )

    def test_decision_clears_when_selected_discount_is_zero(self) -> None:
        decision = decide_manual_promo_change(
            selected_percent=Decimal("0.00"),
            state=build_manual_promo_state(authorized=True, authorized_percent=Decimal("15.00")),
        )

        self.assertEqual(decision.action, "clear")
        self.assertEqual(decision.revert_percent, Decimal("15.00"))

    def test_decision_keeps_existing_authorization_when_same_percent_is_selected(self) -> None:
        decision = decide_manual_promo_change(
            selected_percent=Decimal("15.00"),
            state=build_manual_promo_state(authorized=True, authorized_percent=Decimal("15.00")),
        )

        self.assertEqual(decision.action, "keep")
        self.assertEqual(decision.revert_percent, Decimal("15.00"))

    def test_decision_requires_authorization_for_new_discount(self) -> None:
        decision = decide_manual_promo_change(
            selected_percent=Decimal("20.00"),
            state=build_manual_promo_state(authorized=True, authorized_percent=Decimal("15.00")),
        )

        self.assertEqual(decision.action, "authorize")
        self.assertEqual(decision.selected_percent, Decimal("20.00"))
        self.assertEqual(decision.revert_percent, Decimal("15.00"))

    def test_new_discount_without_previous_authorization_reverts_to_zero(self) -> None:
        decision = decide_manual_promo_change(
            selected_percent=Decimal("20.00"),
            state=build_manual_promo_state(authorized=False, authorized_percent=Decimal("0.00")),
        )

        self.assertEqual(decision.action, "authorize")
        self.assertFalse(decision.previous_state.authorized)
        self.assertEqual(decision.revert_percent, Decimal("0.00"))

    def test_authorization_applies_selected_discount(self) -> None:
        state = apply_manual_promo_authorization(Decimal("12.50"))

        self.assertTrue(state.authorized)
        self.assertEqual(state.authorized_percent, Decimal("12.50"))

    def test_selected_percent_must_match_authorized_percent_to_remain_active(self) -> None:
        state = apply_manual_promo_authorization(Decimal("12.50"))

        self.assertEqual(
            current_manual_promo_percent(selected_percent=Decimal("12.50"), state=state),
            Decimal("12.50"),
        )
        self.assertEqual(
            current_manual_promo_percent(selected_percent=Decimal("15.00"), state=state),
            Decimal("0.00"),
        )

    def test_transition_clears_manual_promo_state(self) -> None:
        decision = decide_manual_promo_change(
            selected_percent=Decimal("0.00"),
            state=build_manual_promo_state(authorized=True, authorized_percent=Decimal("15.00")),
        )

        transition = resolve_manual_promo_transition(
            decision=decision,
            authorization_granted=False,
            format_discount_label=lambda value: f"{value}%",
        )

        self.assertFalse(transition.next_state.authorized)
        self.assertEqual(transition.combo_percent, Decimal("0.00"))
        self.assertEqual(transition.feedback_message, "")

    def test_transition_reverts_when_authorization_is_rejected(self) -> None:
        decision = decide_manual_promo_change(
            selected_percent=Decimal("20.00"),
            state=build_manual_promo_state(authorized=True, authorized_percent=Decimal("15.00")),
        )

        transition = resolve_manual_promo_transition(
            decision=decision,
            authorization_granted=False,
            format_discount_label=lambda value: f"{value}%",
        )

        self.assertTrue(transition.next_state.authorized)
        self.assertEqual(transition.next_state.authorized_percent, Decimal("15.00"))
        self.assertEqual(transition.combo_percent, Decimal("15.00"))
        self.assertEqual(transition.feedback_message, "")

    def test_transition_applies_feedback_when_authorization_is_granted(self) -> None:
        decision = decide_manual_promo_change(
            selected_percent=Decimal("20.00"),
            state=build_manual_promo_state(authorized=False, authorized_percent=Decimal("0.00")),
        )

        transition = resolve_manual_promo_transition(
            decision=decision,
            authorization_granted=True,
            format_discount_label=lambda value: f"{int(value)}%",
        )

        self.assertTrue(transition.next_state.authorized)
        self.assertEqual(transition.next_state.authorized_percent, Decimal("20.00"))
        self.assertEqual(transition.combo_percent, Decimal("20.00"))
        self.assertEqual(
            transition.feedback_message,
            "Promocion manual 20% autorizada con codigo.",
        )
        self.assertEqual(transition.feedback_tone, "warning")
        self.assertEqual(transition.feedback_auto_clear_ms, 1800)
