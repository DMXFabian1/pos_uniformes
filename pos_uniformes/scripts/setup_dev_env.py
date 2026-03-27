"""Bootstrap portable para preparar el entorno local en macOS o Windows."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def venv_python_path(root: Path) -> Path:
    if os_name() == "Windows":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def os_name() -> str:
    return platform.system() or os.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepara el entorno de desarrollo local para POS Uniformes.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra los pasos sin ejecutarlos.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="No instala pip ni dependencias dentro de la .venv.",
    )
    parser.add_argument(
        "--skip-env-copy",
        action="store_true",
        help="No crea pos_uniformes.env a partir del ejemplo.",
    )
    return parser.parse_args(argv)


def run_command(command: list[str], *, dry_run: bool) -> None:
    printable = " ".join(command)
    print(f"$ {printable}")
    if dry_run:
        return
    subprocess.run(command, check=True)


def ensure_venv(root: Path, *, dry_run: bool) -> Path:
    venv_python = venv_python_path(root)
    if venv_python.exists():
        print(f"Entorno virtual detectado: {venv_python}")
        return venv_python

    print("Creando .venv local...")
    run_command([sys.executable, "-m", "venv", str(root / ".venv")], dry_run=dry_run)
    return venv_python


def install_dependencies(root: Path, venv_python: Path, *, dry_run: bool) -> None:
    requirements = root / "requirements.txt"
    build_requirements = root / "requirements-build.txt"
    run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], dry_run=dry_run)
    run_command(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements),
            "-r",
            str(build_requirements),
        ],
        dry_run=dry_run,
    )


def ensure_env_file(root: Path, *, dry_run: bool) -> Path:
    env_example = root / "pos_uniformes.env.example"
    env_file = root / "pos_uniformes.env"
    if env_file.exists():
        print(f"Archivo local ya presente: {env_file}")
        return env_file

    print("Creando pos_uniformes.env local desde el ejemplo...")
    if not dry_run:
        shutil.copy2(env_example, env_file)
    return env_file


def print_next_steps(root: Path, venv_python: Path) -> None:
    relative_python = venv_python.relative_to(root)
    print("")
    print("Siguientes pasos:")
    print(f"1. Edita {root / 'pos_uniformes.env'} con los datos locales de PostgreSQL.")
    print(f"2. Corre {relative_python} -m alembic upgrade head")
    print(f"3. Corre {relative_python} -m pos_uniformes.main")
    if os_name() == "Windows":
        print("4. Cuando quieras generar el .exe, usa scripts\\build_windows_bundle.ps1")
    else:
        print("4. Cuando quieras validar la build final de Windows, haz pull en la PC Windows y corre scripts\\build_windows_bundle.ps1 alla.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = project_root()

    print(f"Proyecto: {root}")
    print(f"Sistema detectado: {os_name()}")
    if sys.version_info[:2] != (3, 12):
        print(
            "Aviso: este proyecto esta pensado para Python 3.12. "
            f"Version actual detectada: {platform.python_version()}",
        )

    venv_python = ensure_venv(root, dry_run=args.dry_run)
    if not args.skip_install:
        install_dependencies(root, venv_python, dry_run=args.dry_run)
    if not args.skip_env_copy:
        ensure_env_file(root, dry_run=args.dry_run)
    print_next_steps(root, venv_python)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
