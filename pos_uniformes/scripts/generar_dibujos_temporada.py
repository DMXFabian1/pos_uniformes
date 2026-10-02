"""Dibuja los PNG de temporada que se imprimen en el ticket.

    python -m pos_uniformes.scripts.generar_dibujos_temporada

Los PNG van versionados en `assets/temporadas/`; este script está para poder
rehacerlos o retocarlos sin depender de un editor de imágenes.

Reglas de dibujo, que vienen de cómo imprime una térmica:

- **Blanco y negro puro, sin grises.** La impresora decide cada punto: o quema o
  no quema. Un gris se convierte en un tramado sucio.
- **Trazo grueso** (4 px o más). A 203 dpi una línea de 1 px se pierde o sale
  quebrada según cómo caiga el papel.
- **Figuras simples y cerradas.** Lo que se ve a 2 cm de alto es la silueta, no
  el detalle: un contorno claro vale más que las facciones.
- **240 px de ancho** sobre los 576 del papel: ocupa poco menos de la mitad,
  centrado, para que no compita con el total.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ANCHO = 240
TRAZO = 5
NEGRO, BLANCO = 0, 255


def _lienzo(alto: int):
    from PIL import Image, ImageDraw

    img = Image.new("L", (ANCHO, alto), BLANCO)
    return img, ImageDraw.Draw(img)


def calabaza():
    img, d = _lienzo(190)
    # Rabo
    d.line([(120, 44), (120, 16)], fill=NEGRO, width=TRAZO + 3)
    d.line([(120, 22), (144, 10)], fill=NEGRO, width=TRAZO)
    # Cuerpo ancho y dos gajos: sin los gajos se lee como una pelota con cara
    d.ellipse([24, 40, 216, 182], outline=NEGRO, width=TRAZO + 2)
    d.arc([58, 42, 182, 180], 0, 360, fill=NEGRO, width=TRAZO - 2)
    d.arc([88, 42, 152, 180], 0, 360, fill=NEGRO, width=TRAZO - 2)
    # Ojos: triángulos macizos. A 2 cm lo que se ve es la mancha, no el trazo.
    d.polygon([(66, 86), (100, 86), (83, 116)], fill=NEGRO)
    d.polygon([(140, 86), (174, 86), (157, 116)], fill=NEGRO)
    # Boca: una banda con los dientes recortados en blanco, que es lo que la
    # hace sonrisa y no un manchón.
    d.polygon([(62, 130), (178, 130), (156, 164), (84, 164)], fill=NEGRO)
    for x in (82, 110, 138):
        d.polygon([(x, 164), (x + 14, 164), (x + 7, 136)], fill=BLANCO)
    for x in (96, 124):
        d.polygon([(x, 130), (x + 14, 130), (x + 7, 156)], fill=BLANCO)
    return img


def calavera():
    img, d = _lienzo(200)
    d.ellipse([45, 20, 195, 150], outline=NEGRO, width=TRAZO + 1)
    d.rectangle([90, 130, 150, 175], outline=NEGRO, width=TRAZO + 1)
    d.ellipse([72, 62, 110, 104], fill=NEGRO)
    d.ellipse([130, 62, 168, 104], fill=NEGRO)
    d.polygon([(120, 108), (106, 130), (134, 130)], fill=NEGRO)
    for x in (103, 120, 137):
        d.line([(x, 132), (x, 173)], fill=NEGRO, width=TRAZO - 1)
    # Flor de cempasúchil de un lado: es lo que la hace de muertos y no de susto
    for ang in range(0, 360, 45):
        import math

        rad = math.radians(ang)
        cx, cy = 42 + 26 * math.cos(rad), 48 + 26 * math.sin(rad)
        d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], outline=NEGRO, width=TRAZO - 2)
    d.ellipse([30, 36, 54, 60], fill=NEGRO)
    return img


def arbolito():
    img, d = _lienzo(210)
    d.polygon([(120, 12), (175, 78), (65, 78)], outline=NEGRO, width=TRAZO)
    d.polygon([(120, 52), (190, 130), (50, 130)], outline=NEGRO, width=TRAZO)
    d.polygon([(120, 100), (205, 180), (35, 180)], outline=NEGRO, width=TRAZO)
    d.rectangle([105, 180, 135, 200], fill=NEGRO)
    # Estrella maciza arriba
    d.polygon([(120, 0), (128, 16), (145, 18), (132, 30), (136, 46),
               (120, 38), (104, 46), (108, 30), (95, 18), (112, 16)], fill=NEGRO)
    return img


def lapiz():
    img, d = _lienzo(110)
    d.polygon([(20, 34), (165, 34), (165, 76), (20, 76)], outline=NEGRO, width=TRAZO)
    d.line([(140, 34), (140, 76)], fill=NEGRO, width=TRAZO - 1)
    d.polygon([(165, 34), (220, 55), (165, 76)], fill=NEGRO)
    d.rectangle([20, 34, 48, 76], fill=NEGRO)
    return img


def corazon():
    img, d = _lienzo(180)
    d.ellipse([38, 28, 122, 112], fill=NEGRO)
    d.ellipse([118, 28, 202, 112], fill=NEGRO)
    d.polygon([(45, 85), (195, 85), (120, 168)], fill=NEGRO)
    return img


def flor():
    img, d = _lienzo(200)
    import math

    for ang in range(0, 360, 60):
        rad = math.radians(ang)
        cx, cy = 120 + 42 * math.cos(rad), 70 + 42 * math.sin(rad)
        d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], outline=NEGRO, width=TRAZO)
    d.ellipse([96, 46, 144, 94], fill=NEGRO)
    d.line([(120, 112), (120, 192)], fill=NEGRO, width=TRAZO + 2)
    d.ellipse([122, 130, 175, 158], outline=NEGRO, width=TRAZO)
    return img


def estrellas():
    img, d = _lienzo(90)
    def estrella(cx, cy, r):
        import math

        pts = []
        for i in range(10):
            ang = math.radians(-90 + i * 36)
            rr = r if i % 2 == 0 else r * 0.42
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
        d.polygon(pts, fill=NEGRO)

    estrella(60, 46, 26)
    estrella(120, 34, 32)
    estrella(180, 50, 22)
    return img


DIBUJOS = {
    "halloween": calabaza,
    "dia_de_muertos": calavera,
    "navidad": arbolito,
    "regreso_a_clases": lapiz,
    "san_valentin": corazon,
    "dia_de_las_madres": flor,
    "anio_nuevo": estrellas,
    "independencia": estrellas,
}


def carpeta() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "temporadas"


def main() -> int:
    destino = carpeta()
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, hacer in DIBUJOS.items():
        img = hacer().convert("1")        # 1 bit: lo que entiende la térmica
        ruta = destino / f"{nombre}.png"
        img.save(ruta)
        print(f"{ruta.name:24} {img.size[0]}x{img.size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
