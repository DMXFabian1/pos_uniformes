"""Servicios reutilizables para respaldo y restauracion de PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import os
import re
import secrets
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


#: Mientras pg_dump escribe, el archivo lleva esta terminación y no `.dump` ni
#: `.sql`: nadie lo lista, nadie lo cuenta como respaldo y la rotación no lo
#: toca. Solo cuando terminó bien y pasó la revisión se publica (2026-11-09).
#: Antes pg_dump escribía directo al nombre final: un corte de luz a la mitad
#: dejaba un `.dump` trunco de más de 50 KB que pasaba por «el respaldo de hoy».
PARCIAL_SUFFIX = ".parcial"

#: Un `.parcial` solo se considera huérfano si tiene más de esto Y el proceso
#: que lo creó ya no existe. Las dos cosas: la fecha sola no basta (un pg_dump
#: esperando un bloqueo no escribe) y el PID solo tampoco (Windows los recicla).
PARCIAL_HUERFANO_HORAS = 6

#: `<nombre final>.<pid>.<al azar>.parcial`
_PARCIAL_RE = re.compile(r"\.(?P<pid>\d+)\.[0-9a-f]+" + re.escape(PARCIAL_SUFFIX) + r"$")

#: Cuántos nombres probar (`_2`, `_3`…) si el definitivo ya existe.
_MAX_NOMBRES = 50

#: El cierre que pg_dump escribe al final de un respaldo de texto (.sql).
_CIERRE_TEXTO = (b"", b"--", b"-- PostgreSQL database dump complete", b"--")
#: pg_dump 17.6+/18 abre con `\restrict <clave>` y cierra con `\unrestrict <clave>`.
_RESTRICT_RE = re.compile(rb"^\\restrict ([A-Za-z0-9]+)$", re.MULTILINE)
_UNRESTRICT_RE = re.compile(rb"^\\unrestrict ([A-Za-z0-9]+)$")

logger = logging.getLogger(__name__)


class BackupIncompletoError(RuntimeError):
    """pg_dump dejó un archivo que no se puede leer completo: no es respaldo."""


# ── Verificación ─────────────────────────────────────────────────────────────


def _sql_cerro_bien(cabeza: bytes, cola: bytes) -> bool:
    """¿El `.sql` termina con el cierre real de pg_dump?

    Las últimas líneas no vacías tienen que ser exactamente, y en este orden,
    una línea vacía, `--`, `-- PostgreSQL database dump complete` y `--`.
    Después solo puede venir `\\unrestrict <clave>` (pg_dump 18), y entonces
    la misma clave tiene que estar en el `\\restrict` del principio: así el
    cierre es de ESTE respaldo y no un dato de tabla que dice lo mismo. Si el
    principio trae `\\restrict`, el `\\unrestrict` es obligatorio. Acepta
    finales de línea de Windows (`\\r\\n`) y de Unix.
    """
    cabeza = cabeza.replace(b"\r\n", b"\n")
    lineas = cola.replace(b"\r\n", b"\n").split(b"\n")
    while lineas and not lineas[-1].strip():
        lineas.pop()
    if not lineas:
        return False

    restrict = _RESTRICT_RE.search(cabeza)
    unrestrict = _UNRESTRICT_RE.match(lineas[-1])
    if restrict is not None:
        if unrestrict is None or unrestrict.group(1) != restrict.group(1):
            return False
    elif unrestrict is not None:
        return False
    if unrestrict is not None:
        lineas.pop()
        while lineas and not lineas[-1].strip():
            lineas.pop()

    return tuple(lineas[-len(_CIERRE_TEXTO):]) == _CIERRE_TEXTO


def _verificar_respaldo(archivo: Path, dump_format: str) -> None:
    """Que el archivo sea un respaldo completo y legible, o BackupIncompletoError.

    - `.dump` (custom): `pg_restore` lo lee de punta a punta sin tocar ninguna
      base (`--file` al nulo). Probado con el respaldo real de la tienda: 114
      cortes, desde el 1 % hasta quitarle 1 byte, todos rechazados.
      Sin `--exit-on-error`: escribiendo a archivo los errores de lectura ya
      son fatales; en 36 casos (truncados y corruptos) daba lo mismo con y sin.
    - `.sql` (plain): ver `_sql_cerro_bien`.
    """
    try:
        tamano = archivo.stat().st_size
    except OSError as exc:
        raise BackupIncompletoError(f"el respaldo no quedó en disco ({exc})") from exc
    if tamano == 0:
        raise BackupIncompletoError("el respaldo quedó vacío (0 bytes)")

    if dump_format == "custom":
        pg_restore_path = _resolve_postgres_binary("pg_restore")
        resultado = subprocess.run(
            [pg_restore_path, "--file", os.devnull, str(archivo)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if resultado.returncode != 0:
            detalle = (resultado.stderr or resultado.stdout or "").strip().splitlines()
            raise BackupIncompletoError(
                "el respaldo está incompleto o dañado (pg_restore no lo pudo leer"
                + (f": {detalle[-1]}" if detalle else "")
                + ")"
            )
        return

    with archivo.open("rb") as fh:
        cabeza = fh.read(8192)
        fh.seek(max(0, tamano - 4096))
        cola = fh.read()
    if not _sql_cerro_bien(cabeza, cola):
        raise BackupIncompletoError("el respaldo de texto no terminó (falta el cierre de pg_dump)")


def _asentar_en_disco(archivo: Path) -> None:
    """Que lo escrito esté en el disco y no solo en la memoria de Windows antes
    de publicarlo: un apagón justo después dejaría un archivo con el nombre
    bueno y el contenido a medias."""
    with archivo.open("rb+") as fh:
        os.fsync(fh.fileno())


# ── Publicar sin pisar ───────────────────────────────────────────────────────


def _enlazar_sin_pisar(origen: Path, destino: Path) -> None:
    """Le da a `origen` el nombre `destino` de un solo golpe, o FileExistsError.

    Windows: `os.rename` (MoveFileExW sin REPLACE_EXISTING) falla si el destino
    existe. POSIX: `os.rename` pisaría, así que se hace `link` (falla si existe)
    y luego se quita el nombre viejo. Nunca `os.replace`."""
    if os.name == "nt":
        os.rename(origen, destino)
        return
    os.link(origen, destino)
    try:
        os.unlink(origen)
    except OSError:
        # El respaldo ya está publicado; el nombre viejo es un `.parcial` que
        # nadie lista y que la limpieza quitará cuando su proceso no exista.
        logger.warning("Respaldo publicado, pero quedó el temporal %s", origen)


def _publicar_sin_pisar(parcial: Path, deseado: Path) -> Path:
    """Publica `parcial` como `deseado`, o `<stem>_2<ext>`, `_3`… si ya existe."""
    for n in range(1, _MAX_NOMBRES + 1):
        destino = deseado if n == 1 else deseado.with_name(f"{deseado.stem}_{n}{deseado.suffix}")
        try:
            _enlazar_sin_pisar(parcial, destino)
        except FileExistsError:
            continue
        return destino
    raise FileExistsError(f"ya existen {_MAX_NOMBRES} respaldos llamados {deseado.stem}*")


# ── Huérfanos ────────────────────────────────────────────────────────────────


def _proceso_existe(pid: int) -> bool | None:
    """True si existe, False si seguro que no, None si no se pudo saber.

    Un PID reciclado (otro programa con el mismo número) cuenta como vivo: se
    prefiere dejar un `.parcial` de más que borrar uno que está en uso."""
    if pid <= 0:
        return None
    if pid == os.getpid():
        return True
    if os.name == "nt":
        return _proceso_existe_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True          # existe, pero es de otro usuario
    except OSError:
        return None
    return True


def _proceso_existe_windows(pid: int) -> bool | None:
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    ERROR_INVALID_PARAMETER = 87
    ERROR_ACCESS_DENIED = 5
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == ERROR_INVALID_PARAMETER:
                return False     # no hay proceso con ese PID
            if error == ERROR_ACCESS_DENIED:
                return True      # existe (de otro usuario o protegido)
            return None
        try:
            codigo = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(codigo)):
                return None
            return codigo.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001 — ante la duda, vivo
        return None


def limpiar_parciales_huerfanos(target_dir: Path, *, horas: int = PARCIAL_HUERFANO_HORAS) -> list[Path]:
    """Borra los `.parcial` de respaldos que se cortaron.

    Solo si tiene más de `horas` Y el proceso que lo creó (su PID va en el
    nombre) ya no existe. Si el nombre no trae PID, o no se puede saber si el
    proceso vive, se queda. Nunca toca un `.dump` ni un `.sql`. Si Windows no
    deja borrarlo (alguien lo tiene abierto), se queda para la próxima."""
    limite = datetime.now() - timedelta(hours=horas)
    borrados: list[Path] = []
    for parcial in target_dir.glob(f"*{PARCIAL_SUFFIX}"):
        try:
            if not parcial.is_file() or datetime.fromtimestamp(parcial.stat().st_mtime) >= limite:
                continue
            nombre = _PARCIAL_RE.search(parcial.name)
            if nombre is None:
                continue
            if _proceso_existe(int(nombre.group("pid"))) is not False:
                continue
            parcial.unlink()
            borrados.append(parcial)
        except OSError:
            continue
    return borrados


# ── El respaldo ─────────────────────────────────────────────────────────────


def _quitar_parcial(parcial: Path, causa: BaseException) -> None:
    """Borra el temporal de un respaldo que falló sin tapar el error que lo hizo
    fallar: si el borrado también falla, se anota en el error original y en el
    log, y el que se propaga sigue siendo el original."""
    try:
        parcial.unlink(missing_ok=True)
    except OSError as exc:
        nota = f"Además no se pudo borrar el temporal {parcial.name}: {exc}"
        causa.add_note(nota)
        logger.warning("%s (el respaldo falló por: %s: %s)", nota, type(causa).__name__, causa)


def create_backup(output_dir: Path | None = None, dump_format: str = "plain", retention_days: int = 7) -> tuple[Path, list[Path]]:
    """Hace un respaldo completo y verificado, o truena sin dejar nada que parezca uno.

    pg_dump escribe a `<nombre>.<pid>.<al azar>.parcial`. Si sale bien y el
    archivo se puede leer completo, se asienta en disco y se publica con su
    nombre final de un solo golpe, sin pisar ningún respaldo que ya exista
    (`_2`, `_3`… si el nombre está ocupado). Si algo falla, el temporal se
    borra, el error original es el que sale, y los respaldos anteriores quedan
    como estaban: la rotación solo corre después de un respaldo bueno."""
    target_dir = (output_dir or backup_output_dir()).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    limpiar_parciales_huerfanos(target_dir)
    pg_dump_path = _resolve_postgres_binary("pg_dump")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = "dump" if dump_format == "custom" else "sql"
    output_file = target_dir / f"{settings.db_name}_{timestamp}.{extension}"
    parcial = output_file.with_name(f"{output_file.name}.{os.getpid()}.{secrets.token_hex(4)}{PARCIAL_SUFFIX}")
    command = _build_backup_command(pg_dump_path, parcial, dump_format)
    try:
        subprocess.run(command, check=True, env=_base_env())
        _verificar_respaldo(parcial, dump_format)
        _asentar_en_disco(parcial)
        output_file = _publicar_sin_pisar(parcial, output_file)
    except BaseException as exc:
        _quitar_parcial(parcial, exc)
        raise
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
    started_at = datetime.now(timezone.utc)
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
