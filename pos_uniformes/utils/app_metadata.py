"""Metadata visible de la aplicacion y branding base."""

from __future__ import annotations

from pathlib import Path

APP_DISPLAY_NAME = "POS Uniformes"
APP_ORGANIZATION_NAME = "POSUniformes"
DEFAULT_APP_VERSION = "2026.03.18"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def app_version() -> str:
    version_file = project_root() / "VERSION"
    try:
        version_text = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        version_text = ""
    return version_text or DEFAULT_APP_VERSION


def app_build_label() -> str:
    return f"Version {app_version()}"


def app_icon_path() -> Path | None:
    assets_root = project_root() / "assets"
    candidates = (
        assets_root / "logo.png",
        assets_root / "logo.jpg",
        assets_root / "logo.jpeg",
        assets_root / "customer_card_template" / "brand" / "business-logo.png",
        assets_root / "customer_card_template" / "brand" / "business-logo.jpg",
        assets_root / "customer_card_template" / "brand" / "business-logo.jpeg",
        assets_root / "customer_card_template" / "brand" / "store-logo.PNG",
        assets_root / "customer_card_template" / "brand" / "store-logo.png",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
