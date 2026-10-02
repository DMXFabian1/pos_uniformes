"""Imprime un ticket de prueba con el dibujo de temporada.

    python -m pos_uniformes.scripts.probar_dibujo_ticket             # el de hoy
    python -m pos_uniformes.scripts.probar_dibujo_ticket halloween   # el que sea
    python -m pos_uniformes.scripts.probar_dibujo_ticket --todas     # los ocho
    python -m pos_uniformes.scripts.probar_dibujo_ticket --solo-ver  # sin imprimir

Existe porque el dibujo solo sale en su temporada, y hay que poder verlo en papel
antes —el 2 de octubre no hay ninguna activa y Halloween entra el día 20—. Usa
**el mismo camino de impresión que un ticket de verdad**: si funciona aquí,
funciona el 31.

Lo que se imprime es un ticket corto de mentiras, marcado como PRUEBA para que
no se confunda con uno real si alguien lo encuentra en el mostrador.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.services import temporada_service as temp  # noqa: E402
from pos_uniformes.ui.helpers.ticket_print_layout_helper import (  # noqa: E402
    TICKET_CHAR_WIDTH as ANCHO,
)
from pos_uniformes.ui.helpers.ticket_print_layout_helper import (  # noqa: E402
    tk_bot,
    tk_dbl_bot,
    tk_dbl_row,
    tk_dbl_top,
    tk_line,
    tk_mid,
    tk_top,
)


def ticket_de_prueba(t: temp.Temporada) -> str:
    """Un ticket corto con el dibujo de esa temporada."""
    archivo = temp.ARCHIVOS.get(t.nombre, "")
    lineas = [
        "MAXIMODA".center(ANCHO),
        "*** PRUEBA DE IMPRESION ***".center(ANCHO),
        tk_top(),
        tk_line(f"Temporada: {t.nombre}"),
        tk_mid(),
        tk_line("Playera de prueba"),
        tk_line("T.12  1 x $185.00           $185.00"[:ANCHO - 4]),
        tk_bot(),
        tk_dbl_top(),
        tk_dbl_row("TOTAL A PAGAR:", "$185.00"),
        tk_dbl_bot(),
        "",
    ]
    if archivo and temp.imagen_para_marcador(archivo):
        lineas.append(f"{temp.MARCADOR_INICIO}{archivo}{temp.MARCADOR_FIN}")
    else:
        lineas.extend(r.center(ANCHO) for r in temp._solo_arte_de(t))
    lineas.append(t.saludo.center(ANCHO))
    return "\n".join(lineas)


def _impresora() -> str:
    from pos_uniformes.services.ticket_print_settings_cache_service import (
        load_ticket_print_settings,
    )

    nombre, _copias = load_ticket_print_settings()
    return nombre or ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ticket de prueba con el dibujo.")
    parser.add_argument("temporada", nargs="?", help="halloween, navidad, … (default: hoy)")
    parser.add_argument("--todas", action="store_true", help="imprimir las ocho")
    parser.add_argument("--solo-ver", action="store_true", help="no imprimir, solo enseñarlo")
    args = parser.parse_args(argv)

    if args.todas:
        cuales = list(temp.TEMPORADAS)
    elif args.temporada:
        buscado = args.temporada.strip().lower().replace(" ", "_")
        cuales = [t for t in temp.TEMPORADAS if temp.ARCHIVOS.get(t.nombre, "") == buscado]
        if not cuales:
            print(f"No conozco «{args.temporada}». Las que hay:")
            for t in temp.TEMPORADAS:
                print(f"   {temp.ARCHIVOS.get(t.nombre, ''):20} {t.nombre}")
            return 1
    else:
        hoy = temp.actual()
        if hoy is None:
            print("Hoy no hay temporada. Di cuál quieres, por ejemplo:")
            print("   scripts\\probar_dibujo_ticket.bat halloween")
            return 1
        cuales = [hoy]

    impresora = _impresora()
    if not args.solo_ver and not impresora:
        print("No hay impresora de tickets configurada en esta máquina.")
        print("Se enseña en pantalla; para imprimir, configúrala en el menú admin.")
        args.solo_ver = True

    for t in cuales:
        texto = ticket_de_prueba(t)
        print("=" * ANCHO)
        print(temp.sin_marcadores(texto))
        print("=" * ANCHO)
        if args.solo_ver:
            continue
        try:
            from pos_uniformes.ui.dialogs.printable_text_dialog import print_ticket_text

            if print_ticket_text(texto):
                print(f"✅ Mandado a «{impresora}».")
            else:
                print("⚠️  No se pudo mandar a la impresora.")
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️  Falló la impresión: {exc}")
    if not args.solo_ver:
        print()
        print("Revisa el papel: el dibujo debe salir negro, parejo y centrado.")
        print("Si sale rayado o a medias, dímelo y le bajamos el ancho.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
