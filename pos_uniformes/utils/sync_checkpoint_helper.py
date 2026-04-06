"""Helpers para marcar checkpoints simples de sincronizacion entre Windows y Mac."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import subprocess
from typing import Literal


PlatformName = Literal["windows", "mac"]


@dataclass(frozen=True)
class SyncCheckpointState:
    windows_updated_at: str | None
    mac_updated_at: str | None


@dataclass(frozen=True)
class SyncCommitResult:
    platform: PlatformName
    updated_at: str
    branch: str
    commit_hash: str
    staged_paths: tuple[str, ...]


def resolve_project_root(start: Path | None = None) -> Path:
    if start is None:
        start = Path(__file__).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "docs").exists() and (candidate / "scripts").exists():
            return candidate
    raise RuntimeError("No fue posible ubicar la raiz del proyecto.")


def resolve_repo_root(project_root: Path) -> Path:
    for candidate in (project_root, *project_root.parents):
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError("No fue posible ubicar la raiz del repositorio Git.")


def resolve_status_file(project_root: Path) -> Path:
    return project_root / "docs" / "sync_checkpoint_status.json"


def get_current_branch_name(project_root: Path) -> str:
    repo_root = resolve_repo_root(project_root)
    return _run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")


def load_sync_checkpoint_state(project_root: Path) -> SyncCheckpointState:
    status_file = resolve_status_file(project_root)
    if not status_file.exists():
        return SyncCheckpointState(windows_updated_at=None, mac_updated_at=None)

    payload = json.loads(status_file.read_text(encoding="utf-8"))
    windows = payload.get("windows", {})
    mac = payload.get("mac", {})
    return SyncCheckpointState(
        windows_updated_at=_normalize_datetime_text(windows.get("updated_at")),
        mac_updated_at=_normalize_datetime_text(mac.get("updated_at")),
    )


def save_sync_checkpoint_state(
    project_root: Path,
    *,
    windows_updated_at: str | None,
    mac_updated_at: str | None,
) -> None:
    payload = {
        "windows": {"updated_at": windows_updated_at},
        "mac": {"updated_at": mac_updated_at},
    }
    status_file = resolve_status_file(project_root)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def format_timestamp_display(value: str | None) -> str:
    if not value:
        return "Nunca"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def commit_sync_checkpoint(
    project_root: Path,
    *,
    platform: PlatformName,
) -> SyncCommitResult:
    repo_root = resolve_repo_root(project_root)
    branch = _run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    timestamp = datetime.now().astimezone().replace(microsecond=0).isoformat()
    current_state = load_sync_checkpoint_state(project_root)

    if platform == "windows":
        save_sync_checkpoint_state(
            project_root,
            windows_updated_at=timestamp,
            mac_updated_at=current_state.mac_updated_at,
        )
    else:
        save_sync_checkpoint_state(
            project_root,
            windows_updated_at=current_state.windows_updated_at,
            mac_updated_at=timestamp,
        )

    staged_paths = stage_sync_checkpoint_changes(project_root)
    _run_git(repo_root, "commit", "-m", _build_commit_message(platform, timestamp))
    _run_git(repo_root, "push")
    commit_hash = _run_git(repo_root, "rev-parse", "--short", "HEAD")
    return SyncCommitResult(
        platform=platform,
        updated_at=timestamp,
        branch=branch,
        commit_hash=commit_hash,
        staged_paths=staged_paths,
    )


def stage_sync_checkpoint_changes(project_root: Path) -> tuple[str, ...]:
    repo_root = resolve_repo_root(project_root)
    changed_paths = list_changed_repo_paths(repo_root)
    allowed_paths = tuple(
        sorted(
            {
                path
                for path in changed_paths
                if _is_sync_candidate_path(path)
            }
        )
    )
    if not allowed_paths:
        raise RuntimeError(
            "No hay cambios utiles para sincronizar. El archivo de estado tampoco pudo prepararse."
        )

    for path in allowed_paths:
        _run_git(repo_root, "add", "--", path)
    return allowed_paths


def list_changed_repo_paths(repo_root: Path) -> tuple[str, ...]:
    output = _run_git(
        repo_root,
        "status",
        "--porcelain",
        "--untracked-files=all",
    )
    changed_paths: list[str] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        line = raw_line.rstrip("\n")
        path_fragment = line[3:]
        if " -> " in path_fragment:
            path_fragment = path_fragment.split(" -> ", 1)[1]
        normalized = path_fragment.replace("\\", "/").strip()
        if normalized:
            changed_paths.append(normalized)
    return tuple(changed_paths)


def _normalize_datetime_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _build_commit_message(platform: PlatformName, timestamp: str) -> str:
    readable = format_timestamp_display(timestamp)
    return f"sync: checkpoint {platform} {readable}"


def _is_sync_candidate_path(path: str) -> bool:
    normalized = path.replace("\\", "/").strip().lstrip("./")
    if not normalized:
        return False
    if any(part == "__pycache__" for part in normalized.split("/")):
        return False
    if normalized.endswith(".pyc"):
        return False
    excluded_prefixes = (
        ".venv/",
        ".venv-py39-backup/",
        "pos_uniformes/.venv/",
        "pos_uniformes/dist/",
        "pos_uniformes/build/",
        "pos_uniformes/packaging/windows/seed/",
        "pos_uniformes/generated/",
        "pos_uniformes/backups/",
    )
    if normalized.startswith(excluded_prefixes):
        return False
    excluded_suffixes = (
        ".dump",
        ".sql",
        ".zip",
        ".exe",
    )
    if normalized.endswith(excluded_suffixes):
        return False
    return True


def _run_git(repo_root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if process.returncode != 0:
        stderr = (process.stderr or "").strip()
        stdout = (process.stdout or "").strip()
        detail = stderr or stdout or f"git {' '.join(args)} fallo"
        raise RuntimeError(detail)
    return (process.stdout or "").rstrip("\r\n")
