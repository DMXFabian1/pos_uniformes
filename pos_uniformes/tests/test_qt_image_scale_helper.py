from __future__ import annotations

import unittest

from PyQt6.QtCore import QRect, QRectF, QSize, QSizeF
from PyQt6.QtGui import QImage

from pos_uniformes.ui.helpers.qt_image_scale_helper import (
    build_centered_paint_rect,
    normalize_printable_image,
    normalize_scaled_target_size,
)


class QtImageScaleHelperTests(unittest.TestCase):
    def test_normalize_scaled_target_size_converts_qsizef_to_qsize(self) -> None:
        normalized = normalize_scaled_target_size(QSizeF(804.0, 1034.0))

        self.assertEqual(normalized, QSize(804, 1034))

    def test_normalize_scaled_target_size_rounds_fractional_values(self) -> None:
        normalized = normalize_scaled_target_size(QSizeF(603.36, 775.2))

        self.assertEqual(normalized, QSize(603, 775))

    def test_normalize_scaled_target_size_clamps_non_positive_values(self) -> None:
        normalized = normalize_scaled_target_size(QSizeF(0.0, -12.4))

        self.assertEqual(normalized, QSize(1, 1))

    def test_build_centered_paint_rect_converts_qrectf_to_qrect(self) -> None:
        rect = build_centered_paint_rect(QRectF(6.0, 11.0, 804.0, 1034.0), QSize(804, 1034))

        self.assertEqual(rect, QRect(6, 11, 804, 1034))

    def test_build_centered_paint_rect_centers_smaller_content(self) -> None:
        rect = build_centered_paint_rect(QRectF(6.0, 11.0, 804.0, 1034.0), QSize(400, 600))

        self.assertEqual(rect, QRect(208, 228, 400, 600))

    def test_normalize_printable_image_converts_mono_to_grayscale(self) -> None:
        image = QImage(10, 10, QImage.Format.Format_Mono)

        normalized = normalize_printable_image(image)

        self.assertEqual(normalized.format(), QImage.Format.Format_Grayscale8)

    def test_normalize_printable_image_keeps_rgb32_unchanged(self) -> None:
        image = QImage(10, 10, QImage.Format.Format_RGB32)

        normalized = normalize_printable_image(image)

        self.assertEqual(normalized.format(), QImage.Format.Format_RGB32)


if __name__ == "__main__":
    unittest.main()
