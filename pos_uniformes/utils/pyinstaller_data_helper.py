"""Helpers para declarar arboles de recursos en builds de PyInstaller."""

from __future__ import annotations

from pathlib import Path


def collect_tree_datas(
    source_root: Path,
    destination_root: str,
    *,
    include_python_files: bool = False,
) -> list[tuple[str, str]]:
    """Devuelve pares ``(source, dest_dir)`` preservando la estructura relativa."""

    normalized_source_root = Path(source_root).resolve()
    if not normalized_source_root.exists():
        return []

    datas: list[tuple[str, str]] = []
    for candidate in sorted(normalized_source_root.rglob("*")):
        if not candidate.is_file():
            continue
        if _should_skip_path(candidate, include_python_files=include_python_files):
            continue

        relative_parent = candidate.relative_to(normalized_source_root).parent
        destination_dir = Path(destination_root) / relative_parent
        datas.append((str(candidate), destination_dir.as_posix()))

    return datas


def _should_skip_path(path: Path, *, include_python_files: bool) -> bool:
    if any(part == "__pycache__" for part in path.parts):
        return True
    if path.name == ".DS_Store":
        return True
    if path.suffix == ".pyc":
        return True
    if path.suffix == ".py" and not include_python_files:
        return True
    return False
