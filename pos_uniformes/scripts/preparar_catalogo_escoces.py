"""Copia el catálogo de escoceses al programa (muestras ligeras + datos).

El catálogo se arma fuera del repo (ver la memoria «Catálogo Tipos de
Escocés»): `organizado/genera_catalogo.py` tiene los GRUPOS (familia →
[(nombre, tartán)]) y `organizado/muestras/ESC-XX.png` las fotos a 1200 px
(113 MB las 37). Aquí se pasan a JPG de 600 px (~5 MB todo) más un
`escoces.json`, que es lo que lee la ventana «Tipos de escocés».

Uso (cuando se agreguen telas):
    python -m pos_uniformes.scripts.preparar_catalogo_escoces [carpeta organizado]
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ORIGEN = Path.home() / "Downloads" / "Nueva carpeta con elementos" / "Tipos de Escoces" / "organizado"
DESTINO = Path(__file__).resolve().parents[1] / "assets" / "catalogos" / "escoces"
LADO = 600


def leer_grupos(genera: Path) -> list:
    arbol = ast.parse(genera.read_text(encoding="utf-8"))
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and any(getattr(t, "id", "") == "GRUPOS" for t in nodo.targets):
            return ast.literal_eval(nodo.value)
    raise SystemExit("No encontré GRUPOS en genera_catalogo.py")


def main(argv: list[str] | None = None) -> int:
    from PIL import Image

    origen = Path((argv or sys.argv[1:] or [str(ORIGEN)])[0])
    grupos = leer_grupos(origen / "genera_catalogo.py")
    DESTINO.mkdir(parents=True, exist_ok=True)
    telas = []
    n = 0
    for familia, lista in grupos:
        for nombre, tartan in lista:
            n += 1
            codigo = f"ESC-{n:02d}"
            foto = origen / "muestras" / f"{codigo}.png"
            if not foto.is_file():
                print(f"Falta la foto de {codigo}: {foto}")
                continue
            im = Image.open(foto).convert("RGB")
            im.thumbnail((LADO, LADO), Image.LANCZOS)
            im.save(DESTINO / f"{codigo}.jpg", "JPEG", quality=80, optimize=True, progressive=True)
            telas.append({"codigo": codigo, "familia": familia, "nombre": nombre, "tartan": tartan,
                          "foto": f"{codigo}.jpg"})
    (DESTINO / "escoces.json").write_text(
        json.dumps({"telas": telas}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(telas)} telas en {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
