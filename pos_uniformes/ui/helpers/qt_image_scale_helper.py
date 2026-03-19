"""Helpers para normalizar tamanos Qt antes de escalar imagenes."""

from __future__ import annotations

from math import isfinite

from PyQt6.QtCore import QRect, QRectF, QSize, QSizeF
from PyQt6.QtGui import QImage


def normalize_scaled_target_size(raw_size: QSize | QSizeF) -> QSize:
    """Convierte QSizeF a QSize para APIs de Qt que solo aceptan enteros."""
    if isinstance(raw_size, QSize):
        return raw_size
    if isinstance(raw_size, QSizeF):
        width = raw_size.width()
        height = raw_size.height()
    else:
        width = float(raw_size.width())
        height = float(raw_size.height())

    if not isfinite(width) or width <= 0:
        width = 1
    if not isfinite(height) or height <= 0:
        height = 1
    return QSize(max(1, round(width)), max(1, round(height)))


def build_centered_paint_rect(raw_rect: QRect | QRectF, content_size: QSize) -> QRect:
    """Genera un QRect entero y centrado para dibujar sobre QPainter."""
    if isinstance(raw_rect, QRect):
        x = raw_rect.x()
        y = raw_rect.y()
        width = raw_rect.width()
        height = raw_rect.height()
    else:
        x = raw_rect.x()
        y = raw_rect.y()
        width = raw_rect.width()
        height = raw_rect.height()

    normalized_size = normalize_scaled_target_size(content_size)
    x_pos = int(round(x + max(0.0, (width - normalized_size.width()) / 2)))
    y_pos = int(round(y + max(0.0, (height - normalized_size.height()) / 2)))
    return QRect(x_pos, y_pos, normalized_size.width(), normalized_size.height())


def normalize_printable_image(image: QImage) -> QImage:
    """Convierte imagenes mono/indice a un formato estable para QPrinter."""
    if image.format() in {
        QImage.Format.Format_Mono,
        QImage.Format.Format_MonoLSB,
        QImage.Format.Format_Indexed8,
    }:
        return image.convertToFormat(QImage.Format.Format_Grayscale8)
    return image
