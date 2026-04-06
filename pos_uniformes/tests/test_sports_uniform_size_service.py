from __future__ import annotations

import unittest

from pos_uniformes.services.sports_uniform_size_service import (
    build_sports_uniform_size_guidance,
    build_sports_uniform_size_hint,
    classify_playera_size_match,
    recommend_playera_sizes_for_pants,
)


class SportsUniformSizeServiceTests(unittest.TestCase):
    def test_recommend_playera_sizes_for_numeric_pants_size(self) -> None:
        self.assertEqual(
            recommend_playera_sizes_for_pants("14"),
            ("14", "16", "12"),
        )

    def test_recommend_playera_sizes_for_alpha_pants_size(self) -> None:
        self.assertEqual(
            recommend_playera_sizes_for_pants("MD"),
            ("MD", "GD", "CH-MD"),
        )

    def test_classify_playera_size_match_marks_exact_and_suggested(self) -> None:
        self.assertEqual(classify_playera_size_match("14", "14"), "exacta")
        self.assertEqual(classify_playera_size_match("14", "16"), "sugerida")

    def test_classify_playera_size_match_marks_atypical_when_outside_guidance(self) -> None:
        self.assertEqual(classify_playera_size_match("14", "CH"), "atipica")

    def test_build_size_guidance_keeps_selected_size_and_level(self) -> None:
        guidance = build_sports_uniform_size_guidance("MD", "GD")

        self.assertEqual(guidance.pants_size, "MD")
        self.assertEqual(guidance.selected_playera_size, "GD")
        self.assertEqual(guidance.match_level, "sugerida")

    def test_build_size_hint_mentions_atypical_selection(self) -> None:
        hint = build_sports_uniform_size_hint("14", "CH")

        self.assertIn("atipica", hint)
        self.assertIn("14", hint)
        self.assertIn("CH", hint)


if __name__ == "__main__":
    unittest.main()
