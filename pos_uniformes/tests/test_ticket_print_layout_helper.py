from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
    TICKET_FONT_POINT_SIZE,
    TICKET_TEXT_WIDTH_MM,
    build_ticket_document,
    build_ticket_print_font,
    millimeters_to_points,
)


class TicketPrintLayoutHelperTests(unittest.TestCase):
    def test_millimeters_to_points_uses_expected_conversion(self) -> None:
        self.assertAlmostEqual(millimeters_to_points(25.4), 72.0)

    def test_build_ticket_document_uses_80mm_text_width_and_fixed_font(self) -> None:
        document = build_ticket_document("Linea 1\nLinea 2")

        self.assertEqual(document.toPlainText(), "Linea 1\nLinea 2")
        self.assertAlmostEqual(document.textWidth(), millimeters_to_points(TICKET_TEXT_WIDTH_MM))
        self.assertEqual(document.defaultFont().pointSize(), TICKET_FONT_POINT_SIZE)
        self.assertTrue(document.defaultFont().bold())

    def test_build_ticket_document_respects_custom_text_width(self) -> None:
        document = build_ticket_document("Test", text_width_mm=60.0)

        self.assertAlmostEqual(document.textWidth(), millimeters_to_points(60.0))

    def test_build_ticket_print_font_is_bold(self) -> None:
        font = build_ticket_print_font()

        self.assertTrue(font.bold())
        self.assertEqual(font.pointSize(), TICKET_FONT_POINT_SIZE)


if __name__ == "__main__":
    unittest.main()
