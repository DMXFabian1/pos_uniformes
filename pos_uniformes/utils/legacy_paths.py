"""Helpers para resolver rutas legacy portables entre macOS y Windows."""

from __future__ import annotations

from pathlib import Path


def legacy_sqlite_candidates(
    *,
    project_root: Path | None = None,
    cwd: Path | None = None,
    home_dir: Path | None = None,
) -> tuple[Path, ...]:
    """Devuelve candidatos razonables para ubicar la base SQLite legacy."""

    resolved_project_root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    resolved_cwd = (cwd or Path.cwd()).resolve()
    resolved_home_dir = (home_dir or Path.home()).resolve()
    workspace_root = resolved_project_root.parent

    return (
        resolved_cwd / "productos.db",
        resolved_project_root / "data" / "productos.db",
        workspace_root / "Gestor_de_Inventarios" / "data" / "productos.db",
        resolved_home_dir / "Downloads" / "productos.db",
    )


def detect_legacy_sqlite_path(
    *,
    project_root: Path | None = None,
    cwd: Path | None = None,
    home_dir: Path | None = None,
) -> Path:
    """Resuelve la mejor ruta legacy disponible sin depender de una Mac especifica."""

    candidates = legacy_sqlite_candidates(
        project_root=project_root,
        cwd=cwd,
        home_dir=home_dir,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
