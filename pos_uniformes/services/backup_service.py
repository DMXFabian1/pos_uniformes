"""Servicios reutilizables para respaldo y restauracion de PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
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


@dataclass(frozen=True)
class AutomaticBackupStatus:
    last_run_at: datetime | None
    last_success_at: datetime | None
    last_backup_path: Path | None
    dump_format: str | None
    retention_days: int | None
    deleted_count: int
    last_error: str | None
    external_copy_dir: Path | None = None
    external_last_success_at: datetime | None = None
    external_last_backup_path: Path | None = None
    external_last_error: str | None = None


def backup_output_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "backups" / "database"


def configured_external_backup_dir() -> Path | None:
    if not settings.backup_external_dir:
        return None
    return Path(settings.backup_external_dir).expanduser().resolve()


def automatic_backup_status_path(output_dir: Path | None = None) -> Path:
    target_dir = (output_dir or backup_output_dir()).expanduser().resolve()
    return target_dir / ".automatic_backup_status.json"


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


def _serialize_optional_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _status_to_payload(status: AutomaticBackupStatus) -> dict[str, object]:
    return {
        "last_run_at": _serialize_optional_datetime(status.last_run_at),
        "last_success_at": _serialize_optional_datetime(status.last_success_at),
        "last_backup_path": str(status.last_backup_path) if status.last_backup_path else None,
        "dump_format": status.dump_format,
        "retention_days": status.retention_days,
        "deleted_count": status.deleted_count,
        "last_error": status.last_error,
        "external_copy_dir": str(status.external_copy_dir) if status.external_copy_dir else None,
        "external_last_success_at": _serialize_optional_datetime(status.external_last_success_at),
        "external_last_backup_path": str(status.external_last_backup_path) if status.external_last_backup_path else None,
        "external_last_error": status.external_last_error,
    }


def _status_from_payload(payload: dict[str, object]) -> AutomaticBackupStatus:
    backup_path_value = payload.get("last_backup_path")
    external_copy_dir_value = payload.get("external_copy_dir")
    external_backup_path_value = payload.get("external_last_backup_path")
    return AutomaticBackupStatus(
        last_run_at=_parse_optional_datetime(payload.get("last_run_at") if isinstance(payload.get("last_run_at"), str) else None),
        last_success_at=_parse_optional_datetime(
            payload.get("last_success_at") if isinstance(payload.get("last_success_at"), str) else None
        ),
        last_backup_path=Path(backup_path_value) if isinstance(backup_path_value, str) and backup_path_value else None,
        dump_format=payload.get("dump_format") if isinstance(payload.get("dump_format"), str) else None,
        retention_days=int(payload["retention_days"]) if payload.get("retention_days") is not None else None,
        deleted_count=int(payload.get("deleted_count") or 0),
        last_error=payload.get("last_error") if isinstance(payload.get("last_error"), str) else None,
        external_copy_dir=(
            Path(external_copy_dir_value)
            if isinstance(external_copy_dir_value, str) and external_copy_dir_value
            else None
        ),
        external_last_success_at=_parse_optional_datetime(
            payload.get("external_last_success_at")
            if isinstance(payload.get("external_last_success_at"), str)
            else None
        ),
        external_last_backup_path=(
            Path(external_backup_path_value)
            if isinstance(external_backup_path_value, str) and external_backup_path_value
            else None
        ),
        external_last_error=payload.get("external_last_error")
        if isinstance(payload.get("external_last_error"), str)
        else None,
    )


def read_automatic_backup_status(output_dir: Path | None = None) -> AutomaticBackupStatus | None:
    status_path = automatic_backup_status_path(output_dir)
    if not status_path.exists():
        return None
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("El archivo de estado del respaldo automatico es invalido.")
    return _status_from_payload(payload)


def write_automatic_backup_status(
    status: AutomaticBackupStatus,
    *,
    output_dir: Path | None = None,
) -> Path:
    status_path = automatic_backup_status_path(output_dir)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(_status_to_payload(status), ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return status_path


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


def copy_backup_to_external(backup_file: Path, external_dir: Path) -> Path:
    source_path = backup_file.expanduser().resolve()
    target_dir = external_dir.expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / source_path.name
    shutil.copy2(source_path, target_path)
    return target_path


def run_automatic_backup(
    *,
    output_dir: Path | None = None,
    dump_format: str = "custom",
    retention_days: int = 14,
    external_dir: Path | None = None,
) -> tuple[Path, list[Path], AutomaticBackupStatus]:
    target_dir = (output_dir or backup_output_dir()).expanduser().resolve()
    previous_status = read_automatic_backup_status(target_dir)
    resolved_external_dir = (external_dir.expanduser().resolve() if external_dir is not None else configured_external_backup_dir())
    started_at = datetime.now()
    try:
        backup_file, deleted_files = create_backup(
            output_dir=target_dir,
            dump_format=dump_format,
            retention_days=retention_days,
        )
    except Exception as exc:  # noqa: BLE001
        failed_status = AutomaticBackupStatus(
            last_run_at=started_at,
            last_success_at=previous_status.last_success_at if previous_status else None,
            last_backup_path=previous_status.last_backup_path if previous_status else None,
            dump_format=previous_status.dump_format if previous_status else dump_format,
            retention_days=retention_days,
            deleted_count=previous_status.deleted_count if previous_status else 0,
            last_error=str(exc),
            external_copy_dir=(
                resolved_external_dir
                if resolved_external_dir is not None
                else previous_status.external_copy_dir if previous_status else None
            ),
            external_last_success_at=previous_status.external_last_success_at if previous_status else None,
            external_last_backup_path=previous_status.external_last_backup_path if previous_status else None,
            external_last_error=previous_status.external_last_error if previous_status else None,
        )
        write_automatic_backup_status(failed_status, output_dir=target_dir)
        raise

    external_backup_path: Path | None = previous_status.external_last_backup_path if previous_status else None
    external_last_success_at = previous_status.external_last_success_at if previous_status else None
    external_last_error = previous_status.external_last_error if previous_status else None
    if resolved_external_dir is not None:
        try:
            external_backup_path = copy_backup_to_external(backup_file, resolved_external_dir)
            external_last_success_at = started_at
            external_last_error = None
        except Exception as exc:  # noqa: BLE001
            external_last_error = str(exc)

    status = AutomaticBackupStatus(
        last_run_at=started_at,
        last_success_at=started_at,
        last_backup_path=backup_file,
        dump_format=dump_format,
        retention_days=retention_days,
        deleted_count=len(deleted_files),
        last_error=None,
        external_copy_dir=resolved_external_dir,
        external_last_success_at=external_last_success_at,
        external_last_backup_path=external_backup_path,
        external_last_error=external_last_error,
    )
    write_automatic_backup_status(status, output_dir=target_dir)
    return backup_file, deleted_files, status


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
