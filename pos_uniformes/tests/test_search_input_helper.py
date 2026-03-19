from __future__ import annotations

import unittest

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QApplication, QLineEdit

from pos_uniformes.ui.helpers.search_input_helper import (
    apply_search_suggestions,
    merge_search_completion,
)


class SearchInputHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_apply_search_suggestions_creates_and_updates_popup_controller(self) -> None:
        line_edit = QLineEdit()
        line_edit.show()
        line_edit.setFocus()
        line_edit.setText("sku")

        apply_search_suggestions(line_edit, ["sku:SKU-001", "Azul Marino"])

        controller = getattr(line_edit, "_search_suggestion_controller")
        popup = controller.popup
        self.assertEqual(popup.count(), 2)
        self.assertEqual(popup.item(0).text(), "sku:SKU-001")
        self.assertEqual(popup.item(1).text(), "Azul Marino")

        apply_search_suggestions(line_edit, ["producto:Pants"])

        self.assertEqual(popup.count(), 1)
        self.assertEqual(popup.item(0).text(), "producto:Pants")

    def test_merge_search_completion_replaces_only_last_term(self) -> None:
        self.assertEqual(
            merge_search_completion("marca:atlas col", "color:Azul Marino"),
            "marca:atlas color:Azul Marino",
        )
        self.assertEqual(
            merge_search_completion("sku:sku-001", "sku:SKU-001"),
            "sku:SKU-001",
        )

    def test_navigation_keeps_typed_text_while_using_arrow_keys(self) -> None:
        line_edit = QLineEdit()
        line_edit.show()
        line_edit.setFocus()
        line_edit.setText("ma")
        apply_search_suggestions(line_edit, ["marca:Atlas", "marca:Nike"])
        controller = getattr(line_edit, "_search_suggestion_controller")
        controller._anchor_text = "ma"
        controller.popup.show()
        controller.popup.setCurrentRow(0)

        handled = controller.eventFilter(
            line_edit,
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier),
        )

        self.assertTrue(handled)
        self.assertEqual(line_edit.text(), "ma")
        self.assertEqual(controller.popup.currentRow(), 1)

    def test_navigation_moves_up_and_down_without_collapsing_list(self) -> None:
        line_edit = QLineEdit()
        line_edit.show()
        line_edit.setFocus()
        line_edit.setText("pa")
        apply_search_suggestions(line_edit, ["Pants", "Playera", "Parka"])
        controller = getattr(line_edit, "_search_suggestion_controller")
        controller._anchor_text = "pa"
        controller.popup.show()
        controller.popup.setCurrentRow(0)

        controller.eventFilter(
            line_edit,
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier),
        )
        controller.eventFilter(
            line_edit,
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier),
        )

        self.assertEqual(controller.popup.count(), 3)
        self.assertEqual(controller.popup.currentRow(), 2)
        self.assertEqual(line_edit.text(), "pa")

        controller.eventFilter(
            line_edit,
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier),
        )

        self.assertEqual(controller.popup.currentRow(), 1)
        self.assertEqual(line_edit.text(), "pa")

    def test_navigation_commits_completion_on_enter(self) -> None:
        line_edit = QLineEdit()
        line_edit.show()
        line_edit.setFocus()
        line_edit.setText("marca:at co")
        apply_search_suggestions(line_edit, ["color:Azul Marino"])
        controller = getattr(line_edit, "_search_suggestion_controller")
        controller._anchor_text = "marca:at co"
        controller.popup.show()
        controller.popup.setCurrentRow(0)

        handled = controller.eventFilter(
            line_edit,
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier),
        )

        self.assertTrue(handled)
        self.assertEqual(line_edit.text(), "marca:at color:Azul Marino")
        self.assertFalse(controller.popup.isVisible())

    def test_mouse_click_commits_completion(self) -> None:
        line_edit = QLineEdit()
        line_edit.show()
        line_edit.setFocus()
        line_edit.setText("col")
        apply_search_suggestions(line_edit, ["color:Azul Marino"])
        controller = getattr(line_edit, "_search_suggestion_controller")
        controller._anchor_text = "col"
        rect = controller.popup.visualItemRect(controller.popup.item(0))

        handled = controller.eventFilter(
            controller.popup,
            QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(rect.center()),
                QPointF(rect.center()),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )

        self.assertTrue(handled)
        self.assertEqual(line_edit.text(), "color:Azul Marino")

    def test_popup_hides_when_suggestions_are_empty(self) -> None:
        line_edit = QLineEdit()
        line_edit.show()
        line_edit.setFocus()
        line_edit.setText("sku")
        apply_search_suggestions(line_edit, ["sku:SKU-001"])
        controller = getattr(line_edit, "_search_suggestion_controller")

        apply_search_suggestions(line_edit, [])

        self.assertEqual(controller.popup.count(), 0)
        self.assertFalse(controller.popup.isVisible())


if __name__ == "__main__":
    unittest.main()
