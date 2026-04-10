"""Resolucion de browsers compatibles para render HTML headless."""

from __future__ import annotations

import os
from pathlib import Path
import shutil


def resolve_headless_browser_executable() -> str | None:
    browser_env = str(os.environ.get("BROWSER", "") or "").strip()
    if browser_env:
        env_path = Path(browser_env).expanduser()
        if env_path.exists():
            return str(env_path)
        resolved = shutil.which(browser_env)
        if resolved:
            return resolved

    for candidate in _browser_path_candidates():
        if candidate.exists():
            return str(candidate)

    for executable in (
        "brave-browser",
        "brave",
        "chrome",
        "google-chrome",
        "msedge",
        "microsoft-edge",
        "chromium",
        "chromium-browser",
    ):
        resolved = shutil.which(executable)
        if resolved:
            return resolved
    return None


def _browser_path_candidates() -> list[Path]:
    mac_candidates = [
        Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        Path("/Applications/Arc.app/Contents/MacOS/Arc"),
    ]

    windows_bases = [
        Path(base)
        for base in (
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        )
        if base
    ]
    windows_suffixes = (
        ("Google", "Chrome", "Application", "chrome.exe"),
        ("Microsoft", "Edge", "Application", "msedge.exe"),
        ("BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        ("Chromium", "Application", "chrome.exe"),
        ("Arc", "Application", "Arc.exe"),
    )
    windows_candidates = [base.joinpath(*suffix) for base in windows_bases for suffix in windows_suffixes]

    return mac_candidates + windows_candidates
