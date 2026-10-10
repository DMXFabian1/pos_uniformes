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
_ESQUINAS_Y_BORDES = set("┌┐└┘├┤┬┴┼─│║═╞╡╔╗╚╝")
#: Las esquinas dobles (╔ ╗ ╚ ╝) son las de la caja del total. Entraron el
#: 10/10: antes se dibujaban como letras y la caja salía hecha de glifos.
_SOLO_HORIZONTAL = set("┌┐└┘├┤┬┴┼─═╞╡╔╗╚╝ ")

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


def _adornos_encendidos() -> bool:
    try:
        from pos_uniformes.services.escpos_settings_cache_service import load_escpos_settings

        return bool(load_escpos_settings().adornos_de_temporada)
    except Exception:  # noqa: BLE001 — ante la duda, el ticket de siempre
        return False


def render_ticket(texto: str, *, ancho: int = ANCHO_PAPEL, adornos: bool | None = None,
                  tema: str | None = None):
    """El ticket como QImage en blanco y negro puro, lista para ESC/POS.

    `adornos`: dibujar los motivos festivos (None = lo que diga el ajuste de
    esta máquina). `tema`: forzar uno (para previas); si no, el que traiga el
    propio ticket en su marcador de temporada."""
    from PyQt6.QtCore import QRect, Qt
    from PyQt6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QImage, QPainter

    from pos_uniformes.services import ticket_adornos_service as adornos_svc

    lineas = (texto or "").split("\n")
    if adornos is None:
        adornos = _adornos_encendidos()
    adorno = adornos_svc.adorno_de(tema or adornos_svc.tema_del_ticket(texto)) if adornos else None

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
    # Aire arriba y abajo del total. Con la caja doble (10/10) el renglón
    # grande rozaba el marco de adentro.
    _AIRE_TOTAL_VERTICAL = 14
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
        cuerpo = _marcador_de_imagen(linea)
        if cuerpo is not None:
            from pos_uniformes.services.temporada_service import partir_marcador

            nombre, respaldo = partir_marcador(cuerpo)
            ruta = imagen_para_marcador(nombre)
            if ruta is None:
                # Con respaldo hay cómo decirlo escrito; sin él, el hueco se
                # ve, que es lo que permite preguntar por qué falta.
                falta = respaldo or f"(falta el dibujo: {nombre})"
                plan.append(("texto", falta.center(COLUMNAS)))
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
            alto += metrica_grande.height() + _AIRE_TOTAL_VERTICAL
            continue
        plan.append(("texto", linea))
        alto += alto_linea
    alto += MARGEN

    # Qué renglón lleva adorno. Se decide sobre el texto y el siguiente, sin
    # cambiar ni un carácter: el adorno se dibuja ENCIMA del renglón, en el
    # aire que ya tenía, o en los bordes de las cajas que ya existían.
    puntos: dict[int, str] = {}
    if adorno is not None:
        for i, (clase, valor) in enumerate(plan):
            if clase != "texto":
                continue
            siguiente = plan[i + 1][1] if i + 1 < len(plan) and plan[i + 1][0] == "texto" else None
            punto = adornos_svc.punto_de_adorno(valor, siguiente)
            if punto:
                puntos[i] = punto
    # Un renglón con motivo grande mide renglón y medio: a un renglón, el
    # motivo queda de 22 puntos (2.7 mm en papel) y la calaverita parece una
    # mota. El texto se centra en ese alto; los demás renglones no cambian.
    alto_fila_adornada = int(alto_linea * 1.8)
    tam_adorno = alto_fila_adornada - 4
    tam_mini = alto_linea - 4
    GRANDES = (adornos_svc.FLANCOS, adornos_svc.TERMINOS, adornos_svc.CABECERA)
    for punto in puntos.values():
        if punto in GRANDES:
            alto += alto_fila_adornada - alto_linea
        elif punto == adornos_svc.GRECA:
            # La greca cierra el marco de los términos: lleva aire extra
            # arriba para que el marco no roce el último renglón de texto.
            alto += alto_fila_adornada + 10
    # Con adorno, la tapa y el fondo de cada caja llevan un poco más de aire:
    # ahí se sientan las esquinas sin rozar el primer y el último renglón.
    pad_caja = 9 if adorno is not None else 0
    alto += pad_caja * sum(1 for c, _ in plan if c in ("abre", "cierra"))
    # Separadores entre productos: solo si el ticket no va apretado.
    n_separadores = sum(1 for c, v in plan if c == "separa" and "─" in v)
    separadores_adornados = (
        adorno is not None and n_separadores <= adornos_svc.MAX_PRODUCTOS_CON_SEPARADOR + 2
    )

    lienzo = QImage(ancho, max(alto, 1), QImage.Format.Format_RGB32)
    lienzo.fill(QColor("white"))
    painter = QPainter(lienzo)

    def _restaurar() -> None:
        painter.setPen(QColor("black"))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setFont(fuente)

    try:
        _restaurar()
        y = MARGEN
        caja_desde: int | None = None
        caja_doble = False
        en_articulos = False           # ya pasó el encabezado ARTÍCULOS de esta caja
        marco_desde: int | None = None  # arriba del marco de los términos
        x_izq, x_der = MARGEN, ancho - MARGEN
        for indice, (clase, valor) in enumerate(plan):
            if clase == "imagen":
                x = (ancho - valor.width()) // 2
                painter.drawImage(x, y, valor)
                y += valor.height() + 6
            elif clase in ("abre", "separa", "cierra"):
                medio = y + alto_linea // 2
                if clase == "cierra":
                    medio += pad_caja
                if clase == "abre":
                    caja_desde = medio
                    caja_doble = "═" in valor
                    en_articulos = False
                else:
                    painter.fillRect(x_izq, medio, x_der - x_izq, _TRAZO, QColor("black"))
                    if (clase == "separa" and adorno is not None and "═" in valor):
                        # Regla doble en medio de una caja (el ticket de caja
                        # la pone antes del total): un motivo al centro.
                        adornos_svc.dibujar_mini_en_regla(
                            painter, adorno, x_izq, x_der, medio + _TRAZO / 2, tam_mini
                        )
                        _restaurar()
                    elif clase == "separa" and separadores_adornados and en_articulos:
                        adornos_svc.dibujar_mini_en_regla(
                            painter, adorno, x_izq, x_der, medio + _TRAZO / 2, tam_mini
                        )
                        _restaurar()
                if clase == "cierra" and caja_desde is not None:
                    # Los dos costados de una sola vez, de la tapa al fondo:
                    # así el recuadro CIERRA en vez de quedar en rayas sueltas.
                    painter.fillRect(x_izq, caja_desde, _TRAZO, medio - caja_desde + _TRAZO, QColor("black"))
                    painter.fillRect(x_der - _TRAZO, caja_desde, _TRAZO, medio - caja_desde + _TRAZO, QColor("black"))
                    painter.fillRect(x_izq, caja_desde, x_der - x_izq, _TRAZO, QColor("black"))
                    if caja_doble:
                        # Línea doble de verdad: un segundo marco 5 puntos
                        # adentro, como el ═ del texto quería decir.
                        d = 5
                        painter.fillRect(x_izq + d, caja_desde + d, x_der - x_izq - 2 * d, _TRAZO, QColor("black"))
                        painter.fillRect(x_izq + d, medio - d, x_der - x_izq - 2 * d, _TRAZO, QColor("black"))
                        painter.fillRect(x_izq + d, caja_desde + d, _TRAZO, medio - caja_desde - 2 * d + _TRAZO, QColor("black"))
                        painter.fillRect(x_der - d - _TRAZO, caja_desde + d, _TRAZO, medio - caja_desde - 2 * d + _TRAZO, QColor("black"))
                    if adorno is not None:
                        if caja_doble:
                            # La caja del total: un motivo al centro de la tapa
                            # y del fondo, y las esquinas trabajadas.
                            for y_regla in (caja_desde + 3, medio + 3):
                                adornos_svc.dibujar_mini_en_regla(
                                    painter, adorno, x_izq, x_der, y_regla, tam_mini
                                )
                        adornos_svc.dibujar_esquinas(
                            painter, adorno, x_izq, caja_desde + _TRAZO / 2,
                            x_der, medio + _TRAZO / 2, tam_adorno * 0.7,
                        )
                        _restaurar()
                    caja_desde = None
                    en_articulos = False
                y += alto_linea + (pad_caja if clase in ("abre", "cierra") else 0)
            elif clase == "total":
                painter.setFont(grande)
                etiqueta, _, importe = valor.replace("│", "").replace("|", "").replace("║", "").strip().rpartition(" ")
                dentro = QRect(
                    MARGEN + _AIRE_TOTAL, y + _AIRE_TOTAL_VERTICAL // 2,
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
                y += metrica_grande.height() + _AIRE_TOTAL_VERTICAL
            else:
                # Dentro de una caja, los bordes los pone el rectángulo: aquí
                # solo se quitan los caracteres para que no se dibujen encima.
                cuerpo = valor
                if cuerpo[:1] in "│|║" and cuerpo[-1:] in "│|║":
                    cuerpo = " " + cuerpo[1:-1] + " "
                punto = puntos.get(indice)
                if punto in GRANDES:
                    alto_fila = alto_fila_adornada
                    desfase = (alto_fila - alto_linea) // 2
                elif punto == adornos_svc.GRECA:
                    # Arriba: el aire donde cierra el marco de los términos.
                    # Abajo: renglón y medio para la greca.
                    alto_fila = alto_linea + 10 + alto_fila_adornada
                    desfase = alto_linea + 10
                else:
                    alto_fila = alto_linea
                    desfase = 0
                if punto == adornos_svc.TERMINOS:
                    marco_desde = y + 2
                if punto == adornos_svc.GRECA and marco_desde is not None:
                    # Cierra el marco de los términos antes de la greca.
                    adornos_svc.dibujar_marco(
                        painter, adorno, MARGEN - 6, marco_desde, ancho - MARGEN + 6,
                        y + alto_linea * 0.6, tam_adorno * 0.62,
                    )
                    _restaurar()
                    marco_desde = None
                _escribir_en_rejilla(painter, cuerpo, MARGEN, y + desfase + metrica.ascent(), avance)
                if punto is not None:
                    y_grande = y + (alto_fila_adornada - tam_adorno) / 2
                    if punto in (adornos_svc.FLANCOS, adornos_svc.TERMINOS):
                        # Dentro del recuadro, a dos casillas del borde: ahí
                        # el renglón centrado deja aire de sobra.
                        adornos_svc.dibujar_flancos(
                            painter, adorno,
                            MARGEN + avance * 2.5, ancho - MARGEN - avance * 2.5 - tam_adorno,
                            y_grande, tam_adorno,
                        )
                    elif punto == adornos_svc.CABECERA:
                        adornos_svc.dibujar_flancos(
                            painter, adorno,
                            MARGEN + avance * 1.5, ancho - MARGEN - avance * 1.5 - tam_adorno,
                            y_grande, tam_adorno, dibujo=adorno.cabecera,
                        )
                    elif punto == adornos_svc.RESUMEN:
                        adorno.mini(
                            painter, ancho - MARGEN - avance * 2 - tam_mini,
                            y + (alto_linea - tam_mini) / 2, tam_mini,
                        )
                    elif punto == adornos_svc.DIVISOR:
                        adornos_svc.dibujar_divisor(
                            painter, adorno, MARGEN, ancho - MARGEN,
                            y + (alto_linea - tam_mini) / 2, tam_mini,
                        )
                    else:  # GRECA
                        adornos_svc.dibujar_greca(
                            painter, adorno, MARGEN + avance * 2, ancho - MARGEN - avance * 2,
                            y + desfase + (alto_fila_adornada - tam_adorno) / 2, tam_adorno,
                        )
                    _restaurar()
                if punto == adornos_svc.FLANCOS:
                    en_articulos = True
                y += alto_fila
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
