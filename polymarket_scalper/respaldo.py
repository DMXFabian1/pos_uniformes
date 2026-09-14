#!/usr/bin/env python3
"""Copia de seguridad de lo que hace falta para reproducir un experimento.

`data/` pesa más de un giga y está en `.gitignore`, así que vive solo en la máquina que corrió el
bot. De ese giga, la mayor parte son deltas de libro en crudo: se pueden volver a capturar y no
entran en ninguna conclusión. Lo que no se puede volver a capturar es el resultado de las
decisiones que ya se tomaron.

Este script separa las dos cosas y guarda solo la primera, que ronda las decenas de megas:

    python respaldo.py crear                    # copia comprimida de las tablas indispensables
    python respaldo.py crear --todo             # incluye también el mercado en crudo (lento y grande)
    python respaldo.py listar                   # qué copias hay y qué contienen
    python respaldo.py verificar copia.tar.gz   # ¿se puede restaurar? comprueba sin escribir nada
    python respaldo.py restaurar copia.tar.gz --en data-restaurada

**No confía en git**: el destino es un archivo comprimido que se puede copiar a donde sea. Y no
sirve de nada un respaldo que no se ha probado, así que `verificar` abre el archivo, cuenta las
filas de cada tabla y compara con el manifiesto que se escribió al crearlo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Tablas sin las cuales no se puede reconstruir ni una sola conclusión. Son el resultado de
# decisiones que ya se tomaron: si se pierden, hay que volver a correr el bot días enteros.
INDISPENSABLES = (
    "experiments",        # qué motor decidió cada cosa; sin esto nada se puede separar
    "ledger",             # el resultado de cada posición
    "decisions",          # todas las decisiones, incluidas las de no operar
    "fill_observations",  # órdenes puestas, llenadas y NO llenadas
    "post_fill",          # trayectoria del precio tras cada llenado
    "partial_legs",       # patas sueltas
    "partial_leg_track",  # su trayectoria y el coste de salir
    "feed_health",        # calidad del dato con el que se decidió
    "reactions",          # retraso entre el partido y el precio
    "signals",            # las señales que se generaron
)

# Se puede volver a capturar conectándose otra vez. Ocupa el 95 % del disco.
RECUPERABLES = ("book_deltas", "book_snapshots", "quotes", "trades", "flow_trades",
                "crypto_prices", "games", "markets", "updown_windows", "wallet_profiles",
                "wallet_closed", "resolutions")


def _tamano(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _humano(n: int) -> str:
    for unidad in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidad == "GB":
            return f"{n:.1f} {unidad}" if unidad != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} GB"


def _filas(carpeta: Path) -> int:
    """Cuenta filas sin cargar los datos en memoria."""
    try:
        import polars as pl
        archivos = list(carpeta.rglob("*.parquet"))
        if not archivos:
            return 0
        return int(pl.scan_parquet(archivos).select(pl.len()).collect().item())
    except Exception:  # noqa: BLE001 - un respaldo no debe fallar por no poder contar
        return -1


def crear(data_dir: Path, destino: Path, todo: bool = False) -> Path:
    tablas = list(INDISPENSABLES) + (list(RECUPERABLES) if todo else [])
    presentes = [t for t in tablas if (data_dir / t).is_dir()]
    if not presentes:
        print(f"No hay ninguna tabla que copiar en {data_dir}", file=sys.stderr)
        raise SystemExit(1)
    sello = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    destino.mkdir(parents=True, exist_ok=True)
    archivo = destino / f"scalper-{sello}{'-completo' if todo else ''}.tar.gz"

    manifiesto = {
        "creado": datetime.now(tz=timezone.utc).isoformat(),
        "origen": str(data_dir.resolve()),
        "completo": todo,
        "tablas": {t: {"filas": _filas(data_dir / t), "bytes": _tamano(data_dir / t)}
                   for t in presentes},
    }
    print(f"Copiando {len(presentes)} tablas de {data_dir}:")
    for t, info in manifiesto["tablas"].items():
        print(f"  {t:22} {info['filas']:>10} filas   {_humano(info['bytes']):>10}")

    with tempfile.TemporaryDirectory() as tmp:
        man = Path(tmp) / "manifiesto.json"
        man.write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
        with tarfile.open(archivo, "w:gz") as tar:
            tar.add(man, arcname="manifiesto.json")
            for t in presentes:
                tar.add(data_dir / t, arcname=f"data/{t}")
    sha = hashlib.sha256(archivo.read_bytes()).hexdigest()[:16]
    (destino / f"{archivo.name}.sha256").write_text(sha + "\n", encoding="utf-8")
    print(f"\nCopia: {archivo}  ({_humano(archivo.stat().st_size)})  sha256:{sha}")
    print("Una copia que no se ha probado no es una copia. Comprueba con:")
    print(f"  python respaldo.py verificar {archivo}")
    return archivo


def verificar(archivo: Path) -> bool:
    """Abre la copia, cuenta las filas de verdad y las compara con el manifiesto."""
    if not archivo.is_file():
        print(f"No existe: {archivo}", file=sys.stderr)
        return False
    sha_guardado = None
    sidecar = archivo.with_name(archivo.name + ".sha256")
    if sidecar.is_file():
        sha_guardado = sidecar.read_text(encoding="utf-8").strip()
        sha_real = hashlib.sha256(archivo.read_bytes()).hexdigest()[:16]
        if sha_real != sha_guardado:
            print(f"FALLO: el archivo no coincide con su sha256 ({sha_real} != {sha_guardado})")
            return False
        print(f"sha256 correcto: {sha_real}")
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp)
        with tarfile.open(archivo, "r:gz") as tar:
            tar.extractall(destino, filter="data")
        man_path = destino / "manifiesto.json"
        if not man_path.is_file():
            print("FALLO: la copia no trae manifiesto", file=sys.stderr)
            return False
        man = json.loads(man_path.read_text(encoding="utf-8"))
        ok = True
        print(f"Copia de {man['creado']}, origen {man['origen']}")
        for tabla, info in man["tablas"].items():
            carpeta = destino / "data" / tabla
            if not carpeta.is_dir():
                print(f"  FALLO {tabla:22} no está en el archivo")
                ok = False
                continue
            reales = _filas(carpeta)
            estado = "ok" if reales == info["filas"] or info["filas"] < 0 else "FALLO"
            if estado == "FALLO":
                ok = False
            print(f"  {estado:5} {tabla:22} {reales:>10} filas (manifiesto: {info['filas']})")
        faltan = [t for t in INDISPENSABLES if t not in man["tablas"]]
        if faltan:
            print(f"  AVISO: la copia no trae {', '.join(faltan)} (puede que no existieran)")
        print("\nLa copia se puede restaurar." if ok else "\nLa copia NO sirve.")
        return ok


def restaurar(archivo: Path, destino: Path) -> None:
    if destino.exists() and any(destino.iterdir()):
        print(f"{destino} existe y no está vacío. Elige otro destino para no pisar nada.",
              file=sys.stderr)
        raise SystemExit(1)
    destino.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(archivo, "r:gz") as tar:
            tar.extractall(tmp, filter="data")
        origen = Path(tmp) / "data"
        for carpeta in sorted(origen.iterdir()):
            shutil.copytree(carpeta, destino / carpeta.name)
        shutil.copy(Path(tmp) / "manifiesto.json", destino / "manifiesto.json")
    print(f"Restaurado en {destino}. Para usarlo: scalper --config config.yaml ... con data_dir={destino}")


def listar(destino: Path) -> None:
    copias = sorted(destino.glob("scalper-*.tar.gz")) if destino.is_dir() else []
    if not copias:
        print(f"No hay copias en {destino}")
        return
    for c in copias:
        try:
            with tarfile.open(c, "r:gz") as tar:
                man = json.loads(tar.extractfile("manifiesto.json").read().decode("utf-8"))
            filas = sum(v["filas"] for v in man["tablas"].values() if v["filas"] > 0)
            print(f"{c.name}  {_humano(c.stat().st_size):>10}  {len(man['tablas'])} tablas  "
                  f"{filas} filas  {man['creado'][:19]}")
        except Exception as e:  # noqa: BLE001
            print(f"{c.name}  ILEGIBLE ({e})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default="data", type=Path)
    ap.add_argument("--destino", default="respaldos", type=Path)
    sub = ap.add_subparsers(dest="accion", required=True)
    c = sub.add_parser("crear", help="crear una copia de las tablas indispensables")
    c.add_argument("--todo", action="store_true", help="incluir también el mercado en crudo")
    sub.add_parser("listar", help="qué copias hay")
    v = sub.add_parser("verificar", help="comprobar que una copia se puede restaurar")
    v.add_argument("archivo", type=Path)
    r = sub.add_parser("restaurar", help="restaurar una copia en otra carpeta")
    r.add_argument("archivo", type=Path)
    r.add_argument("--en", type=Path, required=True,
                   help="carpeta donde restaurar (tiene que estar vacía: no se pisa nada)")
    args = ap.parse_args()

    if args.accion == "crear":
        crear(args.data_dir, args.destino, args.todo)
    elif args.accion == "listar":
        listar(args.destino)
    elif args.accion == "verificar":
        raise SystemExit(0 if verificar(args.archivo) else 1)
    elif args.accion == "restaurar":
        restaurar(args.archivo, args.en)


if __name__ == "__main__":
    main()
