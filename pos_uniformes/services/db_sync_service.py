"""Sincroniza la base de datos remota (Windows) a la local (Mac).

Usa pg_dump/pg_restore para clonar la DB de producción al PostgreSQL local.
Solo se ejecuta cuando:
  1. El host configurado NO es localhost (hay un remoto configurado)
  2. El remoto responde a TCP en el puerto de PostgreSQL
  3. El local tiene PostgreSQL corriendo
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 3


def _load_env() -> dict[str, str]:
    """Carga las variables de conexión desde el .env del proyecto."""
    env_candidates = [
        Path(__file__).resolve().parent.parent / "pos_uniformes.env",
    ]
    for p in env_candidates:
        if p.exists():
            result: dict[str, str] = {}
            for line in p.read_text().splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    result[k.strip()] = v.strip()
            return result
    return {}


def _tcp_probe(host: str, port: int, timeout: float = _DEFAULT_TIMEOUT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def _find_pg_tool(name: str) -> str | None:
    """Busca pg_dump / pg_restore / psql en PATH o en Postgres.app."""
    # PATH primero
    import shutil
    found = shutil.which(name)
    if found:
        return found
    # Postgres.app (macOS)
    pg_app = Path("/Applications/Postgres.app/Contents/Versions/latest/bin") / name
    if pg_app.exists():
        return str(pg_app)
    return None


def can_sync() -> tuple[bool, str]:
    """Verifica si es posible sincronizar. Retorna (ok, motivo)."""
    env = _load_env()
    remote_host = env.get("POS_UNIFORMES_DB_HOST", "localhost")
    port = int(env.get("POS_UNIFORMES_DB_PORT", "5432"))

    if remote_host in ("localhost", "127.0.0.1", "::1"):
        return False, "Host configurado es localhost — no hay remoto"

    if not _tcp_probe(remote_host, port):
        return False, f"No se puede conectar a {remote_host}:{port}"

    if not _tcp_probe("localhost", port):
        return False, "PostgreSQL local no está corriendo"

    if not _find_pg_tool("pg_dump"):
        return False, "pg_dump no encontrado"

    return True, "OK"


def sync_remote_to_local(
    *,
    on_progress: object | None = None,
) -> tuple[bool, str]:
    """Clona la DB remota a la local usando pg_dump → psql.

    Returns (success, message).
    """
    env = _load_env()
    remote_host = env.get("POS_UNIFORMES_DB_HOST", "localhost")
    port = int(env.get("POS_UNIFORMES_DB_PORT", "5432"))
    db_name = env.get("POS_UNIFORMES_DB_NAME", "pos_uniformes")
    user = env.get("POS_UNIFORMES_DB_USER", "postgres")
    password = env.get("POS_UNIFORMES_DB_PASSWORD", "")

    ok, reason = can_sync()
    if not ok:
        return False, reason

    pg_dump = _find_pg_tool("pg_dump")
    psql = _find_pg_tool("psql")
    if not pg_dump or not psql:
        return False, "pg_dump o psql no encontrados"

    pg_env = os.environ.copy()
    pg_env["PGPASSWORD"] = password

    # 1. Dump remoto a archivo temporal
    if on_progress:
        on_progress("Descargando DB remota...")
    logger.info("Sincronizando DB: %s:%d/%s → localhost/%s", remote_host, port, db_name, db_name)

    try:
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
            tmp_path = tmp.name

        result = subprocess.run(
            [
                pg_dump,
                "-h", remote_host,
                "-p", str(port),
                "-U", user,
                "-d", db_name,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "-f", tmp_path,
            ],
            env=pg_env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.warning("pg_dump falló: %s", result.stderr)
            return False, f"pg_dump falló: {result.stderr[:200]}"

        dump_size = Path(tmp_path).stat().st_size
        logger.info("Dump completado: %.1f MB", dump_size / 1024 / 1024)

        # 2. Restaurar en local
        if on_progress:
            on_progress("Restaurando en local...")

        result = subprocess.run(
            [
                psql,
                "-h", "localhost",
                "-p", str(port),
                "-U", user,
                "-d", db_name,
                "-f", tmp_path,
                "--quiet",
            ],
            env=pg_env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        # psql puede tener warnings pero funcionar. Solo fallamos si returncode != 0
        if result.returncode != 0:
            logger.warning("psql restore falló: %s", result.stderr)
            return False, f"Restore falló: {result.stderr[:200]}"

        logger.info("Sincronización completada: %.1f MB restaurados", dump_size / 1024 / 1024)
        return True, f"DB sincronizada ({dump_size / 1024 / 1024:.1f} MB)"

    except subprocess.TimeoutExpired:
        return False, "Timeout — la operación tardó más de 2 minutos"
    except Exception as exc:
        logger.warning("Error en sincronización: %s", exc)
        return False, f"Error: {exc}"
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass
