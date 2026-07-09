"""Tests de la config de impresoras de etiquetas por modo (menú admin).

Dos impresoras Brother idénticas: una para Normal/Split/Continua y otra
para Label (troquelada DK-1221). Se configura una vez y persiste.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.services import label_printer_settings_cache_service as svc
from pos_uniformes.services.label_printer_settings_cache_service import (
    resolve_label_printer_for_mode,
)


class RoutingTests(unittest.TestCase):
    def test_label_mode_goes_to_label_printer(self) -> None:
        self.assertEqual(
            resolve_label_printer_for_mode(
                "dk1221", normal_printer="Brother Etiquetas", label_printer="Brother Label"
            ),
            "Brother Label",
        )

    def test_normal_split_continuous_go_to_normal_printer(self) -> None:
        for mode in ("standard", "split", "continuous"):
            self.assertEqual(
                resolve_label_printer_for_mode(
                    mode, normal_printer="Brother Etiquetas", label_printer="Brother Label"
                ),
                "Brother Etiquetas",
                mode,
            )

    def test_empty_config_returns_empty_for_fallback(self) -> None:
        # Sin config → "" → el llamador cae a la autodetección de la Brother.
        self.assertEqual(
            resolve_label_printer_for_mode("dk1221", normal_printer="", label_printer=""),
            "",
        )
        self.assertEqual(
            resolve_label_printer_for_mode("standard", normal_printer="", label_printer=""),
            "",
        )

    def test_only_label_configured_leaves_normal_on_fallback(self) -> None:
        # Mientras llega la segunda impresora: solo Label configurada.
        self.assertEqual(
            resolve_label_printer_for_mode("standard", normal_printer="", label_printer="Brother Label"),
            "",
        )
        self.assertEqual(
            resolve_label_printer_for_mode("dk1221", normal_printer="", label_printer="Brother Label"),
            "Brother Label",
        )


class PersistenceTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(svc, "satellite_data_dir", return_value=Path(tmp)):
                svc.save_label_printer_settings("Brother Etiquetas", "Brother Label")
                self.assertEqual(
                    svc.load_label_printer_settings(),
                    ("Brother Etiquetas", "Brother Label"),
                )

    def test_load_missing_returns_empty_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(svc, "satellite_data_dir", return_value=Path(tmp)):
                self.assertEqual(svc.load_label_printer_settings(), ("", ""))

    def test_load_corrupt_returns_empty_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(svc, "satellite_data_dir", return_value=Path(tmp)):
                (Path(tmp) / "data").mkdir()
                (Path(tmp) / "data" / "label_printer_settings.json").write_text("{roto", encoding="utf-8")
                self.assertEqual(svc.load_label_printer_settings(), ("", ""))


if __name__ == "__main__":
    unittest.main()
