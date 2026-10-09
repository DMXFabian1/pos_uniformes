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


#: Hasta dónde se le deja crecer a un dibujo con mucho detalle. 340 puntos
#: son 4.3 cm de papel: caro para un adorno, pero menos que imprimir una
#: mancha que no se entiende.
ALTO_MAXIMO = 340
#: De cuánto en cuánto se prueba al crecer.
PASO_ALTO = 40


def preparar_a_lo_ancho(origen: Path, ancho: int = ANCHO_MAXIMO):
    """Igual, pero al ANCHO exacto del papel y sin tocarle el trazo.

    Es para el logo de la tienda. Con una tipografía de trazo contrastado
    —MAXIMODA es una Didone— las serifas quedan en 1-2 puntos a cualquier
    tamaño que quepa en el papel: no es cuestión de crecer, es la letra. Y
    engordarlas la convertiría en otra tipografía, que es peor que una serifa
    tenue (09/10).

    Lo que sí se evita es el reescalado: a 552 justos no lo encoge nadie al
    imprimir, que era lo que lo dejaba apolillado (07/10, medido en papel).
    """
    from PIL import Image

    gris = _aplanar(origen)
    alto = max(1, round(gris.height * ancho / gris.width))
    gris = gris.resize((ancho, alto), Image.LANCZOS)
    return gris.point(lambda v: 0 if v < UMBRAL else 255).convert("1")


def preparar(origen: Path, *, alto: int = ALTO):
    """El dibujo listo para el papel, del tamaño que de verdad necesita.

    Si a `alto` le quedan demasiadas líneas de un punto, **crece** antes que
    engordar: engordar el trazo de «Día de las Madres» le borró las caras —se
    vio en pantalla el 09/10— y un dibujo con detalle fino no necesita más
    tinta, necesita más espacio. Engordar queda de último recurso, para el que
    ni creciendo aguante.
    """
    im = _a_dos_tonos(origen, alto)
    while _proporcion_de_pelo(im) > MAXIMO_PELO and alto < ALTO_MAXIMO:
        alto = min(alto + PASO_ALTO, ALTO_MAXIMO)
        im = _a_dos_tonos(origen, alto)
    return _engordar_si_hace_falta(im)


def _aplanar(origen: Path):
    """El dibujo en grises, sobre blanco y sin márgenes.

    La forma puede venir en el ALFA (negro sobre transparente, como los manda
    Daniel) o en el color: aplanar sobre BLANCO deja las dos igual. Y se
    recorta el aire, que en el papel son renglones en blanco que nadie pidió.
    """
    from PIL import Image

    im = Image.open(origen)
    if "A" in im.getbands():
        fondo = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(fondo, im.convert("RGBA"))
    gris = im.convert("L")
    caja = gris.point(lambda v: 255 if v < UMBRAL else 0).getbbox()
    return gris.crop(caja) if caja else gris


def _a_dos_tonos(origen: Path, alto: int):
    from PIL import Image

    gris = _aplanar(origen)
    ancho = max(1, round(gris.width * alto / gris.height))
    if ancho > ANCHO_MAXIMO:
        ancho, alto = ANCHO_MAXIMO, max(1, round(gris.height * ANCHO_MAXIMO / gris.width))
    # LANCZOS y DESPUÉS el umbral: encoger ya en dos tonos deja la silueta
    # dentada, y es el mismo error que apolilló el logo.
    gris = gris.resize((ancho, alto), Image.LANCZOS)
    return gris.point(lambda v: 0 if v < UMBRAL else 255).convert("1")


#: Qué proporción de trazos de 1-2 puntos se tolera. Una línea de un punto a
#: 203 dpi se la come la impresora —le pasó a las serifas del logo el 07/10—,
#: y un dibujo hecho casi solo de esas sale como una mancha gris rota.
MAXIMO_PELO = 0.25


def _proporcion_de_pelo(im) -> float:
    """Qué tanto del dibujo son líneas de 1 o 2 puntos."""
    from collections import Counter

    gris = im.convert("L")
    px = gris.load()
    rachas = Counter()
    for y in range(gris.height):
        largo = 0
        for x in range(gris.width):
            if px[x, y] < 128:
                largo += 1
            elif largo:
                rachas[largo] += 1
                largo = 0
        if largo:
            rachas[largo] += 1
    total = sum(rachas.values())
    if not total:
        return 0.0
    return sum(c for largo, c in rachas.items() if largo <= 2) / total


def _engordar_si_hace_falta(im, *, vueltas: int = 3):
    """Engorda el trazo cuando el dibujo es casi todo pelo.

    ÚLTIMO recurso, después de haberlo dejado crecer: engordar el de «Día de
    las Madres» le cerró los ojos y la boca a las tres figuras (visto en
    pantalla el 09/10). Solo se usa si ni al tamaño máximo aguanta, porque
    una mancha con forma se entiende mejor que una mancha rota.
    """
    from PIL import ImageFilter

    for _ in range(vueltas):
        if _proporcion_de_pelo(im) <= MAXIMO_PELO:
            return im
        # MinFilter se queda con el pixel más OSCURO del vecindario: en un
        # dibujo de tinta negra, eso es engordar la línea.
        im = im.convert("L").filter(ImageFilter.MinFilter(3)).point(
            lambda v: 0 if v < UMBRAL else 255
        ).convert("1")
    return im


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
