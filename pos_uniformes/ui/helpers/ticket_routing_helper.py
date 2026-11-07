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
    on_printed=None,
    on_back=None,
    tipo=None,
) -> None:
    """`tipo`: TICKET (lo normal) o CORTE. El corte es su propio tipo desde
    2026-10-07 para decidir en qué PC sale; hasta el 2026-11-06 este camino lo
    trataba como ticket, así que las fichas de «¿dónde se imprime?» ofrecían
    las PCs de tickets y no las de cortes (Daniel: «¿también puedo elegir la
    impresora a donde enviar el corte?»)."""
    tickets = [t for t in tickets if t and t.strip()]
    if not tickets:
        return

    from pos_uniformes.database.models import TipoTrabajo
    from pos_uniformes.services.print_routing_cache_service import (
        load_print_routing,
        puede_imprimir,
    )

    tipo = tipo or TipoTrabajo.TICKET
    _modo, origen = load_print_routing()
    # Por TIPO: ver label_routing_helper.
    if not puede_imprimir(tipo):
        # Sin diálogo no hay checkbox: al satélite siempre va el juego base.
        # Encolar exitosamente cuenta como "impreso" para on_printed.
        if _enviar_al_satelite(parent, tickets, origen, tipo=tipo) and on_printed is not None:
            try:
                on_printed()
            except Exception:  # noqa: BLE001
                pass
    else:
        from pos_uniformes.ui.dialogs.printable_text_dialog import open_tickets_print_dialog

        open_tickets_print_dialog(
            parent,
            title,
            tickets,
            unit_label=unit_label,
            alt_tickets=alt_tickets,
            alt_checkbox_label=alt_checkbox_label,
            on_printed=on_printed,
            on_back=on_back,
            # Por si esta impresora falla: las otras PCs que imprimen esto.
            destinos=otras_impresoras_de_tickets(tipo),
            enviar_a=lambda destino, textos: encolar_para(destino, textos, origen, tipo=tipo),
        )


def otras_impresoras_de_tickets(tipo=None) -> list[dict]:
    """Las otras PCs que imprimen tickets (o cortes), para elegirlas en la ventana.

    Vacío si no hay conexión o la base no las conoce: la ventana queda como
    siempre, sin selector."""
    nombre = str(getattr(tipo, "value", tipo) or "TICKET").upper()
    try:
        from pos_uniformes.services.satellite_startup_service import probe_database_host

        if not probe_database_host(0.5):
            return []
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.satelite_registry_service import otras_impresoras
        from pos_uniformes.services.satellite_identity_service import get_satellite_id

        with get_session() as session:
            return otras_impresoras(session, nombre, get_satellite_id())
    except Exception:  # noqa: BLE001 — sin esto se imprime aquí, como siempre
        return []


def _encolar(session, tickets: list[str], *, origen: str, destino: str | None, tipo) -> list:
    """Cada tipo con su cola: el corte entra como CORTE, lo demás como TICKET."""
    from pos_uniformes.database.models import TipoTrabajo
    from pos_uniformes.services import trabajos_service as svc

    if tipo == TipoTrabajo.CORTE:
        return [svc.enviar_corte(session, t, origen=origen, destino=destino) for t in tickets if t and t.strip()]
    return svc.enviar_tickets(session, tickets, origen=origen, destino=destino)


def encolar_para(destino: str, tickets: list[str], origen: str, *, tipo=None) -> int:
    """Encola los tickets dirigidos a la PC `destino`. Devuelve cuántos."""
    from pos_uniformes.database.connection import get_session

    with get_session() as session:
        creados = _encolar(session, tickets, origen=origen, destino=destino, tipo=tipo)
        session.commit()
    return len(creados)


def _enviar_al_satelite(parent: QWidget, tickets: list[str], origen: str, *, tipo=None) -> bool:
    from PyQt6.QtWidgets import QMessageBox

    from pos_uniformes.database.connection import get_session

    try:
        with get_session() as session:
            creados = _encolar(session, tickets, origen=origen, destino=None, tipo=tipo)
            session.commit()
        n = len(creados)
        QMessageBox.information(
            parent,
            "Enviado al satélite",
            f"{n} {'ticket' if n == 1 else 'tickets'} en cola para imprimir en el satélite.",
        )
        return True
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(
            parent,
            "No se pudo enviar al satélite",
            "No se pudo encolar el ticket para el satélite.\n\n"
            f"{exc}\n\nRevisa la conexión con la PC principal.",
        )
        return False
