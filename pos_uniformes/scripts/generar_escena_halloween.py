"""Dibuja la escena de Halloween del kiosko. Ilustración ORIGINAL.

Daniel la pidió «a modo El extraño mundo de Jack» (07/10). Esa película es de
Disney, así que aquí no hay nada de ella: ni personajes, ni la colina de la
película, ni arte bajado de internet. Lo que sí se puede tomar es el género
—noche morada, luna enorme, árboles pelones, cerca chueca, calabazas— que es
de dominio común y es de donde esa película también lo tomó.

Es un script y no un SVG escrito a mano porque las estrellas, los murciélagos
y las calabazas se colocan con una semilla fija: se puede re-generar la escena
cambiando un número en vez de mover sesenta coordenadas a mano.

    python -m pos_uniformes.scripts.generar_escena_halloween
"""

from __future__ import annotations

import random
from pathlib import Path

ANCHO, ALTO = 1600, 1000
SEMILLA = 31      # cambia esto para re-barajar estrellas y murciélagos

#: Horizonte: todo lo de abajo es silueta, todo lo de arriba es cielo.
SUELO = 760


def _cielo() -> str:
    return f'''
  <defs>
    <linearGradient id="cielo" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0"    stop-color="#140d26"/>
      <stop offset="0.38" stop-color="#2b1942"/>
      <stop offset="0.68" stop-color="#5a2a4e"/>
      <stop offset="0.86" stop-color="#9c4a2c"/>
      <stop offset="1"    stop-color="#c76a2e"/>
    </linearGradient>
    <radialGradient id="halo" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0"   stop-color="#ffeec2" stop-opacity="0.55"/>
      <stop offset="0.45" stop-color="#ffd98a" stop-opacity="0.18"/>
      <stop offset="1"   stop-color="#ffd98a" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="brasa" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#ffb347" stop-opacity="0.75"/>
      <stop offset="1" stop-color="#ff8c1a" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="{ANCHO}" height="{ALTO}" fill="url(#cielo)"/>'''


def _luna() -> str:
    cx, cy, r = 1215, 235, 118
    return f'''
  <circle cx="{cx}" cy="{cy}" r="{r * 3.1:.0f}" fill="url(#halo)"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="#f6e9c9"/>
  <circle cx="{cx - 38}" cy="{cy - 30}" r="19" fill="#e6d5ae" opacity="0.7"/>
  <circle cx="{cx + 30}" cy="{cy + 22}" r="27" fill="#e6d5ae" opacity="0.55"/>
  <circle cx="{cx + 8}"  cy="{cy - 58}" r="12" fill="#e6d5ae" opacity="0.5"/>'''


def _estrellas(rnd: random.Random) -> str:
    partes = []
    for _ in range(90):
        x = rnd.uniform(0, ANCHO)
        y = rnd.uniform(0, SUELO - 180)
        # Se apagan hacia abajo: cerca del horizonte el cielo ya está claro.
        op = rnd.uniform(0.25, 0.95) * (1 - y / (SUELO - 180)) ** 0.7
        r = rnd.uniform(1.1, 2.6)
        partes.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" '
                      f'fill="#fff6dd" opacity="{op:.2f}"/>')
    return "\n  ".join(partes)


def _murcielago(x: float, y: float, s: float, op: float) -> str:
    """Un murciélago de una sola silueta: dos alas y el cuerpo."""
    d = ("M0,0 c-6,-9 -16,-13 -26,-8 c6,-3 7,-11 3,-16 "
         "c9,4 16,2 23,-6 c7,8 14,10 23,6 c-4,5 -3,13 3,16 "
         "c-10,-5 -20,-1 -26,8 z")
    return (f'<path d="{d}" transform="translate({x:.0f},{y:.0f}) scale({s:.2f})" '
            f'fill="#120b1e" opacity="{op:.2f}"/>')


def _bandada(rnd: random.Random) -> str:
    partes = []
    for _ in range(11):
        partes.append(_murcielago(
            rnd.uniform(60, ANCHO - 60), rnd.uniform(90, SUELO - 300),
            rnd.uniform(0.55, 1.5), rnd.uniform(0.55, 0.9),
        ))
    return "\n  ".join(partes)


def _cerros() -> str:
    """Cerros con la punta enroscada. Lejos y oscuros: son el fondo."""
    lejos = (f"M0,{SUELO - 40} C180,{SUELO - 150} 300,{SUELO - 90} 430,{SUELO - 165} "
             f"C520,{SUELO - 220} 560,{SUELO - 150} 610,{SUELO - 60} "
             f"C700,{SUELO - 140} 820,{SUELO - 80} 980,{SUELO - 170} "
             f"C1120,{SUELO - 245} 1320,{SUELO - 120} {ANCHO},{SUELO - 60} "
             f"L{ANCHO},{ALTO} L0,{ALTO} Z")
    # La punta que se enrosca: un cerro al que le siguió creciendo el pico y se
    # dobla sobre sí mismo. Va del MISMO color que los cerros y con la base
    # hundida hasta el suelo, porque dibujado más oscuro y apoyado en la cresta
    # parecía un gancho flotando y no la punta de nada.
    rizo = ("M268,790 C262,666 276,556 322,484 C360,424 428,398 472,424 "
            "C514,448 520,506 486,532 C456,554 418,540 414,508 "
            "C410,482 434,468 450,482 C436,476 424,490 430,506 "
            "C436,524 464,530 482,512 C506,488 498,444 466,430 "
            "C424,412 376,448 352,506 C324,572 320,676 328,790 Z")
    return (f'<path d="{lejos}" fill="#1a1030" opacity="0.95"/>\n  '
            f'<path d="{rizo}" fill="#1a1030"/>')


def _arbol(x: float, s: float, espejo: bool = False) -> str:
    """Un árbol pelón con las ramas enroscadas hacia arriba."""
    tronco = ("M0,0 C-10,-60 -4,-120 -16,-182 C-20,-204 -8,-212 2,-196 "
              "C10,-132 8,-70 18,0 Z")
    ramas = [
        "M-10,-150 C-54,-168 -78,-196 -72,-232 C-70,-246 -56,-248 -54,-236 "
        "C-52,-222 -60,-214 -66,-220 C-62,-196 -40,-174 -8,-160 Z",
        "M6,-176 C44,-196 62,-228 56,-258 C54,-270 42,-272 40,-262 "
        "C38,-250 46,-244 50,-250 C50,-226 30,-200 4,-186 Z",
        "M-6,-110 C-40,-120 -58,-136 -58,-158 C-58,-168 -48,-170 -46,-162 "
        "C-44,-154 -50,-150 -52,-154 C-50,-138 -32,-124 -4,-118 Z",
    ]
    cuerpo = "\n    ".join(
        f'<path d="{d}" fill="#0d0718"/>' for d in [tronco, *ramas]
    )
    giro = f"translate({x:.0f},{SUELO + 40}) scale({-s if espejo else s:.2f},{s:.2f})"
    return f'<g transform="{giro}">\n    {cuerpo}\n  </g>'


def _cerca() -> str:
    """Una cerca chueca: ninguna tabla igual a la de al lado."""
    rnd = random.Random(SEMILLA + 7)
    tablas = []
    x = -30
    while x < ANCHO + 40:
        alto = rnd.uniform(78, 118)
        ancho = rnd.uniform(20, 30)
        inclina = rnd.uniform(-7, 7)
        base = SUELO + 150
        punta = base - alto
        tablas.append(
            f'<g transform="translate({x:.0f},{base:.0f}) rotate({inclina:.1f})">'
            f'<path d="M0,0 L0,{-alto:.0f} L{ancho / 2:.0f},{-alto - 16:.0f} '
            f'L{ancho:.0f},{-alto:.0f} L{ancho:.0f},0 Z" fill="#0b0614"/></g>'
        )
        x += ancho + rnd.uniform(14, 26)
    travesanos = (
        f'<rect x="-30" y="{SUELO + 78}" width="{ANCHO + 70}" height="11" '
        f'fill="#0b0614" transform="rotate(-0.6 0 {SUELO + 78})"/>'
        f'<rect x="-30" y="{SUELO + 116}" width="{ANCHO + 70}" height="11" '
        f'fill="#0b0614" transform="rotate(0.5 0 {SUELO + 116})"/>'
    )
    return "\n  ".join(tablas) + "\n  " + travesanos


def _calabaza(x: float, y: float, s: float, cara: bool = True) -> str:
    """Una calabaza chueca. Con cara, le brilla por dentro."""
    gajos = ''.join(
        f'<ellipse cx="{dx}" cy="0" rx="{rx}" ry="46" fill="{col}"/>'
        for dx, rx, col in ((-30, 22, "#c4571c"), (-11, 26, "#e06a22"),
                            (11, 26, "#e06a22"), (30, 22, "#c4571c"))
    )
    ojos = (
        '<path d="M-24,-14 L-8,-4 L-24,2 Z" fill="#2a0f04"/>'
        '<path d="M24,-14 L8,-4 L24,2 Z" fill="#2a0f04"/>'
        '<path d="M-26,16 L-14,10 L-8,18 L0,10 L8,18 L14,10 L26,16 '
        'C14,30 -14,30 -26,16 Z" fill="#2a0f04"/>'
    ) if cara else ""
    brillo = (f'<circle cx="0" cy="0" r="120" fill="url(#brasa)"/>'
              if cara else "")
    return (f'<g transform="translate({x:.0f},{y:.0f}) scale({s:.2f}) '
            f'rotate({-6 if cara else 5})">{brillo}'
            f'<ellipse cx="0" cy="0" rx="52" ry="46" fill="#b64f18"/>{gajos}'
            f'<path d="M-5,-48 C-7,-66 4,-70 10,-62 C14,-56 8,-52 6,-58 '
            f'C2,-62 0,-56 3,-46 Z" fill="#2f6b34"/>{ojos}</g>')


def _suelo() -> str:
    return (f'<path d="M0,{SUELO + 120} C260,{SUELO + 92} 520,{SUELO + 142} '
            f'820,{SUELO + 108} C1120,{SUELO + 76} 1380,{SUELO + 130} '
            f'{ANCHO},{SUELO + 102} L{ANCHO},{ALTO} L0,{ALTO} Z" fill="#080410"/>')


def construir() -> str:
    rnd = random.Random(SEMILLA)
    piezas = [
        _cielo(),
        _estrellas(rnd),
        _luna(),
        _bandada(rnd),
        _cerros(),
        _arbol(170, 1.35), _arbol(1460, 1.15, espejo=True), _arbol(700, 0.8),
        _cerca(),
        _suelo(),
        _calabaza(250, SUELO + 150, 1.15),
        _calabaza(410, SUELO + 168, 0.8, cara=False),
        _calabaza(1230, SUELO + 156, 1.0),
        _calabaza(1370, SUELO + 176, 0.72, cara=False),
    ]
    cuerpo = "\n  ".join(piezas)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {ANCHO} {ALTO}" width="{ANCHO}" height="{ALTO}">\n  '
            f'{cuerpo}\n</svg>\n')


def main() -> int:
    destino = Path(__file__).resolve().parents[1] / "assets" / "escenas" / "halloween.svg"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(construir(), encoding="utf-8")
    print(f"escrito: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
