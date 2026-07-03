"""Tests del excepthook global del satelite."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from pos_uniformes.utils.satellite_excepthook import (
    append_to_error_log,
    format_unhandled_exception,
    install_satellite_excepthook,
)


def _make_exc_info() -> tuple[type[BaseException], BaseException, object]:
    try:
        raise RuntimeError("wrapped C/C++ object of type QPushButton has been deleted")
    except RuntimeError:
        return sys.exc_info()  # type: ignore[return-value]


class FormatTests(unittest.TestCase):
    def test_includes_stamp_type_and_message(self) -> None:
        exc_type, exc, tb = _make_exc_info()
        entry = format_unhandled_exception(
            exc_type, exc, tb, now=datetime(2026, 7, 3, 14, 0, 0)
        )
        self.assertIn("[2026-07-03 14:00:00]", entry)
        self.assertIn("RuntimeError", entry)
        self.assertIn("has been deleted", entry)
        self.assertIn("Traceback", entry)
        self.assertTrue(entry.endswith("\n\n"))


class AppendTests(unittest.TestCase):
    def test_creates_parent_dirs_and_appends(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data" / "satellite_errors.log"
            append_to_error_log("uno\n", path)
            append_to_error_log("dos\n", path)
            self.assertEqual(path.read_text(encoding="utf-8"), "uno\ndos\n")

    def test_truncates_when_log_grows_too_big(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "satellite_errors.log"
            path.write_text("x" * (512 * 1024 + 1), encoding="utf-8")
            append_to_error_log("nuevo\n", path)
            self.assertEqual(path.read_text(encoding="utf-8"), "nuevo\n")

    def test_unwritable_path_does_not_raise(self) -> None:
        # Un log roto jamas debe tumbar al hook (que corre durante un crash).
        append_to_error_log("entrada\n", Path("/dev/null/imposible/errors.log"))


class InstallTests(unittest.TestCase):
    def test_replaces_excepthook_and_hook_does_not_raise(self) -> None:
        original = sys.excepthook
        try:
            install_satellite_excepthook()
            self.assertIsNot(sys.excepthook, original)
            self.assertIsNot(sys.excepthook, sys.__excepthook__)
            exc_type, exc, tb = _make_exc_info()
            # El hook completo corre sin lanzar (stderr + log real del data dir).
            sys.excepthook(exc_type, exc, tb)
        finally:
            sys.excepthook = original


if __name__ == "__main__":
    unittest.main()
