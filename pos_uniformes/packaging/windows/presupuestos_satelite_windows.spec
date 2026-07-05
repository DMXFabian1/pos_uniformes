# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules


PROJECT_ROOT = Path(SPEC).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT.parent))

from pos_uniformes.utils.pyinstaller_data_helper import collect_tree_datas
from pos_uniformes.utils.app_metadata import satellite_windows_icon_path

VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
APP_NAME = f"PresupuestosSatelite-{VERSION}"
WINDOWS_ICON = satellite_windows_icon_path()

datas = []

# Incluir favoritos como seed para el primer arranque en Windows
_favorites_seed = PROJECT_ROOT / "data" / "favorites.json"
if _favorites_seed.exists():
    datas += [(str(_favorites_seed), "data")]

datas += collect_tree_datas(
    PROJECT_ROOT / "assets",
    "pos_uniformes/assets",
)
datas += collect_tree_datas(
    PROJECT_ROOT / "migrations",
    "pos_uniformes/migrations",
    include_python_files=True,
)
datas += [
    (str(PROJECT_ROOT / "alembic.ini"), "pos_uniformes"),
    (str(PROJECT_ROOT / "pos_uniformes.env.example"), "."),
    (str(PROJECT_ROOT / "VERSION"), "."),
    (str(PROJECT_ROOT / "scripts" / "setup_satelite.ps1"), "."),
]

hiddenimports = []
hiddenimports += collect_submodules("psycopg")
hiddenimports += collect_submodules("alembic")
hiddenimports += collect_submodules("meilisearch")
hiddenimports += [
    "pos_uniformes.ui.dialogs.satellite_admin_dialog",
    # Imports lazy (dentro de métodos) — mismo precedente que el admin dialog:
    "pos_uniformes.ui.dialogs.label_print_confirmation_dialog",
    "pos_uniformes.services.inventory_label_service",
    "pos_uniformes.ui.helpers.quick_sale_sports_uniform_helper",
]


a = Analysis(
    [str(PROJECT_ROOT / "presupuestos_satelite_main.py")],
    pathex=[str(PROJECT_ROOT.parent)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(WINDOWS_ICON) if WINDOWS_ICON is not None else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
