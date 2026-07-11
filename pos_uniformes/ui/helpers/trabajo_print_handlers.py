"""Handlers físicos del despachador del satélite (lado Qt/impresoras).

Aquí vive lo que SÍ toca hardware: cada handler recibe un Trabajo reclamado y
lo imprime en la impresora real, reusando las funciones de impresión existentes.
El núcleo del despachador (`services/trabajo_dispatcher.py`) es agnóstico de esto:
solo recibe este diccionario de handlers por inyección.

Fase 1: solo TICKET. Etiquetas y conteo se agregan en fases posteriores.
"""

from __future__ import annotations

from pathlib import Path

from pos_uniformes.database.models import TipoTrabajo, Trabajo
from pos_uniformes.services import trabajos_service as svc
from pos_uniformes.services.trabajo_dispatcher import Handler


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


def build_handlers() -> dict[TipoTrabajo, Handler]:
    """Handlers disponibles en el satélite. Se amplía por fase."""
    return {
        TipoTrabajo.TICKET: _ticket_handler,
        TipoTrabajo.ETIQUETA: _etiqueta_handler,
    }
