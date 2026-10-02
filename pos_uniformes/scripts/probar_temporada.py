"""Finge una temporada un rato, para ver el adorno antes de su fecha.

    python -m pos_uniformes.scripts.probar_temporada halloween
    python -m pos_uniformes.scripts.probar_temporada --quitar
    python -m pos_uniformes.scripts.probar_temporada            # cómo va

Halloween entra el 20 de octubre y querer verlo el 2 es razonable. Lo que no es
razonable es que se quede forzado, así que **vence solo en dos horas**: una
tienda con el arbolito de Navidad en marzo porque alguien probó y se le olvidó
quitarlo es peor que no haber tenido la herramienta.

Afecta a la pantalla **y** al ticket, que es lo que se quiere: así se ve el
adorno completo, no la mitad.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.services import temporada_service as temp  # noqa: E402


def _lista() -> str:
    return "\n".join(
        f"   {temp.ARCHIVOS.get(t.nombre, ''):20} {t.nombre}" for t in temp.TEMPORADAS
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finge una temporada un rato.")
    parser.add_argument("temporada", nargs="?", help="halloween, navidad, …")
    parser.add_argument("--quitar", action="store_true", help="volver al calendario")
    parser.add_argument("--horas", type=float, default=temp.HORAS_FORZADA)
    args = parser.parse_args(argv)

    if args.quitar:
        if temp.quitar_forzada():
            print("Listo: vuelve el calendario de verdad.")
            hoy = temp.actual()
            print(f"Hoy toca: {hoy.nombre if hoy else 'ninguna temporada'}.")
        else:
            print("No había ninguna forzada.")
        print("\nCierra y vuelve a abrir el kiosko para que se note.")
        return 0

    if not args.temporada:
        forzada = temp.forzada()
        if forzada is not None:
            print(f"Ahora mismo está forzada: {forzada.nombre} {forzada.emoji}")
            print("Para quitarla:  scripts\\probar_temporada.bat --quitar")
        else:
            hoy = temp.actual()
            print(f"Sin forzar. Hoy toca: {hoy.nombre if hoy else 'ninguna temporada'}.")
        print("\nLas que hay:")
        print(_lista())
        return 0

    t = temp.forzar(args.temporada.strip().lower().replace(" ", "_"), horas=args.horas)
    if t is None:
        print(f"No conozco «{args.temporada}». Las que hay:")
        print(_lista())
        return 1

    print(f"Listo: {t.emoji}  {t.nombre} — «{t.saludo}»")
    print(f"Dura {args.horas:g} horas y se quita solo.")
    print()
    print("CIERRA Y VUELVE A ABRIR EL KIOSKO para verlo:")
    print("  · la raya de color y el saludo al pie de la barra")
    print("  · el dibujo en la tarjeta de venta rápida")
    print()
    print("Y para verlo en papel:")
    print(f"  scripts\\probar_dibujo_ticket.bat {temp.ARCHIVOS.get(t.nombre, '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
