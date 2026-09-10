"""¿Qué tarea de Windows está abriendo la ventana negra?

    python -m pos_uniformes.scripts.revisar_tareas [--arreglar]

Lista las tareas del POS con la orden que ejecutan y marca las que abren
consola (las que NO pasan por `correr_oculto.vbs`). Con `--arreglar` aplica
la postactualización a la fuerza: borra las obsoletas y recrea las buenas.
"""

from __future__ import annotations

import csv
import io
import subprocess
import sys

PREFIJO = "POS "
OCULTO = "correr_oculto.vbs"


def tareas_del_pos(salida_csv: str) -> list[tuple[str, str]]:
    """(nombre, orden) de las tareas del POS, leyendo el CSV de schtasks (puro)."""
    filas = list(csv.DictReader(io.StringIO(salida_csv)))
    vistas: dict[str, str] = {}
    for fila in filas:
        nombre = (fila.get("TaskName") or fila.get("Nombre de tarea") or "").strip().lstrip("\\")
        orden = (fila.get("Task To Run") or fila.get("Tarea que se ejecutará") or "").strip()
        if nombre.startswith(PREFIJO) and nombre not in vistas:
            vistas[nombre] = orden
    return sorted(vistas.items())


def abre_ventana(orden: str) -> bool:
    """True si esa orden abre consola (no pasa por el lanzador oculto)."""
    return OCULTO.lower() not in (orden or "").lower()


def _consultar() -> str:
    r = subprocess.run(
        ["schtasks", "/Query", "/FO", "CSV", "/V"],
        capture_output=True, text=True, errors="ignore", timeout=60,
    )
    return r.stdout or ""


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not sys.platform.startswith("win"):
        print("Esto se corre en la PC principal (Windows).")
        return 0
    tareas = tareas_del_pos(_consultar())
    if not tareas:
        print("No hay tareas del POS en esta PC.")
        return 0
    culpables = []
    print("Tareas del POS en esta PC:\n")
    for nombre, orden in tareas:
        malo = abre_ventana(orden)
        print(f"  {'⚠️ ABRE VENTANA' if malo else '   oculta      '}  {nombre}")
        print(f"                    {orden}")
        if malo:
            culpables.append(nombre)
    print()
    if not culpables:
        print("Ninguna abre ventana. Si sigues viéndola, dime a qué hora aparece.")
        return 0
    print(f"{len(culpables)} tarea(s) abren la ventana negra: " + ", ".join(culpables))
    if "--arreglar" not in argv:
        print("\nPara arreglarlas: scripts\\revisar_tareas.bat --arreglar")
        return 0
    from pos_uniformes.scripts import postactualizacion

    print("\nArreglando...")
    for h in postactualizacion.aplicar(forzar=True):
        print(f"  {h}")
    postactualizacion.reiniciar_servicios()
    print("\nListo. Si alguna tarea vieja quedó, aparece arriba como quitada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
