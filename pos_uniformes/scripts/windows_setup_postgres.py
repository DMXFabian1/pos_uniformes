"""Instala/configura PostgreSQL local para probar POS Uniformes en Windows."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import platform
import re
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
        description="Instala PostgreSQL local y deja listo POS Uniformes en una PC Windows.",
    )
    parser.add_argument(
        "--install-postgres",
        action="store_true",
        help="Lanza la instalacion de PostgreSQL via winget si no esta instalado.",
    )
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", default="5432")
    parser.add_argument("--db-name", default="pos_uniformes")
    parser.add_argument("--db-user", default="postgres")
    parser.add_argument("--db-password", default="")
    parser.add_argument("--admin-user", default="")
    parser.add_argument("--admin-password", default="")
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="No corre `alembic upgrade head` al final.",
    )
    parser.add_argument(
        "--skip-precheck",
        action="store_true",
        help="No corre `check_startup_health.py` al final.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo imprime los pasos.",
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


def run_command(
    command: list[str],
    *,
    cwd: Path,
    dry_run: bool,
    extra_env: dict[str, str] | None = None,
) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"$ {printable}")
    if dry_run:
        return
    merged_env = os.environ.copy()
    if extra_env:
        merged_env.update(extra_env)
    subprocess.run(command, cwd=cwd, check=True, env=merged_env)


def run_timed_command(
    title: str,
    command: list[str],
    *,
    cwd: Path,
    dry_run: bool,
    extra_env: dict[str, str] | None = None,
) -> None:
    started_at = print_step(title)
    run_command(command, cwd=cwd, dry_run=dry_run, extra_env=extra_env)
    print(f"  OK en {format_elapsed(time.monotonic() - started_at)}")


def resolve_postgres_binary(binary_name: str) -> Path | None:
    direct = shutil.which(binary_name)
    if direct:
        return Path(direct)

    roots = [
        Path(r"C:\Program Files\PostgreSQL"),
        Path(r"C:\Program Files (x86)\PostgreSQL"),
    ]
    for root in roots:
        if not root.exists():
            continue
        for match in sorted(root.iterdir(), reverse=True):
            candidate = match / "bin" / binary_name
            if candidate.exists():
                return candidate
    return None


def postgres_is_installed() -> bool:
    return resolve_postgres_binary("psql.exe") is not None


def install_postgres_via_winget(*, cwd: Path, dry_run: bool) -> None:
    run_timed_command(
        "Instalando PostgreSQL via winget...",
        [
            "winget",
            "install",
            "--id",
            "PostgreSQL.PostgreSQL",
            "-e",
            "--source",
            "winget",
            "--interactive",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        cwd=cwd,
        dry_run=dry_run,
    )


def ensure_env_file(root: Path, *, dry_run: bool) -> Path:
    target = env_path(root)
    if target.exists():
        return target
    print(f"No existe {target.name}; se copiara desde el ejemplo.")
    if not dry_run:
        shutil.copy2(env_example_path(root), target)
    return target


def replace_env_value(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    replacement = f"{key}={value}"
    if pattern.search(content):
        return pattern.sub(replacement, content)
    suffix = "" if content.endswith("\n") or not content else "\n"
    return f"{content}{suffix}{replacement}\n"


def write_env_file(root: Path, args: argparse.Namespace, *, dry_run: bool) -> Path:
    target = ensure_env_file(root, dry_run=dry_run)
    if dry_run:
        print(f"Se actualizaria {target}")
        return target

    content = target.read_text(encoding="utf-8")
    content = replace_env_value(content, "POS_UNIFORMES_DB_HOST", args.db_host)
    content = replace_env_value(content, "POS_UNIFORMES_DB_PORT", args.db_port)
    content = replace_env_value(content, "POS_UNIFORMES_DB_NAME", args.db_name)
    content = replace_env_value(content, "POS_UNIFORMES_DB_USER", args.db_user)
    content = replace_env_value(content, "POS_UNIFORMES_DB_PASSWORD", args.db_password)
    content = replace_env_value(content, "POS_UNIFORMES_AUTO_CREATE_SCHEMA", "0")
    target.write_text(content, encoding="utf-8")
    return target


def resolve_passwords(args: argparse.Namespace) -> tuple[str, str, str]:
    db_password = args.db_password
    if not db_password:
        db_password = getpass.getpass("Password para el usuario de la app (DB user): ")

    admin_user = args.admin_user or args.db_user
    admin_password = args.admin_password or db_password
    if args.admin_user and not args.admin_password:
        admin_password = getpass.getpass(f"Password para {admin_user}: ")

    return db_password, admin_user, admin_password


def database_exists(
    *,
    psql_path: Path,
    args: argparse.Namespace,
    admin_user: str,
    admin_password: str,
    root: Path,
    dry_run: bool,
) -> bool:
    if dry_run:
        print("Se verificaria si la base ya existe.")
        return False

    command = [
        str(psql_path),
        "--host",
        args.db_host,
        "--port",
        args.db_port,
        "--username",
        admin_user,
        "--dbname",
        "postgres",
        "--tuples-only",
        "--no-align",
        "--command",
        f"SELECT 1 FROM pg_database WHERE datname = '{args.db_name}';",
    ]
    result = subprocess.run(
        command,
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PGPASSWORD": admin_password},
    )
    return result.stdout.strip() == "1"


def create_database(
    *,
    createdb_path: Path,
    args: argparse.Namespace,
    admin_user: str,
    admin_password: str,
    root: Path,
    dry_run: bool,
) -> None:
    run_timed_command(
        f"Creando base {args.db_name}...",
        [
            str(createdb_path),
            "--host",
            args.db_host,
            "--port",
            args.db_port,
            "--username",
            admin_user,
            "--owner",
            args.db_user,
            args.db_name,
        ],
        cwd=root,
        dry_run=dry_run,
        extra_env={"PGPASSWORD": admin_password},
    )


def validate_prereqs(root: Path) -> None:
    if os_name() != "Windows":
        raise SystemExit("Este script esta pensado para correrse en una PC Windows.")
    venv_python = venv_python_path(root)
    if not venv_python.exists():
        raise SystemExit(
            "No existe la .venv del proyecto. Primero corre "
            "`py pos_uniformes\\scripts\\windows_build_runner.py --dry-run`."
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = project_root()
    validate_prereqs(root)

    print(f"Proyecto: {root}")
    print(f"Base objetivo: {args.db_name} @ {args.db_host}:{args.db_port}")

    if args.install_postgres and not postgres_is_installed():
        install_postgres_via_winget(cwd=root, dry_run=args.dry_run)

    psql_path = resolve_postgres_binary("psql.exe")
    createdb_path = resolve_postgres_binary("createdb.exe")
    if not psql_path or not createdb_path:
        raise SystemExit(
            "No se encontraron `psql.exe` y `createdb.exe`. Instala PostgreSQL primero "
            "o corre este script con `--install-postgres`."
        )

    db_password, admin_user, admin_password = resolve_passwords(args)
    args.db_password = db_password

    started_at = print_step("Actualizando pos_uniformes.env...")
    env_file = write_env_file(root, args, dry_run=args.dry_run)
    print(f"  OK en {format_elapsed(time.monotonic() - started_at)}")
    print(f"  ENV: {env_file}")

    if database_exists(
        psql_path=psql_path,
        args=args,
        admin_user=admin_user,
        admin_password=admin_password,
        root=root,
        dry_run=args.dry_run,
    ):
        print(f"Base detectada: {args.db_name}")
    else:
        create_database(
            createdb_path=createdb_path,
            args=args,
            admin_user=admin_user,
            admin_password=admin_password,
            root=root,
            dry_run=args.dry_run,
        )

    venv_python = venv_python_path(root)
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

    print("")
    print("Setup PostgreSQL listo.")
    print(f"  ENV: {env_file}")
    print(f"  Base: {args.db_name}")
    print("  Siguiente paso: corre `py -3.12 pos_uniformes\\scripts\\windows_run_dev.py`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
