from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.listing_visibility_helper import (
    matches_active_state,
    matches_fallback_duplicate,
    matches_origin_legacy,
    matches_selected_values,
)


class ListingVisibilityHelperTests(unittest.TestCase):
    def test_matches_selected_values_accepts_empty_filter(self) -> None:
        self.assertTrue(matches_selected_values("General", ()))

    def test_matches_selected_values_uses_fallback_for_none(self) -> None:
        self.assertTrue(matches_selected_values(None, ("General",), fallback="General"))

    def test_matches_active_state_supports_active_and_inactive(self) -> None:
        self.assertTrue(matches_active_state(True, "active"))
        self.assertTrue(matches_active_state(False, "inactive"))
        self.assertFalse(matches_active_state(False, "active"))

    def test_matches_origin_legacy_supports_native_filter(self) -> None:
        self.assertTrue(matches_origin_legacy(False, "native"))
        self.assertFalse(matches_origin_legacy(True, "native"))

    def test_matches_fallback_duplicate_supports_exclude_filter(self) -> None:
        self.assertTrue(matches_fallback_duplicate(False, "fallback_exclude"))
        self.assertFalse(matches_fallback_duplicate(True, "fallback_exclude"))


if __name__ == "__main__":
    unittest.main()
