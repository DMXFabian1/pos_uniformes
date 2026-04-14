from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from pos_uniformes.utils.headless_browser_helper import resolve_headless_browser_executable


class HeadlessBrowserHelperTests(unittest.TestCase):
    def test_resolve_prefers_windows_browser_installation_paths(self) -> None:
        target_suffix = ("Google", "Chrome", "Application", "chrome.exe")

        with patch.dict(
            os.environ,
            {
                "ProgramFiles": r"C:\Program Files",
                "ProgramFiles(x86)": r"C:\Program Files (x86)",
                "LOCALAPPDATA": r"C:\Users\pc\AppData\Local",
            },
            clear=False,
        ), patch("pos_uniformes.utils.headless_browser_helper.shutil.which", return_value=None), patch.object(
            Path,
            "exists",
            new=lambda self: self.parts[-4:] == target_suffix,
        ):
            resolved = resolve_headless_browser_executable()

        self.assertIsNotNone(resolved)
        self.assertTrue(str(resolved).endswith("Google/Chrome/Application/chrome.exe"))

    def test_resolve_uses_browser_env_before_fallbacks(self) -> None:
        existing_paths = {
            Path("/custom/browser"),
        }

        with patch.dict(os.environ, {"BROWSER": "/custom/browser"}, clear=False), patch.object(
            Path,
            "exists",
            new=lambda self: self in existing_paths,
        ), patch("pos_uniformes.utils.headless_browser_helper.shutil.which", return_value=None):
            resolved = resolve_headless_browser_executable()

        self.assertEqual(resolved, "/custom/browser")


if __name__ == "__main__":
    unittest.main()
