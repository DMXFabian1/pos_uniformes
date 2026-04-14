"""Lanzador de desarrollo para Windows con tiempos visibles por paso."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def os_name() -> str:
    return platform.system() or sys.platform


def venv_python_path(root: Path) -> Path:
    return root / ".venv" / "Scripts" / "python.exe"


def env_example_path(root: Path) -> Path:
    return root / "pos_uniformes.env.example"


def env_path(root: Path) -> Path:
    return root / "pos_uniformes.env"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Corre migraciones, precheck y abre POS Uniformes en Windows con mensajes de avance.",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="No corre `alembic upgrade head` antes de abrir la app.",
    )
    parser.add_argument(
        "--skip-precheck",
        action="store_true",
        help="No corre `check_startup_health.py` antes de abrir la app.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra los pasos, sin ejecutarlos.",
    )
    return parser.parse_args(argv)


def format_elapsed(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds:.2f}s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, remainder = divmod(seconds, 60)
    return f"{int(minutes)}m {remainder:.1f}s"


def print_step(title: str) -> float:
    started_at = time.monotonic()
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {title}")
    return started_at


def run_command(command: list[str], *, cwd: Path, dry_run: bool) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"$ {printable}")
    if dry_run:
        return
    subprocess.run(command, cwd=cwd, check=True)


def run_timed_command(title: str, command: list[str], *, cwd: Path, dry_run: bool) -> None:
    started_at = print_step(title)
    run_command(command, cwd=cwd, dry_run=dry_run)
    elapsed = format_elapsed(time.monotonic() - started_at)
    print(f"  OK en {elapsed}")


def ensure_env_file(root: Path, *, dry_run: bool) -> bool:
    target = env_path(root)
    if target.exists():
        print(f"Archivo local detectado: {target}")
        return True

    example = env_example_path(root)
    print(f"No existe {target.name}; se copiara desde el ejemplo.")
    if not dry_run:
        shutil.copy2(example, target)
    print(f"Revisa y edita este archivo antes de volver a correr el script: {target}")
    return False


def launch_app(root: Path, venv_python: Path, *, dry_run: bool) -> None:
    started_at = print_step("Lanzando POS Uniformes...")
    command = [str(venv_python), str(root / "main.py")]
    printable = " ".join(command)
    print(f"$ {printable}")
    if dry_run:
        print("  Nota: dry-run; la app no se abrio.")
        return
    process = subprocess.Popen(command, cwd=root)
    elapsed = format_elapsed(time.monotonic() - started_at)
    print(f"  Proceso lanzado en {elapsed} (PID {process.pid})")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = project_root()

    if os_name() != "Windows":
        raise SystemExit("Este script esta pensado para correrse en una PC Windows.")

    venv_python = venv_python_path(root)
    if not venv_python.exists():
        raise SystemExit(
            "No existe la .venv del proyecto. Primero corre "
            "`py scripts\\setup_dev_env.py` o `py pos_uniformes\\scripts\\windows_build_runner.py --dry-run`."
        )

    print(f"Proyecto: {root}")
    print(f"Python de trabajo: {venv_python}")

    if not ensure_env_file(root, dry_run=args.dry_run):
        return 1

    if not args.skip_migrations:
        run_timed_command(
            "Aplicando migraciones...",
            [str(venv_python), "-m", "alembic", "upgrade", "head"],
            cwd=root,
            dry_run=args.dry_run,
        )

    if not args.skip_precheck:
        run_timed_command(
            "Ejecutando precheck...",
            [str(venv_python), str(root / "scripts" / "check_startup_health.py")],
            cwd=root,
            dry_run=args.dry_run,
        )

    launch_app(root, venv_python, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
