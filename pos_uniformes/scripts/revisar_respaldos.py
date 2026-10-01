"""¿Hay respaldo, y sirve?

Un respaldo que nunca se restauró no es un respaldo, es un archivo. Esto
revisa las dos cosas: cuándo fue el último y —con `--probar`— lo restaura en
una base de juguete que luego se tira, para saber que de verdad se puede
volver de él.

Uso:
    # Solo mirar: qué respaldos hay y de cuándo
    python -m pos_uniformes.scripts.revisar_respaldos

    # Además, restaurar el último en una base aparte y contar qué trajo
    python -m pos_uniformes.scripts.revisar_respaldos --probar

La base de prueba se llama `pos_uniformes_prueba_respaldo` y se borra al
terminar. La base de la tienda NO se toca en ningún momento.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

#: Pasado esto, un respaldo ya no sirve para dormir tranquilo.
DIAS_VIEJO = 3

BASE_PRUEBA = "pos_uniformes_prueba_respaldo"

#: Las que dolería perder; se cuentan tras restaurar.
TABLAS_CLAVE = ("variante", "libreta_venta", "libreta_corte", "empleada_pago", "conteo_inventario")


def _carpeta() -> Path:
    from pos_uniformes.services.backup_service import backup_output_dir

    return backup_output_dir()


def _respaldos(carpeta: Path) -> list[Path]:
    if not carpeta.exists():
        return []
    archivos = [p for p in carpeta.iterdir() if p.suffix in (".dump", ".sql")]
    return sorted(archivos, key=lambda p: p.stat().st_mtime, reverse=True)


def _edad(archivo: Path) -> timedelta:
    return datetime.now() - datetime.fromtimestamp(archivo.stat().st_mtime)


def _humano(td: timedelta) -> str:
    dias = td.days
    if dias == 0:
        return "hoy"
    if dias == 1:
        return "ayer"
    return f"hace {dias} días"


def _mega(archivo: Path) -> float:
    return archivo.stat().st_size / (1024 * 1024)


def mirar(carpeta: Path) -> list[Path]:
    archivos = _respaldos(carpeta)
    print(f"Carpeta: {carpeta}")
    if not archivos:
        print("\n*** NO HAY NINGÚN RESPALDO. ***")
        print("Eso significa que una falla de disco se lleva todo.")
        return []

    print(f"\n{len(archivos)} respaldo(s). Los más recientes:\n")
    for a in archivos[:5]:
        print(f"   {a.name:<46} {_mega(a):>7.1f} MB   {_humano(_edad(a))}")

    ultimo = archivos[0]
    dias = _edad(ultimo).days
    print()
    if dias > DIAS_VIEJO:
        print(f"*** El último respaldo es de {_humano(_edad(ultimo))}. ***")
        print(f"    Si la base se pierde hoy, se pierden {dias} días de trabajo.")
    else:
        print(f"El último es de {_humano(_edad(ultimo))}. 👍")
    return archivos


def _psql(*argumentos: str) -> subprocess.CompletedProcess:
    from pos_uniformes.services.backup_service import _base_env, _resolve_postgres_binary

    return subprocess.run(
        [_resolve_postgres_binary("psql"), *argumentos],
        env={**os.environ, **_base_env()},
        capture_output=True, text=True,
    )


def probar(archivo: Path) -> bool:
    """Restaura el respaldo en una base de juguete y cuenta qué trajo."""
    from pos_uniformes.services.backup_service import _base_env, _resolve_postgres_binary
    from pos_uniformes.utils.config import settings

    print(f"\nProbando «{archivo.name}» en una base aparte…")
    print("(la base de la tienda no se toca)")

    conn = f"host={settings.db_host} port={settings.db_port} user={settings.db_user}"
    _psql("-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{BASE_PRUEBA}"')
    creada = _psql("-d", "postgres", "-c", f'CREATE DATABASE "{BASE_PRUEBA}"')
    if creada.returncode != 0:
        print(f"   No se pudo crear la base de prueba: {creada.stderr.strip()[:200]}")
        return False

    try:
        if archivo.suffix == ".dump":
            restaurar = subprocess.run(
                [_resolve_postgres_binary("pg_restore", "pg_restore.exe"),
                 "--no-owner", "--no-privileges", "--dbname", BASE_PRUEBA, str(archivo)],
                env={**os.environ, **_base_env()}, capture_output=True, text=True,
            )
        else:
            restaurar = _psql("-d", BASE_PRUEBA, "-f", str(archivo))

        # pg_restore avisa de cosas menores con returncode 1; lo que importa
        # es si los datos llegaron.
        filas = {}
        for tabla in TABLAS_CLAVE:
            r = _psql("-d", BASE_PRUEBA, "-tAc", f"SELECT COUNT(*) FROM {tabla}")
            filas[tabla] = r.stdout.strip() if r.returncode == 0 else "no está"

        print()
        for tabla, cuantas in filas.items():
            print(f"   {tabla:<22} {cuantas}")

        sirve = all(str(v).isdigit() for v in filas.values())
        print()
        if sirve:
            print("✅ El respaldo SIRVE: se restauró y los datos están ahí.")
        else:
            print("*** El respaldo NO se pudo restaurar completo. ***")
            if restaurar.stderr:
                print("    " + restaurar.stderr.strip().splitlines()[-1][:200])
        return sirve
    finally:
        _psql("-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{BASE_PRUEBA}"')
        print("(base de prueba borrada)")


def main() -> int:
    carpeta = _carpeta()
    archivos = mirar(carpeta)
    if not archivos:
        return 1
    if "--probar" not in sys.argv:
        print("\nPara saber si de verdad sirve: --probar")
        return 0
    return 0 if probar(archivos[0]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
