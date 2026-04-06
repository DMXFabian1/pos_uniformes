from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.window_close_helper import build_main_window_close_decision


class WindowCloseHelperTests(unittest.TestCase):
    def test_busy_state_blocks_close(self) -> None:
        decision = build_main_window_close_decision(is_busy=True)

        self.assertTrue(decision.should_block)
        self.assertIn("proceso", decision.message.lower())

    def test_idle_state_prompts_confirmation(self) -> None:
        decision = build_main_window_close_decision(is_busy=False)

        self.assertFalse(decision.should_block)
        self.assertIn("continuar", decision.message.lower())


if __name__ == "__main__":
    unittest.main()
