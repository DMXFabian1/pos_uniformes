"""Handlers físicos del despachador del satélite (lado Qt/impresoras).

Aquí vive lo que SÍ toca hardware: cada handler recibe un Trabajo reclamado y
lo imprime en la impresora real, reusando las funciones de impresión existentes.
El núcleo del despachador (`services/trabajo_dispatcher.py`) es agnóstico de esto:
solo recibe este diccionario de handlers por inyección.

Fase 1: solo TICKET. Etiquetas y conteo se agregan en fases posteriores.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from pos_uniformes.database.models import TipoTrabajo, Trabajo
from pos_uniformes.services import trabajos_service as svc
from pos_uniformes.services.trabajo_dispatcher import Handler

# Misma pausa que TicketPrintQueue usa entre tickets (apartado): le da tiempo al
# spooler/autocutter de terminar una hoja antes de mandar la siguiente. Sin esto,
# imprimir las hojas en un bucle apretado hacía que se cortaran antes de tiempo.
DELAY_ENTRE_HOJAS_S = 1.5


def _qt_sleep(seconds: float) -> None:
    """Espera `seconds` sin congelar la UI (event loop anidado)."""
    from PyQt6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()


def imprimir_hojas_paced(
    hojas: Sequence[str],
    *,
    print_fn: Callable[[str], bool],
    sleep_fn: Callable[[float], None] | None = None,
    delay_s: float = DELAY_ENTRE_HOJAS_S,
) -> int:
    """Imprime cada hoja como job separado con una pausa entre ellas.

    Devuelve cuántas fallaron. La pausa va ENTRE hojas (no después de la última),
    igual que TicketPrintQueue. `print_fn`/`sleep_fn` se inyectan para testear sin Qt.
    """
    if sleep_fn is None:
        sleep_fn = _qt_sleep
    errores = 0
    n = len(hojas)
    for i, hoja in enumerate(hojas):
        if not print_fn(hoja):
            errores += 1
        if i < n - 1:
            sleep_fn(delay_s)
    return errores


def _ticket_handler(trabajo: Trabajo) -> None:
    # Import diferido: solo el runtime del satélite (con Qt) carga esto.
    from pos_uniformes.ui.dialogs.printable_text_dialog import print_ticket_text

    texto = svc.texto_de_ticket(trabajo)
    if not print_ticket_text(texto):
        raise RuntimeError(
            "La impresora de tickets no respondió (¿apagada o sin configurar?)."
        )


def _etiqueta_handler(trabajo: Trabajo) -> None:
    import tempfile

    from pos_uniformes.ui.helpers.satellite_label_print_helper import (
        print_label_image_headless,
    )

    imagen, sku, copies, paper_mode = svc.datos_de_etiqueta(trabajo)
    tmp_dir = tempfile.mkdtemp(prefix="etiqueta_satelite_")
    tmp_path = Path(tmp_dir) / f"etiqueta_{trabajo.id}.png"
    tmp_path.write_bytes(imagen)
    print_label_image_headless(tmp_path, sku=sku, copies=copies, paper_mode=paper_mode)


def _conteo_handler(trabajo: Trabajo) -> None:
    from pos_uniformes.ui.dialogs.printable_text_dialog import print_ticket_text

    hojas = svc.hojas_de_conteo(trabajo)
    errores = imprimir_hojas_paced(hojas, print_fn=print_ticket_text)
    if errores:
        raise RuntimeError(
            f"{errores} de {len(hojas)} hoja(s) de conteo no se imprimieron."
        )


def build_handlers() -> dict[TipoTrabajo, Handler]:
    """Handlers disponibles en el satélite. Se amplía por fase."""
    return {
        TipoTrabajo.TICKET: _ticket_handler,
        TipoTrabajo.ETIQUETA: _etiqueta_handler,
        TipoTrabajo.CONTEO: _conteo_handler,
    }
