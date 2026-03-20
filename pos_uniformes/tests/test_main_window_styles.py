from __future__ import annotations

import unittest

from pos_uniformes.ui.styles.main_window_control_styles import (
    build_main_window_control_styles,
)
from pos_uniformes.ui.styles.main_window_hero_cashier_styles import (
    build_main_window_hero_cashier_styles,
)
from pos_uniformes.ui.styles.main_window_inventory_analytics_styles import (
    build_main_window_inventory_analytics_styles,
)
from pos_uniformes.ui.styles.main_window_styles import build_main_window_stylesheet


class MainWindowStylesTests(unittest.TestCase):
    def test_builds_main_window_stylesheet(self) -> None:
        stylesheet = build_main_window_stylesheet()

        self.assertIn("QMainWindow, QWidget", stylesheet)
        self.assertIn("#cashierFeedbackLabel[tone=\"warning\"]", stylesheet)
        self.assertIn("QPushButton#toolbarAccentButton", stylesheet)
        self.assertIn("#qrPreview", stylesheet)
        self.assertIn("#kpiCard[tone=\"warning\"]", stylesheet)

    def test_builds_control_style_section(self) -> None:
        stylesheet = build_main_window_control_styles()

        self.assertIn("QPushButton#inventoryActionButton", stylesheet)
        self.assertIn("QLineEdit, QComboBox, QSpinBox, QTextEdit", stylesheet)
        self.assertIn("#dataTable", stylesheet)

    def test_builds_hero_cashier_style_section(self) -> None:
        stylesheet = build_main_window_hero_cashier_styles()

        self.assertIn("#heroPanel", stylesheet)
        self.assertIn("#cashierFeedbackLabel[tone=\"danger\"]", stylesheet)
        self.assertIn("#cashierTotalValue", stylesheet)

    def test_builds_inventory_analytics_style_section(self) -> None:
        stylesheet = build_main_window_inventory_analytics_styles()

        self.assertIn("#inventoryStatusBadge[tone=\"warning\"]", stylesheet)
        self.assertIn("#inventoryCounterChip", stylesheet)
        self.assertIn("#analyticsFlagCard[tone=\"positive\"]", stylesheet)


if __name__ == "__main__":
    unittest.main()
