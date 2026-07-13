"""Ajustes de impresión ESC/POS (crudo) para la térmica de tickets.

Imprimir por ESC/POS crudo (spooler RAW) evita el driver de Windows y sus
problemas con el tamaño de página (la 1ª hoja salía ancha/recortada). Estos
ajustes se guardan por máquina en un JSON para poder calibrar el codepage sin
recompilar (el valor de `ESC t n` que selecciona CP850 depende del modelo).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

_CACHE_FILENAME = "escpos_settings.json"


@dataclass(frozen=True)
class EscPosSettings:
    enabled: bool = True          # usar ESC/POS crudo (Windows) en vez del driver
    codepage: int = 2             # valor de `ESC t n` (2 = CP850 en la mayoría)
    encoding: str = "cp850"       # codificación del texto (caja + acentos)
    feed_lines: int = 3           # líneas en blanco antes del corte (offset cuchilla)
    full_cut: bool = True         # True = corte total; False = corte parcial


def _cache_path() -> Path:
    return satellite_data_dir() / "data" / _CACHE_FILENAME


def load_escpos_settings() -> EscPosSettings:
    """Ajustes ESC/POS de esta máquina (defaults si no hay archivo/corrupto)."""
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        d = EscPosSettings()
        return EscPosSettings(
            enabled=bool(data.get("enabled", d.enabled)),
            codepage=int(data.get("codepage", d.codepage)),
            encoding=str(data.get("encoding", d.encoding)) or d.encoding,
            feed_lines=max(0, int(data.get("feed_lines", d.feed_lines))),
            full_cut=bool(data.get("full_cut", d.full_cut)),
        )
    except Exception:  # noqa: BLE001
        return EscPosSettings()


def save_escpos_settings(settings: EscPosSettings) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "enabled": settings.enabled,
                "codepage": settings.codepage,
                "encoding": settings.encoding,
                "feed_lines": settings.feed_lines,
                "full_cut": settings.full_cut,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
