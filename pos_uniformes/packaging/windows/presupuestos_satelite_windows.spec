# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


PROJECT_ROOT = Path(SPEC).resolve().parents[2]
VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
APP_NAME = f"PresupuestosSatelite-{VERSION}"

datas = collect_data_files(
    "pos_uniformes",
    includes=[
        "assets/**/*",
        "migrations/**/*",
    ],
)
datas += [
    (str(PROJECT_ROOT / "alembic.ini"), "pos_uniformes"),
    (str(PROJECT_ROOT / "pos_uniformes.env.example"), "."),
    (str(PROJECT_ROOT / "VERSION"), "."),
]

hiddenimports = []
hiddenimports += collect_submodules("psycopg")
hiddenimports += collect_submodules("alembic")


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
