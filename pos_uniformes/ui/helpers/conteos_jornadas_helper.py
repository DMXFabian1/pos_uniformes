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


def pintar_jornadas(window, *, abiertas, por_revisar, code: str) -> None:
    """Rellena las dos listas de la página Conteos.

    `abiertas`: [(JornadaRef, Avance, puede_seguir)]
    `por_revisar`: [(JornadaRef, Avance)] — solo llega algo si es el dueño.
    """
    mias = sum(1 for foto, _a, _p in abiertas if foto.empleada_code == code)
    escribir = getattr(window, "_conteos_card", None)
    if escribir is not None:
        escribir("a_medias", str(len(abiertas)), "jornadas sin terminar" if abiertas else "nada a medias")
        escribir("mias", str(mias), "que puedo seguir" if mias else "ninguna mía")
        escribir("por_revisar", str(len(por_revisar)), "esperando tu revisión" if por_revisar else "nada pendiente")
        cards = getattr(window, "_conteos_cards", {})
        if "por_revisar" in cards:
            from pos_uniformes.services.conteo_jornada_service import DUENO_CODE

            cards["por_revisar"][0].setVisible(code == DUENO_CODE)

    _vaciar(window.conteos_jornadas_box)
    if not abiertas:
        vacio = QLabel("No hay conteos a medias. Empieza uno con el botón de arriba.")
        vacio.setObjectName("libretaSubtitulo")
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
    for foto, avance in por_revisar:
        window.conteos_revisar_box.addWidget(
            _tarjeta(
                foto, avance, boton="Revisar", activo=True,
                al_click=window._conteos_revisar, resaltada=True,
            )
        )
