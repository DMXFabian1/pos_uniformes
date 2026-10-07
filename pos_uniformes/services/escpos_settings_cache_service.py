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
    #: Dibujar el ticket como IMAGEN de 576 puntos en vez de mandarlo como
    #: texto. Es lo que permite el logo nítido, las cajas con línea de verdad y
    #: el total grande — y de paso se acaban los problemas de codepage, porque
    #: una imagen no tiene codificación. Apagado por defecto: cambia cómo se ve
    #: el ticket y eso se enciende a propósito, no por actualizar
    #: (Daniel, 2026-10-07).
    ticket_como_imagen: bool = False
    #: Dejar que la impresora calcule hasta dónde avanzar antes de cortar
    #: (`GS V 65`) en vez de empujar `feed_lines` renglones a ciegas. Encendido
    #: por defecto porque lo de antes cortaba el último renglón a la mitad. Si
    #: alguna impresora vieja no entendiera el comando, se apaga aquí y vuelve
    #: el avance a mano (2026-10-07).
    corte_calculado: bool = True
    #: Puntos EXTRA más allá de la posición de corte. 0 = al ras.
    puntos_tras_corte: int = 0


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
            ticket_como_imagen=bool(data.get("ticket_como_imagen", d.ticket_como_imagen)),
            corte_calculado=bool(data.get("corte_calculado", d.corte_calculado)),
            puntos_tras_corte=max(0, min(255, int(
                data.get("puntos_tras_corte", d.puntos_tras_corte)
            ))),
        )
    except Exception:  # noqa: BLE001
        return EscPosSettings()


def save_escpos_settings(settings: EscPosSettings) -> None:
    """Guarda TODOS los campos, sacándolos del dataclass.

    Antes la lista de claves estaba escrita a mano y había que acordarse de
    agregar cada campo nuevo en dos lugares. No se acordó nadie: `ticket_como_imagen`
    se leía pero no se escribía, así que Daniel marcaba la casilla, guardaba,
    volvía a abrir y estaba desmarcada — sin error ni aviso, como si no hubiera
    tocado nada (2026-10-07). Con `asdict` el campo nuevo se guarda solo.
    """
    from dataclasses import asdict

    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False), encoding="utf-8")
