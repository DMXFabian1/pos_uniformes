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
        imprimir_aqui_de_respaldo,
        load_print_routing,
        puede_imprimir,
    )

    tipo = tipo or TipoTrabajo.TICKET
    _modo, origen = load_print_routing()
    # Por TIPO: ver label_routing_helper.
    if not puede_imprimir(tipo):
        # Un corte se elige a dónde va aunque esta PC no lo imprima (Daniel,
        # 2026-11-07): la ventana sale sin la ficha «Aquí». Los tickets de venta
        # siguen yéndose solos a la cola: ahí no hay que decidir nada.
        otras = otras_impresoras_de_tickets(tipo) if tipo == TipoTrabajo.CORTE else []
        if imprimir_aqui_de_respaldo(tipo, otras):
            # La PC de cortes está apagada y esta tiene impresora: sale aquí
            # (las apagadas se ven en gris, por si se prefiere esperar).
            from pos_uniformes.ui.dialogs.printable_text_dialog import open_tickets_print_dialog

            open_tickets_print_dialog(
                parent, title, tickets, unit_label=unit_label, alt_tickets=alt_tickets,
                alt_checkbox_label=alt_checkbox_label, on_printed=on_printed, on_back=on_back,
                destinos=otras, aqui_respaldo=True,
                enviar_a=_enviar_y_vigilar(parent, otras, origen, tipo),
            )
            return
        if otras:
            from pos_uniformes.ui.dialogs.printable_text_dialog import open_tickets_print_dialog

            open_tickets_print_dialog(
                parent, title, tickets, unit_label=unit_label, alt_tickets=alt_tickets,
                alt_checkbox_label=alt_checkbox_label, on_printed=on_printed, on_back=on_back,
                destinos=otras, aqui_imprime=False,
                enviar_a=_enviar_y_vigilar(parent, otras, origen, tipo),
            )
            return
        # Sin diálogo no hay checkbox: al satélite siempre va el juego base.
        # Encolar exitosamente cuenta como "impreso" para on_printed.
        if _enviar_al_satelite(parent, tickets, origen, tipo=tipo) and on_printed is not None:
            try:
                on_printed()
            except Exception:  # noqa: BLE001
                pass
    else:
        from pos_uniformes.ui.dialogs.printable_text_dialog import open_tickets_print_dialog

        otras = otras_impresoras_de_tickets(tipo)
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
            destinos=otras,
            enviar_a=_enviar_y_vigilar(parent, otras, origen, tipo),
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
    return len(encolar_para_ids(destino, tickets, origen, tipo=tipo))


def encolar_para_ids(destino: str, tickets: list[str], origen: str, *, tipo=None) -> list[int]:
    """Como `encolar_para`, pero devuelve los ids (para revisar si salieron)."""
    from pos_uniformes.database.connection import get_session

    with get_session() as session:
        creados = _encolar(session, tickets, origen=origen, destino=destino, tipo=tipo)
        session.commit()
        return [int(t.id) for t in creados]


def _enviar_y_vigilar(parent: QWidget, otras: list[dict], origen: str, tipo):
    """El `enviar_a` de la ventana: encola y, al rato, revisa que haya salido.

    Si la otra PC no lo tomó (se apagó justo después de su último latido),
    avisa aquí mismo en vez de dejar creer que salió (2026-11-12)."""

    def enviar(destino: str, textos: list[str]) -> int:
        ids = encolar_para_ids(destino, textos, origen, tipo=tipo)
        nombre = next((d.get("nombre", "") for d in otras if d.get("identificador") == destino), "")
        vigilar_envio(parent, ids, nombre)
        return len(ids)

    return enviar


def vigilar_envio(parent: QWidget | None, ids: list[int], nombre_destino: str, *, segundos: int | None = None) -> None:
    """Dentro de unos segundos revisa esos trabajos y avisa si no salieron.

    El temporizador cuelga de `parent`: si esa ventana ya se cerró, no avisa
    (y no truena). Sin `parent` no hay a quién avisar."""
    if parent is None or not ids:
        return
    from PyQt6.QtCore import QTimer

    from pos_uniformes.services import trabajos_service as svc

    espera = svc.SEGUNDOS_PARA_REVISAR if segundos is None else segundos
    timer = QTimer(parent)
    timer.setSingleShot(True)

    def revisar() -> None:
        timer.deleteLater()
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                texto = svc.aviso_no_ha_salido(svc.sin_salir(session, ids), nombre_destino)
        except Exception:  # noqa: BLE001 — sin base no se puede saber; no se inventa un aviso
            return
        if texto:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(parent, "Todavía no sale", texto)

    timer.timeout.connect(revisar)
    timer.start(int(espera * 1000))


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
