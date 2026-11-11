"""E7: la etiqueta de Oferta o Liquidación (Daniel, 2026-11-11).

La cuadrada de 23 mm (DK-1221), para pegar junto a la etiqueta normal de la
prenda. La Brother imprime solo en negro, así que los dos tipos se distinguen
por la franja de arriba:

    OFERTA       franja negra sólida, letras blancas
    LIQUIDACIÓN  franja a rayas diagonales, letras negras en un recuadro blanco

Debajo: «Antes $450» tachado, el precio rebajado grande, la prenda con su
talla y, al pie, «Hasta 30/11» (oferta) o «Sin cambios» (liquidación).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw

from pos_uniformes.utils.label_generator import DK1221_SIZE, LABELS_OUTPUT_DIR, LabelGenerator

ALTO_FRANJA = 50


def _precio(valor) -> str:
    v = Decimal(str(valor))
    return f"${v:,.0f}" if v == v.to_integral_value() else f"${v:,.2f}"


def ruta_por_omision(sku: str) -> Path:
    carpeta = LABELS_OUTPUT_DIR / "rebaja"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / f"{sku}_rebaja.png"


def render_rebaja(
    *,
    tipo: str,
    nombre: str,
    talla: str,
    precio,
    precio_antes,
    hasta: date | None,
    output_path: Path,
) -> Path:
    size = DK1221_SIZE
    img = Image.new("1", (size, size), 1)
    draw = ImageDraw.Draw(img)
    lg = LabelGenerator

    def centrado(texto: str, fuente, y: int, *, fill: int = 0) -> int:
        caja = draw.textbbox((0, 0), texto, font=fuente)
        draw.text(((size - (caja[2] - caja[0])) // 2 - caja[0], y - caja[1]), texto, font=fuente, fill=fill)
        return caja[3] - caja[1]

    # ── Franja ──
    liquidacion = tipo == "liquidacion"
    titulo = "LIQUIDACIÓN" if liquidacion else "OFERTA"
    if liquidacion:
        for x in range(-ALTO_FRANJA, size, 12):
            draw.line([(x, ALTO_FRANJA), (x + ALTO_FRANJA, 0)], fill=0, width=5)
        f_tit = lg._fit_font(draw, titulo, size - 28, base_size=30, min_size=12, bold=True)
        caja = draw.textbbox((0, 0), titulo, font=f_tit)
        ancho, alto = caja[2] - caja[0], caja[3] - caja[1]
        x0, y0 = (size - ancho) // 2 - 6, (ALTO_FRANJA - alto) // 2 - 5
        draw.rectangle([x0, y0, x0 + ancho + 12, y0 + alto + 10], fill=1, outline=0, width=2)
        centrado(titulo, f_tit, y0 + 5)
    else:
        draw.rectangle([0, 0, size, ALTO_FRANJA], fill=0)
        f_tit = lg._fit_font(draw, titulo, size - 16, base_size=38, min_size=12, bold=True)
        caja = draw.textbbox((0, 0), titulo, font=f_tit)
        centrado(titulo, f_tit, (ALTO_FRANJA - (caja[3] - caja[1])) // 2, fill=1)

    # ── Antes (tachado) y ahora ──
    y = ALTO_FRANJA + 6
    antes = f"Antes {_precio(precio_antes)}"
    f_antes = lg._fit_font(draw, antes, size - 8, base_size=20, min_size=10)
    caja = draw.textbbox((0, 0), antes, font=f_antes)
    alto_antes = centrado(antes, f_antes, y)
    x_ini = (size - (caja[2] - caja[0])) // 2
    draw.line([(x_ini, y + alto_antes // 2 + 1), (x_ini + caja[2] - caja[0], y + alto_antes // 2 + 1)], fill=0, width=2)
    y += alto_antes + 6

    ahora = _precio(precio)
    f_ahora = lg._fit_font(draw, ahora, size - 8, base_size=58, min_size=16, bold=True)
    y += centrado(ahora, f_ahora, y) + 8

    # ── Prenda y pie ──
    pie = f"Hasta {hasta:%d/%m}" if (hasta and not liquidacion) else ("Sin cambios" if liquidacion else "")
    f_pie = lg._load_font(16, bold=True)
    alto_pie = lg._line_height(f_pie) if pie else 0
    prenda = f"{nombre} · T.{talla}" if talla else nombre
    alto_disp = size - y - alto_pie - 4
    if alto_disp > 10:
        f_nom, renglones = lg._fit_lines(draw, prenda, size - 6, alto_disp, base_size=20, min_size=10, max_renglones=2)
        paso = lg._alto_real(f_nom)
        for renglon in renglones:
            centrado(renglon, f_nom, y)
            y += paso
    if pie:
        centrado(pie, f_pie, size - alto_pie - 2)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return output_path
