"""Wrapper para usar una PC Windows solo como maquina de build."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import subprocess
import sys


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def os_name() -> str:
    return platform.system() or sys.platform


def venv_python_path(root: Path) -> Path:
    return root / ".venv" / "Scripts" / "python.exe"


def version_path(root: Path) -> Path:
    return root / "VERSION"


def read_version(root: Path) -> str:
    return version_path(root).read_text(encoding="utf-8").strip()


def bundle_zip_path(root: Path, version: str) -> Path:
    return root / "dist" / f"POSUniformes-{version}-windows.zip"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Actualiza la rama y genera el bundle portable de Windows para POS Uniformes.",
    )
    parser.add_argument(
        "--branch",
        default="",
        help="Rama que se va a actualizar y empaquetar. Si no se pasa, usa la rama actual.",
    )
    parser.add_argument(
        "--skip-git",
        action="store_true",
        help="No hace fetch/checkout/pull antes de empaquetar.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="No reinstala dependencias en la .venv antes de empaquetar.",
    )
    parser.add_argument(
        "--with-precheck",
        action="store_true",
        help="Ejecuta el precheck de base dentro del build.",
    )
    parser.add_argument(
        "--create-seed-backup",
        action="store_true",
        help="Incluye una semilla generada desde la base local.",
    )
    parser.add_argument(
        "--seed-backup-path",
        default="",
        help="Ruta a un .dump existente para incluirlo como semilla.",
    )
    parser.add_argument(
        "--brother-driver-installer-path",
        default="",
        help="Ruta al instalador oficial del driver Brother a incluir en el bundle.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra comandos sin ejecutarlos.",
    )
    return parser.parse_args(argv)


def run_command(command: list[str], *, cwd: Path, dry_run: bool) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"$ {printable}")
    if dry_run:
        return
    subprocess.run(command, cwd=cwd, check=True)


def current_branch(root: Path) -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def local_branch_exists(root: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "show-ref", "--verify", f"refs/heads/{branch}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def build_git_commands(root: Path, branch: str) -> list[list[str]]:
    commands: list[list[str]] = [["git", "fetch", "origin", branch]]
    if local_branch_exists(root, branch):
        commands.append(["git", "checkout", branch])
    else:
        commands.append(["git", "checkout", "-B", branch, f"origin/{branch}"])
    commands.append(["git", "pull", "--ff-only", "origin", branch])
    return commands


def ensure_venv(root: Path, *, dry_run: bool) -> Path:
    venv_python = venv_python_path(root)
    if venv_python.exists():
        print(f"Entorno virtual detectado: {venv_python}")
        return venv_python

    run_command(["py", "-3.12", "-m", "venv", str(root / ".venv")], cwd=root, dry_run=dry_run)
    return venv_python


def install_dependencies(root: Path, venv_python: Path, *, dry_run: bool) -> None:
    run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], cwd=root, dry_run=dry_run)
    run_command(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "-r",
            str(root / "requirements.txt"),
            "-r",
            str(root / "requirements-build.txt"),
        ],
        cwd=root,
        dry_run=dry_run,
    )


def build_bundle_command(root: Path, args: argparse.Namespace) -> list[str]:
    command = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(root / "scripts" / "build_windows_bundle.ps1"),
    ]
    if args.with_precheck:
        command.append("-WithPrecheck")
    if args.create_seed_backup:
        command.append("-CreateSeedBackup")
    if args.seed_backup_path:
        command.extend(["-SeedBackupPath", args.seed_backup_path])
    if args.brother_driver_installer_path:
        command.extend(["-BrotherDriverInstallerPath", args.brother_driver_installer_path])
    return command


def validate_args(args: argparse.Namespace) -> None:
    if args.create_seed_backup and args.seed_backup_path:
        raise SystemExit("Usa solo una opcion de semilla: --create-seed-backup o --seed-backup-path.")


def print_summary(root: Path, branch: str, *, dry_run: bool) -> None:
    version = read_version(root)
    zip_path = bundle_zip_path(root, version)
    print("")
    print("Build Windows preparada:")
    print(f"  Rama:    {branch}")
    print(f"  Version: {version}")
    print(f"  ZIP:     {zip_path}")
    if dry_run:
        print("  Nota:    dry-run; no se genero ningun archivo.")
    else:
        print("  Siguiente paso: copia ese zip a la PC de pruebas y valida el .exe ahi.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    validate_args(args)
    root = project_root()

    if os_name() != "Windows":
        raise SystemExit("Este script esta pensado para correrse en una PC Windows.")

    branch = args.branch or current_branch(root)
    print(f"Proyecto: {root}")
    print(f"Rama de build: {branch}")

    if not args.skip_git:
        for command in build_git_commands(root, branch):
            run_command(command, cwd=root, dry_run=args.dry_run)

    venv_python = ensure_venv(root, dry_run=args.dry_run)
    if not args.skip_install:
        install_dependencies(root, venv_python, dry_run=args.dry_run)

    run_command(build_bundle_command(root, args), cwd=root, dry_run=args.dry_run)
    print_summary(root, branch, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
