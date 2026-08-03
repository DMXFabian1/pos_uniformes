"""Ruteo de tickets según el modo de esta máquina (local vs satélite).

Punto único que reemplaza a `open_tickets_print_dialog` en los flujos de venta:
consulta el ajuste por máquina y, o bien imprime local (comportamiento actual),
o bien encola los tickets para que los imprima el satélite.

Default = local, así que sin configurar nada el comportamiento no cambia.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget


def route_tickets(
    parent: QWidget,
    title: str,
    tickets: list[str],
    *,
    unit_label: str = "ticket",
    alt_tickets: list[str] | None = None,
    alt_checkbox_label: str | None = None,
) -> None:
    tickets = [t for t in tickets if t and t.strip()]
    if not tickets:
        return

    from pos_uniformes.services.print_routing_cache_service import (
        MODO_SATELITE,
        load_print_routing,
    )

    modo, origen = load_print_routing()
    if modo == MODO_SATELITE:
        # Sin diálogo no hay checkbox: al satélite siempre va el juego base.
        _enviar_al_satelite(parent, tickets, origen)
    else:
        from pos_uniformes.ui.dialogs.printable_text_dialog import open_tickets_print_dialog

        open_tickets_print_dialog(
            parent,
            title,
            tickets,
            unit_label=unit_label,
            alt_tickets=alt_tickets,
            alt_checkbox_label=alt_checkbox_label,
        )


def _enviar_al_satelite(parent: QWidget, tickets: list[str], origen: str) -> None:
    from PyQt6.QtWidgets import QMessageBox

    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services import trabajos_service as svc

    try:
        with get_session() as session:
            creados = svc.enviar_tickets(session, tickets, origen=origen)
            session.commit()
        n = len(creados)
        QMessageBox.information(
            parent,
            "Enviado al satélite",
            f"{n} {'ticket' if n == 1 else 'tickets'} en cola para imprimir en el satélite.",
        )
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(
            parent,
            "No se pudo enviar al satélite",
            "No se pudo encolar el ticket para el satélite.\n\n"
            f"{exc}\n\nRevisa la conexión con la PC principal.",
        )
