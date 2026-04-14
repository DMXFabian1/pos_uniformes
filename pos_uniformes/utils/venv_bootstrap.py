"""Bootstrap de dependencias locales cuando se ejecuta fuera de la .venv."""

from __future__ import annotations

from pathlib import Path
import site
import sys


def ensure_local_venv_site_packages(anchor: str | Path) -> None:
    """Agrega el `site-packages` de `.venv` al `sys.path` cuando existe."""
    anchor_path = Path(anchor).resolve()

    for base_dir in anchor_path.parents:
        venv_dir = base_dir / ".venv"
        if not venv_dir.is_dir():
            continue

        site_packages_candidates: list[Path] = []
        if sys.platform.startswith("win"):
            site_packages_candidates.append(venv_dir / "Lib" / "site-packages")
        else:
            version_dir = venv_dir / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
            site_packages_candidates.append(version_dir)
            site_packages_candidates.extend(sorted((venv_dir / "lib").glob("python*/site-packages")))

        for site_packages_dir in site_packages_candidates:
            if not site_packages_dir.is_dir():
                continue
            site.addsitedir(str(site_packages_dir))
            return
