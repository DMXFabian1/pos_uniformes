"""Cache local de las impresoras de etiquetas del satélite.

Permite dedicar una impresora a los modos Normal/Split/Continua y otra al
modo Label (troquelada DK-1221), sin cambiar el rollo entre trabajos. Se
configura una vez desde el menú admin (Ctrl+Shift+A) y persiste en disco;
cada satélite tiene su propia configuración local.

Espejo de ticket_print_settings_cache_service.
"""

from __future__ import annotations

import json
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

_CACHE_FILENAME = "label_printer_settings.json"

# El modo Label es el único que necesita el rollo troquelado; el resto
# (Normal, Split, Continua) usa el rollo continuo de la otra impresora.
_LABEL_MODE = "dk1221"


def _cache_path() -> Path:
    return satellite_data_dir() / "data" / _CACHE_FILENAME


def save_label_printer_settings(normal_printer: str, label_printer: str) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "normal_printer": str(normal_printer or ""),
                "label_printer": str(label_printer or ""),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def load_label_printer_settings() -> tuple[str, str]:
    """Devuelve (normal_printer, label_printer); ("", "") si no hay config."""
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        return (
            str(data.get("normal_printer", "")),
            str(data.get("label_printer", "")),
        )
    except Exception:  # noqa: BLE001
        return "", ""


def resolve_label_printer_for_mode(
    mode: str,
    *,
    normal_printer: str,
    label_printer: str,
) -> str:
    """Impresora que corresponde al modo, o "" si no está configurada.

    Cuando devuelve "" el llamador debe caer al comportamiento anterior
    (autodetección de la Brother) — así los satélites sin esta config no se
    rompen.
    """
    chosen = label_printer if str(mode or "").strip() == _LABEL_MODE else normal_printer
    return str(chosen or "").strip()
