"""Ruteo de etiquetas según el modo de esta máquina (local vs satélite).

Guard que se llama al inicio de la impresión física de etiquetas: si esta PC
está en modo SATÉLITE, encola la etiqueta (imagen ya renderizada) y devuelve
True para que el llamador NO imprima local. En modo LOCAL devuelve False y la
impresión sigue como siempre.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QWidget


def maybe_route_label_to_satellite(
    image_path: Path | str,
    *,
    sku: str,
    copies: int,
    paper_mode: str,
    parent: QWidget | None = None,
) -> bool:
    """True si la etiqueta se encoló para el satélite (no imprimir local)."""
    from pos_uniformes.services.print_routing_cache_service import (
        enviar_al_satelite_activo,
        load_print_routing,
    )

    if not enviar_al_satelite_activo():
        return False

    from PyQt6.QtWidgets import QMessageBox

    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services import trabajos_service as svc

    try:
        imagen = Path(image_path).read_bytes()
        _, origen = load_print_routing()
        with get_session() as session:
            svc.enviar_etiqueta(
                session,
                imagen,
                sku=sku,
                copies=copies,
                paper_mode=paper_mode,
                origen=origen,
            )
            session.commit()
        QMessageBox.information(
            parent,
            "Enviado al satélite",
            f"Etiqueta de {sku or 'producto'} ({copies} copia(s)) "
            "en cola para imprimir en el satélite.",
        )
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(
            parent,
            "No se pudo enviar al satélite",
            "No se pudo encolar la etiqueta para el satélite.\n\n"
            f"{exc}\n\nRevisa la conexión con la PC principal.",
        )
    # Aun si falló el encolado, no imprimimos local: esta PC no tiene la
    # impresora de etiquetas (por eso está en modo satélite).
    return True
