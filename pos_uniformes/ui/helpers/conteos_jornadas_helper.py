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

_ESTILO_TARJETA = (
    "QFrame#jornadaCard {{ background: #fffdf9; border: 1px solid {borde};"
    " border-radius: 10px; }}"
)
_ESTILO_BARRA = (
    "QProgressBar { background: #efe8dc; border: none; border-radius: 5px; max-height: 9px; }"
    "QProgressBar::chunk { background: #7aa87a; border-radius: 5px; }"
)


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
    card.setObjectName("jornadaCard")
    card.setStyleSheet(_ESTILO_TARJETA.format(borde="#a05334" if resaltada else "#e0d8cb"))
    ly = QHBoxLayout()
    ly.setContentsMargins(14, 10, 14, 10)
    ly.setSpacing(14)

    izq = QVBoxLayout()
    izq.setSpacing(2)
    titulo = QLabel(foto.titulo)
    titulo.setStyleSheet("font-size: 14px; font-weight: 700; color: #3a2a1a; border: none; background: transparent;")
    izq.addWidget(titulo)
    momento = foto.terminada_at or foto.iniciada_at
    detalle = QLabel(f"{foto.quien}  ·  {cuando(momento)}")
    detalle.setStyleSheet("font-size: 11px; color: #8a7a68; border: none; background: transparent;")
    izq.addWidget(detalle)
    ly.addLayout(izq, 1)

    der = QVBoxLayout()
    der.setSpacing(3)
    etiqueta = QLabel(texto_avance(avance))
    etiqueta.setStyleSheet("font-size: 12px; font-weight: 700; color: #6B4226; border: none; background: transparent;")
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
    btn.setObjectName("primaryButton" if activo else "secondaryButton")
    btn.setEnabled(activo)
    btn.setFixedHeight(34)
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
    _vaciar(window.conteos_jornadas_box)
    if not abiertas:
        vacio = QLabel("No hay conteos a medias. Empieza uno con el botón de arriba.")
        vacio.setObjectName("guidedStepHint")
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
