"""Dibuja el ticket como IMAGEN de puntos, al ancho exacto del papel.

Por qué existe: el ticket se dibujaba como texto sobre una página de Qt de 302
puntos de ancho (96 dpi) cuando la impresora tiene 576, y las imágenes además
se encogían a la mitad de eso con suavizado. El logo de 500 puntos acababa
achicado 3.3 veces y re-estirado 3.8 por el driver: salía apolillado, con las
astas huecas (2026-10-07, medido en papel).

Dibujando a 576 y mandando los puntos por ESC/POS no hay reescalado en ningún
punto de la cadena. De paso se ganan tres cosas que el camino de texto no podía
dar: las cajas salen como líneas de verdad en vez de guiones sueltos, el total
puede ir más grande, y se acaban los problemas de codificación — una imagen no
tiene codepage.

La entrada sigue siendo el MISMO texto de 38 columnas que ya arman los
servicios de ticket, apartado, presupuesto y corte. Eso es a propósito: no hay
que tocar a ninguno de ellos, y lo que se ve en pantalla y lo que sale en papel
siguen saliendo de la misma fuente.
"""

from __future__ import annotations

#: El papel: 576 puntos imprimibles (72 mm a 203 dpi) en las térmicas de 80 mm.
ANCHO_PAPEL = 576
#: Aire a los lados. No es estético: la cabeza no quema bien el borde mismo.
MARGEN = 12
#: Las columnas del texto de siempre.
COLUMNAS = 38

#: Caracteres de caja que se convierten en trazos dibujados.
_ESQUINAS_Y_BORDES = set("┌┐└┘├┤┬┴┼─│║═╞╡")
_SOLO_HORIZONTAL = set("┌┐└┘├┤┬┴┼─═╞╡ ")

#: Grosor de las líneas de los recuadros.
_TRAZO = 2

#: Fuentes monoespaciadas por orden de preferencia. Se busca una DE VERDAD y no
#: se confía en `systemFont(FixedFont)`: en la Mac devuelve la del sistema, que
#: es proporcional, y entonces cada letra queda centrada en su casilla y el
#: ticket sale aireado, deletreado (2026-10-07). Consolas es la de Windows, que
#: es donde imprime la tienda.
_MONOS = (
    "Consolas", "Lucida Console", "Courier New", "DejaVu Sans Mono",
    "Liberation Mono", "Menlo", "Monaco", "Noto Sans Mono",
)


def _fuente_mono():
    """Una monoespaciada de verdad, o la del sistema si no hay ninguna."""
    from PyQt6.QtGui import QFont, QFontDatabase, QFontInfo

    for familia in _MONOS:
        f = QFont(familia)
        f.setFixedPitch(True)
        f.setStyleHint(QFont.StyleHint.TypeWriter)
        if QFontInfo(f).fixedPitch():
            return f
    # Sin monoespaciada, el dibujo por casillas de abajo salva la rejilla:
    # se verá aireado, pero cuadrado.
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)


def _es_regla(linea: str) -> bool:
    """¿Esta línea es un renglón de marco (solo esquinas y guiones)?"""
    limpia = linea.strip()
    if len(limpia) < 4:
        return False
    return all(c in _SOLO_HORIZONTAL for c in limpia) and any(
        c in "─═" for c in limpia
    )


def _es_total(linea: str) -> bool:
    """La línea del total: la única que se imprime más grande.

    Se reconoce por el texto y no por su posición porque el ticket de venta, el
    de apartado y el del corte la ponen en lugares distintos."""
    sin_caja = linea.replace("│", "").replace("|", "").strip().upper()
    return sin_caja.startswith("TOTAL") and any(c.isdigit() for c in sin_caja)


def _marcador_de_imagen(linea: str) -> str | None:
    from pos_uniformes.services.temporada_service import MARCADOR_FIN, MARCADOR_INICIO

    limpia = linea.strip()
    if limpia.startswith(MARCADOR_INICIO) and limpia.endswith(MARCADOR_FIN):
        return limpia[len(MARCADOR_INICIO):-len(MARCADOR_FIN)]
    return None


def _escribir_en_rejilla(painter, texto: str, x0: int, base: int, avance: float) -> None:
    """Un carácter por casilla, cada uno centrado en la suya.

    Es lo que hace una térmica de verdad y lo que mantiene cuadrados los
    recuadros y los importes pegados a la derecha, venga la fuente que venga."""
    from PyQt6.QtGui import QFontMetricsF

    metrica = QFontMetricsF(painter.font())
    for i, c in enumerate(texto[:COLUMNAS]):
        if c == " ":
            continue
        centro = x0 + i * avance + (avance - metrica.horizontalAdvance(c)) / 2
        painter.drawText(int(round(centro)), base, c)


def render_ticket(texto: str, *, ancho: int = ANCHO_PAPEL):
    """El ticket como QImage en blanco y negro puro, lista para ESC/POS."""
    from PyQt6.QtCore import QRect, Qt
    from PyQt6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QImage, QPainter

    lineas = (texto or "").split("\n")

    fuente = _fuente_mono()
    fuente.setBold(True)
    util = ancho - MARGEN * 2
    # La columna es FIJA y sale de la división, no de la fuente: cada carácter
    # se dibuja en su casilla. Así la rejilla de 38 columnas se cumple aunque
    # el Windows de turno resuelva la fuente «monoespaciada» por una que no lo
    # es — pasó en la primera prueba y los importes dejaron de alinearse a la
    # derecha (2026-10-07).
    avance = util / COLUMNAS
    tam = 8
    for candidato in range(6, 40):
        fuente.setPointSize(candidato)
        if QFontMetrics(fuente).horizontalAdvance("M") <= avance:
            tam = candidato
        else:
            break
    fuente.setPointSize(tam)
    metrica = QFontMetrics(fuente)
    alto_linea = metrica.height()

    # El total, más grande pero SIN tocar el marco: se busca el tamaño mayor
    # que deje entrar etiqueta e importe con aire a los lados. Fijarlo a ojo
    # hacía que se montara sobre los costados de la caja (2026-10-07).
    _AIRE_TOTAL = 16
    util_total = util - _AIRE_TOTAL * 2
    grande = QFont(fuente)
    for candidato in range(tam + 8, tam, -1):
        grande.setPointSize(candidato)
        m = QFontMetrics(grande)
        if m.horizontalAdvance("TOTAL A PAGAR") + m.horizontalAdvance("$0,000.00") + 24 <= util_total:
            break
    metrica_grande = QFontMetrics(grande)

    # Primera pasada: cuánto mide todo, para crear la imagen del alto justo.
    from pos_uniformes.services.temporada_service import imagen_para_marcador

    alto = MARGEN
    plan: list[tuple[str, object]] = []
    for linea in lineas:
        nombre = _marcador_de_imagen(linea)
        if nombre is not None:
            ruta = imagen_para_marcador(nombre)
            if ruta is None:
                plan.append(("texto", f"(falta el dibujo: {nombre})".center(COLUMNAS)))
                alto += alto_linea
                continue
            imagen = QImage(str(ruta))
            if imagen.isNull():
                continue
            if imagen.width() > util:
                imagen = imagen.scaledToWidth(util, Qt.TransformationMode.FastTransformation)
            plan.append(("imagen", imagen))
            alto += imagen.height() + 6
            continue
        if _es_regla(linea):
            # Abre / separa / cierra: con eso se puede dibujar un RECTÁNGULO de
            # verdad en vez de un tick por renglón. El marco de hoy es "┌" …
            # "├" … "└", así que la forma ya está dicha en el texto.
            primera = linea.strip()[0]
            if primera in "┌╔":
                clase = "abre"
            elif primera in "└╚":
                clase = "cierra"
            else:
                clase = "separa"
            plan.append((clase, linea))
            alto += alto_linea
            continue
        if _es_total(linea):
            plan.append(("total", linea))
            alto += metrica_grande.height() + 4
            continue
        plan.append(("texto", linea))
        alto += alto_linea
    alto += MARGEN

    lienzo = QImage(ancho, max(alto, 1), QImage.Format.Format_RGB32)
    lienzo.fill(QColor("white"))
    painter = QPainter(lienzo)
    try:
        painter.setPen(QColor("black"))
        painter.setFont(fuente)
        y = MARGEN
        caja_desde: int | None = None
        for clase, valor in plan:
            if clase == "imagen":
                x = (ancho - valor.width()) // 2
                painter.drawImage(x, y, valor)
                y += valor.height() + 6
            elif clase in ("abre", "separa", "cierra"):
                medio = y + alto_linea // 2
                if clase == "abre":
                    caja_desde = medio
                else:
                    painter.fillRect(
                        MARGEN, medio, ancho - MARGEN * 2, _TRAZO, QColor("black")
                    )
                if clase == "cierra" and caja_desde is not None:
                    # Los dos costados de una sola vez, de la tapa al fondo:
                    # así el recuadro CIERRA en vez de quedar en rayas sueltas.
                    painter.fillRect(
                        MARGEN, caja_desde, _TRAZO, medio - caja_desde + _TRAZO, QColor("black")
                    )
                    painter.fillRect(
                        ancho - MARGEN - _TRAZO, caja_desde,
                        _TRAZO, medio - caja_desde + _TRAZO, QColor("black"),
                    )
                    painter.fillRect(
                        MARGEN, caja_desde, ancho - MARGEN * 2, _TRAZO, QColor("black")
                    )
                    caja_desde = None
                y += alto_linea
            elif clase == "total":
                painter.setFont(grande)
                etiqueta, _, importe = valor.replace("│", "").replace("|", "").strip().rpartition(" ")
                dentro = QRect(
                    MARGEN + _AIRE_TOTAL, y,
                    ancho - (MARGEN + _AIRE_TOTAL) * 2, metrica_grande.height(),
                )
                painter.drawText(
                    dentro,
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                    etiqueta.strip(" :") or "TOTAL",
                )
                painter.drawText(
                    dentro,
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                    importe.strip(),
                )
                painter.setFont(fuente)
                y += metrica_grande.height() + 4
            else:
                # Dentro de una caja, los bordes los pone el rectángulo: aquí
                # solo se quitan los caracteres para que no se dibujen encima.
                cuerpo = valor
                if cuerpo[:1] in "│|║" and cuerpo[-1:] in "│|║":
                    cuerpo = " " + cuerpo[1:-1] + " "
                _escribir_en_rejilla(painter, cuerpo, MARGEN, y + metrica.ascent(), avance)
                y += alto_linea
    finally:
        painter.end()
    return lienzo


def render_ticket_png(texto: str, *, ancho: int = ANCHO_PAPEL) -> bytes:
    """El ticket como PNG en bytes (lo que espera el raster de ESC/POS)."""
    from PyQt6.QtCore import QBuffer, QByteArray

    imagen = render_ticket(texto, ancho=ancho)
    datos = QByteArray()
    buffer = QBuffer(datos)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    imagen.save(buffer, "PNG")
    buffer.close()
    return bytes(datos.data())
