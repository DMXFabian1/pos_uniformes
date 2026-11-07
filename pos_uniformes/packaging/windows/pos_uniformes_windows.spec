# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules


PROJECT_ROOT = Path(SPEC).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT.parent))

from pos_uniformes.utils.app_metadata import app_windows_icon_path
from pos_uniformes.utils.pyinstaller_data_helper import collect_tree_datas

VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
APP_NAME = f"POSUniformes-{VERSION}"
WINDOWS_ICON = app_windows_icon_path()

datas = []
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
    (str(PROJECT_ROOT / "scripts" / "setup_windows_local_bundle.ps1"), "."),
    (str(PROJECT_ROOT / "scripts" / "setup_windows_local_bundle.bat"), "."),
]

# El mapa de escuelas (Ctrl+Shift+M) con su Leaflet dentro (2026-11-07): sin
# el HTML el POS decía «Esta PC no tiene el mapa»; sin vendor/ salía en blanco
# si unpkg.com no contestaba. Mismo arreglo que el spec del satélite.
_mapas = PROJECT_ROOT.parent / "mapas_escuelas"
if (_mapas / "mapa_escuelas_san_felipe.html").exists():
    datas += [(str(_mapas / "mapa_escuelas_san_felipe.html"), "mapas_escuelas")]
if (_mapas / "vendor").is_dir():
    datas += [(str(_mapas / "vendor"), "mapas_escuelas/vendor")]

seed_backup = PROJECT_ROOT / "packaging" / "windows" / "seed" / "initial.dump"
if seed_backup.exists():
    datas.append((str(seed_backup), "seed"))

driver_dir = PROJECT_ROOT / "packaging" / "windows" / "drivers"
if driver_dir.exists():
    for installer in driver_dir.iterdir():
        if installer.is_file():
            datas.append((str(installer), "drivers"))

hiddenimports = []
hiddenimports += collect_submodules("psycopg")
hiddenimports += collect_submodules("alembic")
hiddenimports += collect_submodules("meilisearch")
# Mapa de escuelas y tipos de escocés en una ventana del programa (imports lazy).
hiddenimports += [
    "pos_uniformes.services.mapa_escuelas_service",
    "pos_uniformes.ui.helpers.abrir_consultas",
    "pos_uniformes.ui.dialogs.visor_consulta_dialog",
    "pos_uniformes.ui.dialogs.visor_escoces_dialog",
    "pos_uniformes.ui.helpers.avisos_bonitos",
    "PyQt6.QtPdf",
    "PyQt6.QtPdfWidgets",
    "PyQt6.QtPrintSupport",
]


a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
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
