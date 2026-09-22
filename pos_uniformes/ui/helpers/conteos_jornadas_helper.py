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


def _tarjeta(foto, avance, *, boton: str, activo: bool, al_click, resaltada: bool, extras=()) -> QFrame:
    """`extras`: [(texto, callback, es_peligroso)] — botones chicos junto al
    principal (Reasignar, Eliminar)."""
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
    titulo.setMinimumWidth(0)
    titulo.setWordWrap(True)
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
    etiqueta.setMinimumWidth(0)
    der.addWidget(etiqueta)
    barra = QProgressBar()
    barra.setMaximum(max(1, avance.tallas_total))
    barra.setValue(min(avance.tallas_hechas, max(1, avance.tallas_total)))
    barra.setTextVisible(False)
    # Ancho máximo, no fijo: con 35 tarjetas el ancho fijo sacaba scroll
    # horizontal en el kiosko (2026-09-22).
    barra.setMaximumWidth(200)
    barra.setMinimumWidth(80)
    barra.setStyleSheet(_ESTILO_BARRA)
    der.addWidget(barra)
    ly.addLayout(der)

    for texto, cb, peligroso in extras:
        chico = QPushButton(texto)
        chico.setObjectName("dangerButton" if peligroso else "")
        chico.setAutoDefault(False)
        chico.setStyleSheet("QPushButton { padding: 5px 10px; font-size: 12px; }")
        chico.clicked.connect(lambda _c=False, f=foto, c=cb: c(f))
        ly.addWidget(chico)
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
        escribir("mias", str(mias), "las empecé yo" if mias else "ninguna empezada por mí")
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
    # Sin jornadas a medias la sección desaparece: el "no hay nada" ocupaba
    # media pantalla para no decir nada (Daniel, 2026-09-22).
    for nombre in ("conteos_jornadas_titulo", "conteos_jornadas_panel"):
        w = getattr(window, nombre, None)
        if w is not None:
            w.setVisible(bool(abiertas))
    from pos_uniformes.services.conteo_jornada_service import puede_eliminarla

    reasignar = getattr(window, "_conteos_reasignar", None)
    eliminar = getattr(window, "_conteos_eliminar", None)
    for foto, avance, puede in abiertas:
        # Reasignar: solo el dueño. Eliminar: el dueño o quien la abrió (para
        # las duplicadas o abiertas por error, como pidió Daniel el 2026-09-13).
        extras = []
        if reasignar is not None and code == DUENO_CODE:
            extras.append(("Reasignar", reasignar, False))
        if eliminar is not None and puede_eliminarla(foto, code):
            extras.append(("Eliminar", eliminar, True))
        window.conteos_jornadas_box.addWidget(
            _tarjeta(
                foto, avance, boton="Seguir", activo=puede,
                al_click=window._conteos_capturar, resaltada=(foto.empleada_code == code),
                extras=extras,
            )
        )

    window.conteos_revisar_titulo.setVisible(bool(por_revisar))
    panel = getattr(window, "conteos_revisar_panel", None)
    if panel is not None:
        panel.setVisible(bool(por_revisar))
    # De a poquitas: 35 tarjetas de golpe eran una pared (2026-09-22).
    _pintar_por_revisar(window, por_revisar, tope=8)


    tabla = getattr(window, "conteos_historial_table", None)
    if tabla is not None:
        pintar_historial(tabla, recientes)


def _pintar_por_revisar(window, por_revisar, *, tope: int | None) -> None:
    from PyQt6.QtWidgets import QPushButton

    _vaciar(window.conteos_revisar_box)
    filas = list(por_revisar)
    mostrar = filas if tope is None else filas[:tope]
    for foto, avance in mostrar:
        window.conteos_revisar_box.addWidget(
            _tarjeta(
                foto, avance, boton="Revisar", activo=True,
                al_click=window._conteos_revisar, resaltada=True,
            )
        )
    if len(filas) > len(mostrar):
        mas = QPushButton(f"▾ ver las otras {len(filas) - len(mostrar)}")
        mas.setAutoDefault(False)
        mas.setStyleSheet("border: none; color: #a8481f; font-size: 13px; background: transparent;")
        mas.clicked.connect(lambda _c=False: _pintar_por_revisar(window, filas, tope=None))
        window.conteos_revisar_box.addWidget(mas)


def pintar_historial(tabla, filas) -> None:
    """El tablero: cada escuela y prenda básica con su último conteo
    (`FilaTablero`), o las jornadas recientes `(JornadaRef, Avance)` de antes."""
    from PyQt6.QtGui import QBrush, QColor
    from PyQt6.QtWidgets import QTableWidgetItem

    from pos_uniformes.services.conteo_jornada_service import cuando

    colores = {
        "Aplicada": "#166534", "Descartada": "#8a8177", "Por revisar": "#b9770e",
        "En proceso": "#b45309", "Nunca": "#b91c1c", "Conteo viejo": "#8a8177",
    }
    filas = list(filas)
    tabla.setRowCount(len(filas))
    for i, f in enumerate(filas):
        if isinstance(f, tuple):   # formato viejo: (JornadaRef, Avance)
            foto, avance = f
            valores = (foto.titulo, cuando(foto.terminada_at), "", foto.quien, f"{avance.tallas_hechas} de {avance.tallas_total}", foto.estado)
            estado = foto.estado
        else:
            u = f.ultimo
            fecha = u.fecha.astimezone().strftime("%d/%m/%Y") if u.fecha is not None and u.fecha.tzinfo else (u.fecha.strftime("%d/%m/%Y") if u.fecha is not None else "")
            hace = u.texto().split(" (")[0] if u.fecha is not None else "nunca"
            quien = f.quien_en_proceso or u.quien
            valores = (f.titulo, hace, fecha, quien, f.tallas, f.estado + (f" · {f.quien_en_proceso}" if f.quien_en_proceso else ""))
            estado = f.estado
        jornada_id = None if isinstance(f, tuple) else f.jornada_id
        for col, txt in enumerate(valores):
            item = QTableWidgetItem(txt)
            item.setData(Qt.ItemDataRole.UserRole, jornada_id)   # doble clic → comparativo
            if jornada_id is not None:
                item.setToolTip("Doble clic: comparar con el conteo anterior")
            if col in (1, 2, 4, 5):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col == 5:
                item.setForeground(QBrush(QColor(colores.get(estado, "#2c2a27"))))
            if col == 1 and estado == "Nunca":
                item.setForeground(QBrush(QColor("#b91c1c")))
            tabla.setItem(i, col, item)
    if not filas:
        tabla.setRowCount(1)
        item = QTableWidgetItem("Todavía no hay conteos terminados.")
        item.setForeground(QBrush(QColor("#8a8177")))
        tabla.setItem(0, 0, item)
        tabla.setSpan(0, 0, 1, tabla.columnCount())
    else:
        tabla.clearSpans()
