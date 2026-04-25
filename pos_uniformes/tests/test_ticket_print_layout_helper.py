from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
    TICKET_FONT_POINT_SIZE,
    TICKET_TEXT_WIDTH_MM,
    build_ticket_document,
    millimeters_to_points,
)


class TicketPrintLayoutHelperTests(unittest.TestCase):
    def test_millimeters_to_points_uses_expected_conversion(self) -> None:
        self.assertAlmostEqual(millimeters_to_points(25.4), 72.0)

    def test_build_ticket_document_uses_80mm_text_width_and_correct_font(self) -> None:
        html = "<html><body><p>Linea 1</p><p>Linea 2</p></body></html>"
        document = build_ticket_document(html)

        self.assertAlmostEqual(document.textWidth(), millimeters_to_points(TICKET_TEXT_WIDTH_MM))
        self.assertEqual(document.defaultFont().pointSize(), TICKET_FONT_POINT_SIZE)

    def test_build_ticket_document_respects_custom_text_width(self) -> None:
        html = "<html><body><p>Test</p></body></html>"
        document = build_ticket_document(html, text_width_mm=60.0)

        self.assertAlmostEqual(document.textWidth(), millimeters_to_points(60.0))


if __name__ == "__main__":
    unittest.main()
