"""Convierte el logo del negocio al PNG que se imprime en el ticket.

    python -m pos_uniformes.scripts.generar_logo_ticket

El logo de la configuración es a color y con transparencia; la térmica no sabe
de eso: cada punto o quema o no quema. Este script hace la traducción una vez y
deja el resultado versionado en `assets/ticket/logo.png`, para no convertir en
cada impresión y para poder mirarlo antes de gastar papel.

Las reglas son las mismas de los dibujos de temporada (ver
`generar_dibujos_temporada`), con una propia:

- **Blanco y negro puro, por umbral.** Nada de tramado: un gris tramado en un
  logo se lee como suciedad, no como gris.
- **500 px de ancho** sobre los 576 del papel. No es capricho: MAXIMODA es una
  tipografía con serifas de un solo punto de grosor a 203 dpi, y entre más
  chica se imprima, más probable es que la térmica se las coma. A 500 px esos
  trazos son gruesos en términos absolutos y el contraste fino/grueso que le da
  carácter al logo sobrevive. Engrosarlo con un filtro se probó y se descartó:
  engorda todo y lo vuelve un bloque.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ANCHO = 500
#: Por debajo de esto, el pixel quema. 170 deja pasar el antialias claro del
#: redimensionado y conserva los bordes.
UMBRAL = 170


def carpeta_destino() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "ticket"


def _logo_configurado() -> Path | None:
    """La ruta del logo que el negocio tiene puesto, si existe el archivo."""
    try:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.database.models import ConfiguracionNegocio

        with get_session() as session:
            fila = session.query(ConfiguracionNegocio).first()
            crudo = str(getattr(fila, "logo_path", "") or "").strip()
    except Exception:  # noqa: BLE001 — sin base, se busca en el repo
        crudo = ""
    if crudo and Path(crudo).exists():
        return Path(crudo)
    # Respaldo: el que vive en el repo (el mismo que usa la tarjeta de cliente).
    marca = Path(__file__).resolve().parents[1] / "assets" / "customer_card_template" / "brand"
    for nombre in ("business-logo.png", "business-logo.jpeg", "store-logo.PNG"):
        if (marca / nombre).exists():
            return marca / nombre
    return None


def convertir(origen: Path, destino: Path, *, ancho: int = ANCHO, umbral: int = UMBRAL) -> Path:
    from PIL import Image

    src = Image.open(origen).convert("RGBA")
    # El PNG trae transparencia: sobre negro se vería invertido, así que se
    # aplana sobre blanco antes de nada.
    blanco = Image.new("RGBA", src.size, (255, 255, 255, 255))
    gris = Image.alpha_composite(blanco, src).convert("L")
    # Quitar el aire que trae alrededor: si no, el logo sale chiquito y perdido
    # en medio de un margen que nadie pidió.
    caja = gris.point(lambda p: 255 if p < 200 else 0).getbbox()
    if caja:
        gris = gris.crop(caja)
    alto = max(1, round(gris.height * ancho / gris.width))
    gris = gris.resize((ancho, alto), Image.LANCZOS)
    bn = gris.point(lambda p: 0 if p < umbral else 255, mode="1")
    destino.parent.mkdir(parents=True, exist_ok=True)
    bn.save(destino, optimize=True)
    return destino


def main() -> int:
    origen = _logo_configurado()
    if origen is None:
        print("No encontré el logo del negocio.")
        print("Ponlo en Configuración → el campo del logo, o deja el archivo en")
        print("assets/customer_card_template/brand/business-logo.png")
        return 1
    destino = carpeta_destino() / "logo.png"
    convertir(origen, destino)
    from PIL import Image

    img = Image.open(destino)
    print(f"Listo: {destino}")
    print(f"De {origen.name} → {img.width} x {img.height} px, blanco y negro puro.")
    print("Para verlo en papel: scripts\\probar_logo_ticket.bat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
