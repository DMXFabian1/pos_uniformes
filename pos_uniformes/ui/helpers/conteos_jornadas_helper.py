"""Las tarjetas de jornada de la sección Conteos.

Cada jornada abierta es una tarjeta con escuela, quién, cuándo, el avance
("4 de 14 prendas") y el botón Seguir — que solo se prende para quien la
abrió (o el dueño). Las terminadas sin revisar son tarjetas parecidas, solo
para el dueño, con el botón Revisar.

Vive aparte para no engordar `quote_satellite_window.py`.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

# La tarjeta es un `libretaCard` (mismo estilo de la hoja global); la propia
# se resalta con el borde de la marca, igual que las cosas activas en la Libreta.
_ESTILO_PROPIA = (
    "QFrame#libretaCard { border: 1.5px solid #c76b39; }"
)
_ESTILO_BARRA = (
    "QProgressBar { background: #efe8dc; border: none; border-radius: 5px; max-height: 9px; }"
    "QProgressBar::chunk { background: #7aa87a; border-radius: 5px; }"
)
_TXT = "background: transparent; border: none;"


def _vaciar(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()


def texto_avance(avance) -> str:
    """'4 de 14 prendas · 31 de 128 tallas'."""
    return (
        f"{avance.prendas_hechas} de {avance.prendas_total} prendas"
        f"  ·  {avance.tallas_hechas} de {avance.tallas_total} tallas"
    )


def _tarjeta(foto, avance, *, boton: str, activo: bool, al_click, resaltada: bool) -> QFrame:
    from pos_uniformes.services.conteo_jornada_service import cuando

    card = QFrame()
    card.setObjectName("libretaCard")
    # Dentro de un área con scroll, sin esto la tarjeta se aplasta hasta
    # encimar los textos cuando la página compite por altura.
    card.setMinimumHeight(68)
    if resaltada:
        card.setStyleSheet(_ESTILO_PROPIA)
    ly = QHBoxLayout()
    ly.setContentsMargins(16, 12, 16, 12)
    ly.setSpacing(14)

    izq = QVBoxLayout()
    izq.setSpacing(2)
    titulo = QLabel(foto.titulo)
    titulo.setStyleSheet(f"font-size: 15px; font-weight: 800; color: #2c2a27; {_TXT}")
    izq.addWidget(titulo)
    momento = foto.terminada_at or foto.iniciada_at
    detalle = QLabel(f"{foto.quien}  ·  {cuando(momento)}")
    detalle.setStyleSheet(f"font-size: 12px; color: #8a8177; {_TXT}")
    izq.addWidget(detalle)
    ly.addLayout(izq, 1)

    der = QVBoxLayout()
    der.setSpacing(3)
    etiqueta = QLabel(texto_avance(avance))
    etiqueta.setStyleSheet(f"font-size: 12px; font-weight: 800; color: #73341c; {_TXT}")
    etiqueta.setAlignment(Qt.AlignmentFlag.AlignRight)
    der.addWidget(etiqueta)
    barra = QProgressBar()
    barra.setMaximum(max(1, avance.tallas_total))
    barra.setValue(min(avance.tallas_hechas, max(1, avance.tallas_total)))
    barra.setTextVisible(False)
    barra.setFixedWidth(200)
    barra.setStyleSheet(_ESTILO_BARRA)
    der.addWidget(barra)
    ly.addLayout(der)

    btn = QPushButton(boton if activo else "Es de otra")
    if activo:
        btn.setObjectName("primaryButton")
    btn.setEnabled(activo)
    btn.setAutoDefault(False)
    if activo:
        btn.clicked.connect(lambda _c=False, f=foto: al_click(f))
    ly.addWidget(btn)
    card.setLayout(ly)
    return card


def pintar_jornadas(window, *, abiertas, por_revisar, code: str, recientes=()) -> None:
    """Rellena la página Conteos: números, listas e historial.

    `abiertas`: [(JornadaRef, Avance, puede_seguir)]
    `por_revisar`: [(JornadaRef, Avance)] — solo llega algo si es el dueño.
    `recientes`: [(JornadaRef, Avance)] — las últimas terminadas.
    """
    from pos_uniformes.services.conteo_jornada_service import DUENO_CODE

    mias = sum(1 for foto, _a, _p in abiertas if foto.empleada_code == code)
    escribir = getattr(window, "_conteos_card", None)
    if escribir is not None:
        escribir("a_medias", str(len(abiertas)), "jornadas sin terminar" if abiertas else "nada a medias")
        escribir("mias", str(mias), "que puedo seguir" if mias else "ninguna mía")
        escribir("por_revisar", str(len(por_revisar)), "esperando tu revisión" if por_revisar else "nada pendiente")
        cards = getattr(window, "_conteos_cards", {})
        if "por_revisar" in cards:
            cards["por_revisar"][0].setVisible(code == DUENO_CODE)

    # Subtítulo bajo el saludo, como "0 operacion(es) hoy" en la Libreta.
    sub = getattr(window, "conteos_quien_label", None)
    if sub is not None:
        partes = []
        if abiertas:
            partes.append(f"{len(abiertas)} a medias" + (f" ({mias} tuya{'s' if mias != 1 else ''})" if mias else ""))
        if por_revisar:
            partes.append(f"{len(por_revisar)} por revisar")
        sub.setText("  ·  ".join(partes) if partes else "Nada a medias")

    _vaciar(window.conteos_jornadas_box)
    if not abiertas:
        vacio = QLabel("No hay conteos a medias. Empieza uno desde la barra de arriba.")
        vacio.setObjectName("libretaPanelVacio")
        window.conteos_jornadas_box.addWidget(vacio)
    for foto, avance, puede in abiertas:
        window.conteos_jornadas_box.addWidget(
            _tarjeta(
                foto, avance, boton="Seguir", activo=puede,
                al_click=window._conteos_capturar, resaltada=(foto.empleada_code == code),
            )
        )

    _vaciar(window.conteos_revisar_box)
    window.conteos_revisar_titulo.setVisible(bool(por_revisar))
    panel = getattr(window, "conteos_revisar_panel", None)
    if panel is not None:
        panel.setVisible(bool(por_revisar))
    for foto, avance in por_revisar:
        window.conteos_revisar_box.addWidget(
            _tarjeta(
                foto, avance, boton="Revisar", activo=True,
                al_click=window._conteos_revisar, resaltada=True,
            )
        )


    tabla = getattr(window, "conteos_historial_table", None)
    if tabla is not None:
        pintar_historial(tabla, recientes)


def pintar_historial(tabla, recientes) -> None:
    """Las últimas jornadas terminadas, una fila cada una."""
    from PyQt6.QtGui import QBrush, QColor
    from PyQt6.QtWidgets import QTableWidgetItem

    from pos_uniformes.services.conteo_jornada_service import cuando

    colores = {"Aplicada": "#166534", "Descartada": "#8a8177", "Por revisar": "#b9770e"}
    filas = list(recientes)
    tabla.setRowCount(len(filas))
    for i, (foto, avance) in enumerate(filas):
        estado = foto.estado
        valores = (
            foto.titulo, foto.quien, cuando(foto.terminada_at),
            f"{avance.tallas_hechas} de {avance.tallas_total}", estado,
        )
        for col, txt in enumerate(valores):
            item = QTableWidgetItem(txt)
            if col in (2, 3, 4):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col == 4:
                item.setForeground(QBrush(QColor(colores.get(estado, "#2c2a27"))))
            tabla.setItem(i, col, item)
    if not filas:
        tabla.setRowCount(1)
        item = QTableWidgetItem("Todavía no hay conteos terminados.")
        item.setForeground(QBrush(QColor("#8a8177")))
        tabla.setItem(0, 0, item)
        tabla.setSpan(0, 0, 1, tabla.columnCount())
    else:
        tabla.clearSpans()
