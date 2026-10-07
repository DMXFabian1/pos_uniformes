"""Manda a la impresora de tickets una prueba del logo, y nada más.

    python -m pos_uniformes.scripts.probar_logo_ticket

El logo es lo único del ticket nuevo que puede salir mal por la impresora y no
por el programa: MAXIMODA tiene serifas de un punto de grosor a 203 dpi y la
térmica se las puede comer. Antes de rehacer el ticket entero hay que verlo en
papel, que es lo único que decide (Daniel, 2026-10-07).

Dos caminos, y la diferencia importa:

    probar_logo_ticket.bat            por la COLA: lo imprime quien la atienda
    probar_logo_ticket.bat --aqui     AQUÍ MISMO, en la impresora de esta PC

Para comparar impresoras hay que usar `--aqui`. Por la cola no se puede elegir
en cuál sale: el kiosko está pegado a ella y se lleva el trabajo en menos de un
segundo (pasó dos veces el 2026-10-07, con la prueba destinada a la principal).
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def texto_de_prueba() -> str:
    """El logo en los dos anchos, para saber a quién culpar.

    A 500 puntos el driver tiene que reescalar la imagen para acomodarla en la
    página; a 576 —el ancho completo del papel— no. Si B sale limpia y A no, el
    culpable es el reescalado y no la impresora ni el tamaño del logo."""
    from pos_uniformes.services.temporada_service import marcador_de

    a, b = marcador_de("logo"), marcador_de("logo_ancho")
    if not a and not b:
        return ""
    ancho = 38
    lineas = ["PRUEBA DEL LOGO".center(ancho), ""]
    if a:
        lineas += ["A) 500 puntos de ancho", a, ""]
    if b:
        lineas += ["B) 576 puntos (ancho completo)", b, ""]
    lineas += [
        "Si B sale limpia y A no, el driver",
        "esta reescalando la imagen.",
        "",
        "Si las dos salen apolilladas, hay que",
        "mandarla por ESC/POS crudo.",
        "",
        "-" * ancho,
        "",
        "",
    ]
    return "\n".join(lineas)


def _imprimir_aqui(texto: str) -> int:
    """Directo a la impresora de ESTA PC, sin pasar por la cola."""
    from PyQt6.QtWidgets import QApplication

    from pos_uniformes.ui.dialogs.printable_text_dialog import print_ticket_text

    # QPrinter necesita una QApplication aunque no se abra ninguna ventana.
    app = QApplication.instance() or QApplication(sys.argv[:1])
    del app
    if print_ticket_text(texto):
        print("Mandado a la impresora de tickets de esta PC.")
        return 0
    print("No se pudo imprimir. ¿Está elegida la impresora de tickets de esta PC?")
    print("Se escoge en el menú admin del kiosko (Ctrl+Shift+A).")
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    aqui = "--aqui" in argv

    texto = texto_de_prueba()
    if not texto:
        print("No hay logo preparado todavía.")
        print("Córrelo primero: python -m pos_uniformes.scripts.generar_logo_ticket")
        return 1

    if aqui:
        return _imprimir_aqui(texto)

    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services import trabajos_service

    with get_session() as session:
        trabajo = trabajos_service.enviar_ticket(
            session, texto, origen="prueba_logo", creado_por="VEND-1"
        )
        session.commit()
        print(f"Encolado el trabajo {trabajo.id}.")
        print("OJO: sale en la PC que atienda la cola, que normalmente es el kiosko.")
        print("Para probar en ESTA PC: probar_logo_ticket.bat --aqui")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
