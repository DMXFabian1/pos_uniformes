"""Servicios reutilizables para respaldo y restauracion de PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import os
import shutil
import subprocess
from typing import Sequence

from pos_uniformes.utils.config import settings

WINDOWS_PG_DIRS = (
    Path("C:/Program Files/PostgreSQL"),
    Path("C:/Program Files (x86)/PostgreSQL"),
)

POSTGRES_APP_BIN = Path("/Applications/Postgres.app/Contents/Versions/latest/bin")


@dataclass(frozen=True)
class BackupEntry:
    path: Path
    dump_format: str
    modified_at: datetime
    size_bytes: int


def backup_output_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "backups" / "database"


def _resolve_postgres_binary(binary_name: str, windows_name: str | None = None) -> str:
    direct = shutil.which(binary_name)
    if direct:
        return direct

    app_candidate = POSTGRES_APP_BIN / binary_name
    if app_candidate.exists():
        return str(app_candidate)

    executable_name = windows_name or f"{binary_name}.exe"
    for base_dir in WINDOWS_PG_DIRS:
        if not base_dir.exists():
            continue
        candidates = sorted(base_dir.glob(f"*/bin/{executable_name}"), reverse=True)
        if candidates:
            return str(candidates[0])

    raise FileNotFoundError(
        f"No se encontro '{binary_name}'. Agrega PostgreSQL al PATH o instala Postgres.app/PostgreSQL."
    )


def _build_backup_command(pg_dump_path: str, output_file: Path, dump_format: str) -> Sequence[str]:
    command = [
        pg_dump_path,
        "--host",
        settings.db_host,
        "--port",
        str(settings.db_port),
        "--username",
        settings.db_user,
        "--dbname",
        settings.db_name,
        "--no-owner",
        "--no-privileges",
        "--verbose",
        "--file",
        str(output_file),
    ]
    if dump_format == "custom":
        command.extend(["--format", "custom"])
    else:
        command.extend(["--format", "plain"])
    return command


def _backup_suffix(dump_format: str) -> str:
    return ".dump" if dump_format == "custom" else ".sql"


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = settings.db_password
    return env


def prune_old_backups(output_dir: Path, dump_format: str, retention_days: int) -> list[Path]:
    if retention_days < 0:
        raise ValueError("retention_days no puede ser negativo.")

    suffix = _backup_suffix(dump_format)
    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted: list[Path] = []
    for backup_file in sorted(output_dir.glob(f"*{suffix}")):
        modified_at = datetime.fromtimestamp(backup_file.stat().st_mtime)
        if modified_at >= cutoff:
            continue
        backup_file.unlink(missing_ok=True)
        deleted.append(backup_file)
    return deleted


def create_backup(output_dir: Path | None = None, dump_format: str = "plain", retention_days: int = 7) -> tuple[Path, list[Path]]:
    target_dir = (output_dir or backup_output_dir()).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    pg_dump_path = _resolve_postgres_binary("pg_dump")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = "dump" if dump_format == "custom" else "sql"
    output_file = target_dir / f"{settings.db_name}_{timestamp}.{extension}"
    command = _build_backup_command(pg_dump_path, output_file, dump_format)
    subprocess.run(command, check=True, env=_base_env())
    deleted_files = prune_old_backups(target_dir, dump_format, retention_days)
    return output_file, deleted_files


def list_backups(output_dir: Path | None = None) -> list[BackupEntry]:
    target_dir = (output_dir or backup_output_dir()).expanduser().resolve()
    if not target_dir.exists():
        return []

    backups: list[BackupEntry] = []
    for path in sorted(target_dir.glob("*"), reverse=True):
        if path.suffix not in {".sql", ".dump"} or not path.is_file():
            continue
        backups.append(
            BackupEntry(
                path=path,
                dump_format="custom" if path.suffix == ".dump" else "plain",
                modified_at=datetime.fromtimestamp(path.stat().st_mtime),
                size_bytes=path.stat().st_size,
            )
        )
    return backups


def format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def restore_backup(backup_file: Path) -> None:
    backup_path = backup_file.expanduser().resolve()
    if not backup_path.exists():
        raise FileNotFoundError(f"No existe el respaldo seleccionado: {backup_path}")
    if backup_path.suffix != ".dump":
        raise ValueError("La restauracion desde la app solo soporta respaldos .dump.")

    pg_restore_path = _resolve_postgres_binary("pg_restore")
    command = [
        pg_restore_path,
        "--host",
        settings.db_host,
        "--port",
        str(settings.db_port),
        "--username",
        settings.db_user,
        "--dbname",
        settings.db_name,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--verbose",
        str(backup_path),
    ]
    subprocess.run(command, check=True, env=_base_env())
