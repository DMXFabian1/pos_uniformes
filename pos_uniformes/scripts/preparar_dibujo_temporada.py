"""Deja un dibujo de Daniel listo para el ticket térmico.

Los manda grandes y a veces con transparencia; la térmica quiere otra cosa:
blanco y negro puro, sin grises, y del tamaño exacto con que se va a imprimir.

Por qué se prepara aquí y no al imprimir: encoger un dibujo de un bit en el
último momento es lo que dejó el logo apolillado el 07/10. Si se hace una vez,
con un buen filtro y un umbral claro, lo que viaja ya es lo que sale.

    python -m pos_uniformes.scripts.preparar_dibujo_temporada halloween

Lee  assets/temporadas/originales/<nombre>.png
Deja assets/temporadas/<nombre>.png
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

#: Alto con el que se imprime. Los que ya estaban miden entre 90 y 210 puntos
#: (1 a 2.5 cm de papel): un dibujo más alto se come media cuenta.
ALTO = 190
#: El papel son 576 puntos menos los márgenes. Más ancho que esto lo encoge el
#: programa al imprimir, que es justo lo que se quiere evitar.
ANCHO_MAXIMO = 552
#: Por debajo de este brillo es tinta. A la mitad, porque el dibujo ya viene
#: en dos tonos y lo único gris son los bordes suavizados.
UMBRAL = 128


def preparar(origen: Path, *, alto: int = ALTO):
    from PIL import Image

    im = Image.open(origen)
    # La forma puede venir en el ALFA (negro sobre transparente, como los
    # manda Daniel) o en el color. Aplanar sobre BLANCO deja las dos igual.
    if "A" in im.getbands():
        fondo = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(fondo, im.convert("RGBA"))
    gris = im.convert("L")

    # Se recorta el aire: el dibujo suele venir con márgenes que en el papel
    # son renglones en blanco que nadie pidió.
    caja = gris.point(lambda v: 255 if v < UMBRAL else 0).getbbox()
    if caja:
        gris = gris.crop(caja)

    ancho = max(1, round(gris.width * alto / gris.height))
    if ancho > ANCHO_MAXIMO:
        ancho, alto = ANCHO_MAXIMO, max(1, round(gris.height * ANCHO_MAXIMO / gris.width))
    # LANCZOS y DESPUÉS el umbral: encoger ya en dos tonos deja la silueta
    # dentada, y es el mismo error que apolilló el logo.
    gris = gris.resize((ancho, alto), Image.LANCZOS)
    return gris.point(lambda v: 0 if v < UMBRAL else 255).convert("1")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    carpeta = Path(__file__).resolve().parents[1] / "assets" / "temporadas"
    for nombre in argv:
        origen = carpeta / "originales" / f"{nombre}.png"
        if not origen.exists():
            print(f"no está {origen}")
            return 1
        salida = carpeta / f"{nombre}.png"
        im = preparar(origen)
        im.save(salida)
        print(f"{nombre}: {im.size[0]}x{im.size[1]} → {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
