"""Ruteo de hojas de conteo según el modo de esta máquina (local vs satélite).

Guard llamado al inicio de la impresión de hojas de conteo: si esta PC está en
modo SATÉLITE, encola las hojas y devuelve True (no imprimir local). En modo
LOCAL devuelve False y sigue el diálogo de impresión de siempre.
"""

from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtWidgets import QWidget


def maybe_route_conteo_to_satellite(
    sheets: Sequence[str],
    *,
    titulo: str,
    parent: QWidget | None = None,
) -> bool:
    """True si las hojas se encolaron para el satélite (no imprimir local)."""
    from pos_uniformes.services.print_routing_cache_service import (
        enviar_al_satelite_activo,
        load_print_routing,
    )

    if not enviar_al_satelite_activo():
        return False

    hojas = [s for s in sheets if s and s.strip()]
    if not hojas:
        return True  # nada que imprimir; tampoco abrir el diálogo local

    from PyQt6.QtWidgets import QMessageBox

    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services import trabajos_service as svc

    try:
        _, origen = load_print_routing()
        with get_session() as session:
            svc.enviar_conteo(session, hojas, titulo=titulo, origen=origen)
            session.commit()
        QMessageBox.information(
            parent,
            "Enviado al satélite",
            f"{len(hojas)} hoja(s) de «{titulo}» en cola para imprimir en el satélite.",
        )
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(
            parent,
            "No se pudo enviar al satélite",
            "No se pudieron encolar las hojas para el satélite.\n\n"
            f"{exc}\n\nRevisa la conexión con la PC principal.",
        )
    return True
