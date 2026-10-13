"""Imprime el MISMO ticket largo con distintos altos de franja, para escoger.

    python -m pos_uniformes.scripts.probar_velocidad_ticket            # A, B, C y D
    python -m pos_uniformes.scripts.probar_velocidad_ticket --guardar 256

El ticket dibujado se manda en franjas porque, de una pieza, la térmica se
quedaba sin memoria y dejaba el final en blanco (2026-10-11). Pero cada franja es
una pausa, y con 128 filas se siente trabado (Daniel, 2026-10-13). Cuánto aguanta
la impresora antes de volver a dejar el final en blanco no se puede saber desde
la Mac: se mide en papel.

Cada ticket sale marcado con su letra. Lo que hay que ver en cada uno:
  1. ¿Salió COMPLETO? (la calabaza y los términos del final)
  2. ¿Salió de corrido o a tirones?
El más alto que salga completo es el bueno; se guarda con --guardar.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

#: (letra, filas por franja). None = el ticket de texto de antes, de referencia.
PRUEBAS = (("A", 128), ("B", 256), ("C", 512), ("D", None))


def ticket_largo(letra: str, que: str) -> str:
    """30 productos, el dibujo de temporada y los términos: lo que tronaba."""
    from pos_uniformes.services import temporada_service as temp
    from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
        TICKET_CHAR_WIDTH as ANCHO,
    )
    from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
        tk_bot,
        tk_dbl_bot,
        tk_dbl_row,
        tk_dbl_top,
        tk_line,
        tk_mid,
        tk_top,
    )

    lineas = [
        "MAXIMODA".center(ANCHO),
        f"*** PRUEBA {letra}: {que} ***".center(ANCHO),
        tk_top(),
    ]
    for i in range(1, 31):
        lineas.append(tk_line(f"{i:>2}. Playera Deportiva de prueba"))
        lineas.append(tk_line("    T.12  1 x $185.00       $185.00"[:ANCHO - 4]))
    lineas += [
        tk_mid(),
        tk_line("Artículos: 30"),
        tk_bot(),
        tk_dbl_top(),
        tk_dbl_row("TOTAL A PAGAR:", "$5,550.00"),
        tk_dbl_bot(),
        "",
    ]
    t = temp.actual() or next(
        (x for x in temp.TEMPORADAS if temp.ARCHIVOS.get(x.nombre) == "halloween"), None
    )
    archivo = temp.ARCHIVOS.get(t.nombre, "") if t else ""
    if archivo and temp.imagen_para_marcador(archivo):
        lineas.append(f"{temp.MARCADOR_INICIO}{archivo}{temp.MARCADOR_FIN}")
    lineas += [
        "",
        "TERMINOS Y CONDICIONES".center(ANCHO),
        "Cambios dentro de 15 dias con ticket.",
        "No hay devoluciones de dinero.",
        "Prendas con escudo no tienen cambio.",
        "",
        f"FIN DE LA PRUEBA {letra}".center(ANCHO),
    ]
    return "\n".join(lineas)


def _impresora() -> str:
    from pos_uniformes.services.ticket_print_settings_cache_service import (
        load_ticket_print_settings,
    )

    nombre, _copias = load_ticket_print_settings()
    return nombre or ""


def _mandar(impresora: str, datos: bytes) -> None:
    from pos_uniformes.ui.helpers import escpos_ticket_print_helper as esc

    if sys.platform.startswith("win"):
        esc._send_raw_windows(impresora, datos, 1)
    else:
        esc._send_raw_cups(impresora, datos, 1)


def guardar(filas: int) -> int:
    from pos_uniformes.services.escpos_settings_cache_service import (
        load_escpos_settings,
        save_escpos_settings,
    )

    actual = load_escpos_settings()
    save_escpos_settings(replace(actual, filas_por_franja=filas))
    print(f"✅ Guardado: el ticket dibujado sale en franjas de {load_escpos_settings().filas_por_franja} filas.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Escoger el alto de franja del ticket dibujado.")
    parser.add_argument("--guardar", type=int, metavar="FILAS",
                        help="dejar este alto de franja en esta máquina (16 a 1024)")
    parser.add_argument("--solo", metavar="LETRA", help="imprimir solo una prueba (A, B, C o D)")
    args = parser.parse_args(argv)

    if args.guardar:
        return guardar(args.guardar)

    from PyQt6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication(sys.argv)  # el dibujo usa Qt

    from pos_uniformes.services.escpos_settings_cache_service import load_escpos_settings
    from pos_uniformes.ui.helpers import escpos_ticket_print_helper as esc

    impresora = _impresora()
    if not impresora:
        print("No hay impresora de tickets configurada en esta máquina.")
        return 1

    base = load_escpos_settings()
    print(f"Impresora: {impresora}   (hoy: franjas de {base.filas_por_franja})")
    print()
    for letra, filas in PRUEBAS:
        if args.solo and letra != args.solo.strip().upper():
            continue
        if filas is None:
            que = "texto, como antes"
            datos = esc.build_escpos_bytes(ticket_largo(letra, que), base)
        else:
            que = f"franjas de {filas}"
            ajustes = replace(base, filas_por_franja=filas)
            datos = esc.build_escpos_imagen(ticket_largo(letra, que), ajustes)
        inicio = time.perf_counter()
        try:
            _mandar(impresora, datos)
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️  {letra} ({que}): no se pudo mandar: {exc}")
            continue
        print(f"   {letra}: {que:<20} {len(datos):>9,} bytes, mandado en {time.perf_counter() - inicio:.1f} s")
        # Una pausa entre pruebas para que no se encimen en la cola.
        time.sleep(8)

    print()
    print("Revisa cada ticket:")
    print("  1. ¿Salió completo, con el dibujo y los términos hasta «FIN DE LA PRUEBA»?")
    print("  2. ¿Salió de corrido o a tirones?")
    print()
    print("El más alto que haya salido COMPLETO es el bueno. Para dejarlo, por ejemplo:")
    print("   scripts\\probar_velocidad_ticket.bat --guardar 256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
