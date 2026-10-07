"""Convierte las siluetas que dibuja Daniel en trazos de vector.

Las manda como PNG (el murciélago y la bruja, 07/10). Pegarlas como imagen
habría sido más rápido, pero la escena del kiosko se estira a la pantalla que
toque: un PNG de 1961 puntos de ancho se vería pixeleado en una grande y
pesado en el archivo. Trazados, escalan a cualquier tamaño y se guardan en dos
renglones.

Los dibujos son de Daniel. Esto solo los pasa de puntos a contorno:

  1. La silueta sale del canal ALFA si lo hay, y si no del BRILLO. No es un
     detalle: el murciélago venía con transparencia y la bruja no —traía el
     cuadriculado pintado en los pixeles—, así que mirar solo el alfa habría
     dado una figura vacía.
  2. Se sigue el borde pixel por pixel (Moore) y queda un contorno de miles de
     puntos, uno por pixel del borde.
  3. Se simplifica (Ramer-Douglas-Peucker) hasta unos cientos: a ojo es el
     mismo dibujo y el archivo deja de pesar.
  4. Se normaliza a una caja de 0..1 para poder plantarlo a cualquier tamaño.

    python -m pos_uniformes.scripts.trazar_silueta
"""

from __future__ import annotations

from pathlib import Path

#: Qué tanto se permite que el contorno simplificado se separe del original,
#: en pixeles de la imagen. 1.5 quita el escalón de los pixeles sin comerse
#: ninguna punta de las alas.
TOLERANCIA = 1.5


#: Por debajo de este brillo, un pixel es figura. Alto a propósito: el
#: cuadriculado de fondo de la bruja es gris 230, y cualquier corte entre 100
#: y 200 lo deja fuera sin comerse el borde suavizado del dibujo.
UMBRAL_BRILLO = 128


def _mascara(ruta: Path):
    """Qué pixeles son figura. Alfa si lo hay; si no, los oscuros.

    Las dos cosas, porque los dibujos no vienen iguales: el murciélago traía
    transparencia de verdad y la bruja traía el cuadriculado pintado encima.
    Con solo alfa, la bruja salía vacía; con solo brillo, el murciélago salía
    como un rectángulo negro.
    """
    from PIL import Image

    im = Image.open(ruta)
    w, h = im.size
    if "A" in im.getbands() and im.getchannel("A").getextrema()[0] < 255:
        alfa = im.getchannel("A").load()
        return [[alfa[x, y] > 127 for x in range(w)] for y in range(h)], w, h
    gris = im.convert("L").load()
    return [[gris[x, y] < UMBRAL_BRILLO for x in range(w)] for y in range(h)], w, h


def _contorno(mascara, w: int, h: int, inicio=None) -> list[tuple[int, int]]:
    """El borde de la figura desde `inicio`, siguiendo los vecinos (Moore)."""
    if inicio is None:
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


#: Un hueco más chico que esto es borde suavizado, no un hueco del dibujo.
HUECO_MINIMO = 24


def _huecos(mascara, w: int, h: int) -> list[list[tuple[int, int]]]:
    """Los agujeros ENCERRADOS por la figura, cada uno como lista de pixeles.

    Hacen falta porque el seguidor de bordes solo da el contorno de afuera: sin
    esto, la bruja salía con el hueco entre la escoba y la capa relleno, y el
    dibujo dejaba de ser el dibujo (07/10).

    Se encuentran por descarte: se inunda el fondo desde la orilla, y el fondo
    al que no se llega es fondo encerrado, o sea un hueco.
    """
    alcanzado = [[False] * w for _ in range(h)]
    pila = []
    for x in range(w):
        for y in (0, h - 1):
            if not mascara[y][x] and not alcanzado[y][x]:
                alcanzado[y][x] = True
                pila.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if not mascara[y][x] and not alcanzado[y][x]:
                alcanzado[y][x] = True
                pila.append((x, y))
    while pila:
        x, y = pila.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = x + dx, y + dy
            if 0 <= a < w and 0 <= b < h and not mascara[b][a] and not alcanzado[b][a]:
                alcanzado[b][a] = True
                pila.append((a, b))

    vistos = [[False] * w for _ in range(h)]
    encontrados = []
    for y in range(h):
        for x in range(w):
            if mascara[y][x] or alcanzado[y][x] or vistos[y][x]:
                continue
            grupo, pila = [], [(x, y)]
            vistos[y][x] = True
            while pila:
                a, b = pila.pop()
                grupo.append((a, b))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    c, d = a + dx, b + dy
                    if (0 <= c < w and 0 <= d < h and not mascara[d][c]
                            and not alcanzado[d][c] and not vistos[d][c]):
                        vistos[d][c] = True
                        pila.append((c, d))
            if len(grupo) >= HUECO_MINIMO:
                encontrados.append(grupo)
    return encontrados


def trazar(ruta: Path) -> str:
    mascara, w, h = _mascara(ruta)
    contornos = [_contorno(mascara, w, h)]
    for hueco in _huecos(mascara, w, h):
        # Se traza el borde del hueco como si el hueco fuera la figura.
        suyo = [[False] * w for _ in range(h)]
        for x, y in hueco:
            suyo[y][x] = True
        contornos.append(_contorno(suyo, w, h, min(hueco, key=lambda p: (p[1], p[0]))))

    contornos = [_simplificar(c, TOLERANCIA) for c in contornos]
    # La caja sale del contorno de AFUERA: un hueco nunca la agranda.
    xs = [p[0] for p in contornos[0]]
    ys = [p[1] for p in contornos[0]]
    x0, y0 = min(xs), min(ys)
    ancho = (max(xs) - x0) or 1
    alto = (max(ys) - y0) or 1
    # Normalizado a 0..1 en X y a 0..(alto/ancho) en Y: así no se deforma y
    # plantarlo es decir nada más qué tan ancho se quiere.
    razon = alto / ancho
    partes = [
        "M" + " L".join(
            f"{(x - x0) / ancho:.4f},{(y - y0) / ancho:.4f}" for x, y in c
        ) + " Z"
        for c in contornos
    ]
    return f"{razon:.5f}\n{' '.join(partes)}\n"


#: Los dibujos de Daniel que viven en la escena.
SILUETAS = ("murcielago_de_daniel", "bruja_de_daniel")


def main() -> int:
    carpeta = Path(__file__).resolve().parents[1] / "assets" / "escenas"
    for nombre in SILUETAS:
        salida = carpeta / f"{nombre}.path"
        salida.write_text(trazar(carpeta / f"{nombre}.png"), encoding="utf-8")
        puntos = salida.read_text(encoding="utf-8").count(",")
        print(f"escrito: {salida} ({puntos} puntos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
