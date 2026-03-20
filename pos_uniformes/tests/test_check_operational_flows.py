from __future__ import annotations

import unittest
from unittest.mock import patch

from pos_uniformes.scripts.check_operational_flows import (
    FLOW_GROUPS,
    _build_suite,
    _normalize_requested_groups,
    main,
)


class CheckOperationalFlowsTests(unittest.TestCase):
    def test_normalize_requested_groups_returns_all_when_empty(self) -> None:
        self.assertEqual(_normalize_requested_groups([]), list(FLOW_GROUPS.keys()))

    def test_normalize_requested_groups_rejects_unknown_group(self) -> None:
        with self.assertRaisesRegex(ValueError, "Grupo desconocido"):
            _normalize_requested_groups(["desconocido"])

    def test_build_suite_includes_tests_from_selected_group(self) -> None:
        suite = _build_suite(["caja_cobro"])
        self.assertGreater(suite.countTestCases(), 0)

    def test_main_returns_zero_for_list_mode(self) -> None:
        self.assertEqual(main(["--list"]), 0)

    def test_main_returns_two_for_unknown_group(self) -> None:
        self.assertEqual(main(["grupo-invalido"]), 2)

    def test_main_returns_zero_when_runner_succeeds(self) -> None:
        fake_result = type("FakeResult", (), {"wasSuccessful": lambda self: True, "testsRun": 5})()

        with patch("pos_uniformes.scripts.check_operational_flows._build_suite", return_value=unittest.TestSuite()), patch(
            "unittest.TextTestRunner.run",
            return_value=fake_result,
        ):
            self.assertEqual(main(["caja_cobro"]), 0)


if __name__ == "__main__":
    unittest.main()
