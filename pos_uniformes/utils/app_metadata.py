"""Metadata visible de la aplicacion y branding base."""

from __future__ import annotations

import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

APP_DISPLAY_NAME = "POS Uniformes"
APP_ORGANIZATION_NAME = "POSUniformes"
SATELLITE_DISPLAY_NAME = "Kiosko de Presupuestos"
DEFAULT_APP_VERSION = "2026.03.18"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _version_file_candidates() -> tuple[Path, ...]:
    # En el exe empaquetado (PyInstaller) el archivo VERSION vive en la raiz
    # del bundle (_MEIPASS), no junto al paquete: sin esto la app caia al
    # DEFAULT y creia por siempre que habia actualizacion disponible.
    meipass = getattr(sys, "_MEIPASS", "")
    frozen = (Path(meipass) / "VERSION",) if meipass else ()
    return (*frozen, project_root() / "VERSION")


def app_version() -> str:
    for version_file in _version_file_candidates():
        try:
            version_text = version_file.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if version_text:
            return version_text
    return DEFAULT_APP_VERSION


# ─── La versión que se ve ───────────────────────────────────────────────
# Daniel, 2026-11-06: «el sistema de versiones sigue viéndose así, está mal
# ¿no?» — la cabecera decía «Version 2026.11.11»: el archivo VERSION, que se
# subía a mano y llevaba dos meses quieto. Lo que se enseña ahora sale solo
# del último cambio: su fecha y su clave, «6 nov · 6ba73b01». En el kiosko lo
# sella la build (VERSION.txt junto al exe); corriendo del código, lo dice git.
_SELLO = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})\+([0-9a-fA-F]{6,40})$")
_MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def _sello_junto_al_exe() -> str:
    if not getattr(sys, "frozen", False):
        return ""
    try:
        return (Path(sys.executable).resolve().parent / "VERSION.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


@lru_cache(maxsize=4)
def _sello_de_git(raiz: str) -> str:
    """«2026.11.06+6ba73b01» del último commit, o "" si git no contesta."""
    try:
        salida = subprocess.run(
            ["git", "log", "-1", "--format=%cd+%h", "--date=format:%Y.%m.%d"],
            cwd=raiz, capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),   # sin ventana negra en Windows
        )
    except Exception:  # noqa: BLE001 — sin git, sin sello; nunca tumba el arranque
        return ""
    return salida.stdout.strip() if salida.returncode == 0 else ""


def sello_del_codigo() -> str:
    """Fecha y clave del último cambio que trae esta PC, o "" si no se sabe."""
    return _sello_junto_al_exe() or _sello_de_git(str(project_root()))


def version_visible() -> str:
    """«6 nov · 6ba73b01». Sin sello legible, lo que diga el sello o VERSION."""
    sello = sello_del_codigo()
    m = _SELLO.match(sello)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{int(m.group(3))} {_MESES[int(m.group(2)) - 1]} · {m.group(4)}"
    return sello or app_version()


def app_build_label() -> str:
    if sello_del_codigo():
        return f"Versión {version_visible()}"
    return f"Version {app_version()}"


def satellite_display_name() -> str:
    return SATELLITE_DISPLAY_NAME


def satellite_build_label() -> str:
    return app_build_label()


def satellite_windows_icon_path() -> Path | None:
    assets_root = project_root() / "assets"
    candidates = (
        assets_root / "kiosk_app_icon.ico",
        assets_root / "satellite_app_icon.ico",
        app_windows_icon_path(),
    )
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate
    return None


def app_windows_icon_path() -> Path | None:
    assets_root = project_root() / "assets"
    candidates = (
        assets_root / "app_icon.ico",
        assets_root / "logo.ico",
        assets_root / "customer_card_template" / "brand" / "store-logo.ico",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def app_icon_path() -> Path | None:
    assets_root = project_root() / "assets"
    candidates = (
        *(path for path in (app_windows_icon_path(),) if path is not None),
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
