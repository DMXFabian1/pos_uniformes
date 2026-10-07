"""Manda a la impresora de tickets una prueba del logo, y nada más.

    python -m pos_uniformes.scripts.probar_logo_ticket

El logo es lo único del ticket nuevo que puede salir mal por la impresora y no
por el programa: MAXIMODA tiene serifas de un punto de grosor a 203 dpi y la
térmica se las puede comer. Antes de rehacer el ticket entero hay que verlo en
papel, que es lo único que decide (Daniel, 2026-10-07).

Va por la cola de trabajos, así que sale en la PC que tenga la impresora, con
el kiosko abierto o con el servidor de impresión corriendo.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def texto_de_prueba() -> str:
    from pos_uniformes.services.temporada_service import marcador_de

    marcador = marcador_de("logo")
    if not marcador:
        return ""
    ancho = 38
    return "\n".join([
        "PRUEBA DEL LOGO".center(ancho),
        "",
        marcador,
        "",
        "Si se ve parejo y las patitas de las",
        "letras salen completas, sirve.",
        "",
        "Si sale deshilachado o con huecos,",
        "hay que imprimirlo mas grande.",
        "",
        "-" * ancho,
        "",
        "",
    ])


def main() -> int:
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services import trabajos_service

    texto = texto_de_prueba()
    if not texto:
        print("No hay logo preparado todavía.")
        print("Córrelo primero: python -m pos_uniformes.scripts.generar_logo_ticket")
        return 1
    with get_session() as session:
        trabajo = trabajos_service.enviar_ticket(
            session, texto, origen="prueba_logo", creado_por="VEND-1"
        )
        session.commit()
        print(f"Encolado el trabajo {trabajo.id}. Sale en la PC que tiene la impresora.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
