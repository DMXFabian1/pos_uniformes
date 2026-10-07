"""Convierte el murciélago que dibujó Daniel en un trazo de vector.

Lo mandó como PNG el 07/10 («lo hice yo»). Pegarlo como imagen habría sido
más rápido, pero la escena del kiosko se estira a la pantalla que toque: un
PNG de 1961 puntos de ancho se vería pixeleado en una grande y pesado en el
archivo. Trazado, escala a cualquier tamaño y se guarda en dos renglones.

El dibujo es de Daniel. Esto solo lo pasa de puntos a contorno:

  1. La silueta sale del canal ALFA, no del color: la imagen es negra entera y
     la forma vive en la transparencia.
  2. Se sigue el borde pixel por pixel (Moore) y queda un contorno de miles de
     puntos, uno por pixel del borde.
  3. Se simplifica (Ramer-Douglas-Peucker) hasta unos cientos: a ojo es el
     mismo murciélago y el archivo deja de pesar.
  4. Se normaliza a una caja de 0..1 para poder plantarlo a cualquier tamaño.

    python -m pos_uniformes.scripts.trazar_murcielago
"""

from __future__ import annotations

from pathlib import Path

#: Qué tanto se permite que el contorno simplificado se separe del original,
#: en pixeles de la imagen. 1.5 quita el escalón de los pixeles sin comerse
#: ninguna punta de las alas.
TOLERANCIA = 1.5


def _mascara(ruta: Path):
    from PIL import Image

    im = Image.open(ruta).convert("RGBA")
    alfa = im.getchannel("A").load()
    w, h = im.size
    return [[alfa[x, y] > 127 for x in range(w)] for y in range(h)], w, h


def _contorno(mascara, w: int, h: int) -> list[tuple[int, int]]:
    """El borde exterior de la figura, siguiendo los vecinos (Moore)."""
    inicio = None
    for y in range(h):
        for x in range(w):
            if mascara[y][x]:
                inicio = (x, y)
                break
        if inicio:
            break
    if inicio is None:
        raise SystemExit("la imagen no tiene figura")

    vecinos = [(-1, 0), (-1, -1), (0, -1), (1, -1),
               (1, 0), (1, 1), (0, 1), (-1, 1)]

    def lleno(x, y):
        return 0 <= x < w and 0 <= y < h and mascara[y][x]

    borde = [inicio]
    actual, previo = inicio, (inicio[0] - 1, inicio[1])
    tope = w * h * 4          # un tope duro: un borde raro no cuelga el script
    while tope > 0:
        tope -= 1
        d = (previo[0] - actual[0], previo[1] - actual[1])
        i = vecinos.index(d)
        siguiente = None
        for k in range(1, 9):
            v = vecinos[(i + k) % 8]
            c = (actual[0] + v[0], actual[1] + v[1])
            if lleno(*c):
                siguiente = c
                previo = (actual[0] + vecinos[(i + k - 1) % 8][0],
                          actual[1] + vecinos[(i + k - 1) % 8][1])
                break
        if siguiente is None or (siguiente == inicio and len(borde) > 2):
            break
        actual = siguiente
        borde.append(actual)
    return borde


def _simplificar(puntos, tol: float):
    """Ramer-Douglas-Peucker, iterativo para no reventar la pila."""
    if len(puntos) < 3:
        return list(puntos)
    guardar = [False] * len(puntos)
    guardar[0] = guardar[-1] = True
    pila = [(0, len(puntos) - 1)]
    while pila:
        i, j = pila.pop()
        if j <= i + 1:
            continue
        ax, ay = puntos[i]
        bx, by = puntos[j]
        dx, dy = bx - ax, by - ay
        largo = (dx * dx + dy * dy) ** 0.5 or 1.0
        peor, peor_i = 0.0, i
        for k in range(i + 1, j):
            px, py = puntos[k]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / largo
            if d > peor:
                peor, peor_i = d, k
        if peor > tol:
            guardar[peor_i] = True
            pila.append((i, peor_i))
            pila.append((peor_i, j))
    return [p for p, s in zip(puntos, guardar) if s]


def trazar(ruta: Path) -> str:
    mascara, w, h = _mascara(ruta)
    puntos = _simplificar(_contorno(mascara, w, h), TOLERANCIA)
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    x0, y0 = min(xs), min(ys)
    ancho = (max(xs) - x0) or 1
    alto = (max(ys) - y0) or 1
    # Normalizado a 0..1 en X y a 0..(alto/ancho) en Y: así no se deforma y
    # plantarlo es decir nada más qué tan ancho se quiere.
    razon = alto / ancho
    cuerpo = " L".join(
        f"{(x - x0) / ancho:.4f},{(y - y0) / ancho:.4f}" for x, y in puntos
    )
    return f"{razon:.5f}\nM{cuerpo} Z\n"


def main() -> int:
    carpeta = Path(__file__).resolve().parents[1] / "assets" / "escenas"
    salida = carpeta / "murcielago_de_daniel.path"
    salida.write_text(trazar(carpeta / "murcielago_de_daniel.png"), encoding="utf-8")
    puntos = salida.read_text(encoding="utf-8").count(",")
    print(f"escrito: {salida} ({puntos} puntos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
