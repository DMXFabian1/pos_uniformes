"""La Libreta de la empleada, agrupada (Daniel, 2026-11-12).

«Me refería a completamente cómo ven ellas su libreta: que quede más clara o
agrupada.» Antes todo iba en una sola columna, uno debajo del otro: la tarjeta
del ciclo, dos botones del ancho de la pantalla, avisos sueltos en naranja,
la tarjeta del descuento y hasta abajo sus ventas.

Ahora, debajo de los números de hoy, dos columnas:

- Izquierda, «LO QUE LLEVAS»: la meta y sus ventas.
- Derecha, sus cosas, cada una en su recuadro:
  «AVISOS PARA TI» (respuestas de Daniel), «MI PAGO» (comisiones desde su
  último pago, próximo pago, el préstamo), «MIS DESCANSOS» (el siguiente, pedir
  uno, vacaciones) y «MI DESCUENTO».

Aquí solo se ACOMODAN los widgets que ya arma la ventana: quién se ve y qué
dice lo siguen decidiendo los mismos métodos de siempre. Cada recuadro se
esconde solo cuando no le queda nada visible adentro (un filtro de eventos
mira cuándo se muestran o esconden sus piezas), así nada de esa lógica cambia.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

TARJETA = "#fffdf9"
BORDE = "#e6dccd"
GRIS = "#8a7a68"

_EVENTOS = (QEvent.Type.ShowToParent, QEvent.Type.HideToParent)


def _grupo(titulo: str) -> tuple[QFrame, QVBoxLayout]:
    marco = QFrame()
    marco.setObjectName("libretaGrupo")
    marco.setStyleSheet(
        f"QFrame#libretaGrupo {{ background: {TARJETA}; border: 1px solid {BORDE}; border-radius: 16px; }}"
    )
    ly = QVBoxLayout(marco)
    ly.setContentsMargins(18, 14, 18, 16)
    ly.setSpacing(8)
    encabezado = QLabel(titulo)
    encabezado.setStyleSheet(
        f"background: transparent; color: {GRIS}; font-size: 12px; font-weight: 800; letter-spacing: 1.5px;"
    )
    ly.addWidget(encabezado)
    return marco, ly


def _dato(tile: QWidget) -> QWidget:
    """Un dato del ciclo (⭐ 73 / 💵 sáb 14 nov / 🛌 dom 15 nov) sin el fondo naranja."""
    tile.setStyleSheet("background: transparent;")
    return tile


class _Vigia(QObject):
    """Cuando una pieza se muestra o se esconde, rehace qué recuadro se ve."""

    def __init__(self, win) -> None:
        super().__init__(win)
        self._win = win

    def eventFilter(self, obj, ev):  # noqa: N802 (API de Qt)
        if ev.type() in _EVENTOS:
            if obj is getattr(self._win, "libreta_ciclo_banner", None) and ev.type() == QEvent.Type.HideToParent:
                # Sin ciclo, sus datos tampoco (los pinta el mismo método al haberlo).
                for tile, _v, _c in self._win._libreta_ciclo_tiles:
                    tile.setVisible(False)
            sincronizar(self._win)
        return False


def agrupar(win, view_ly: QVBoxLayout) -> None:
    """Saca las piezas de la empleada de la columna y las acomoda en grupos."""
    banner = win.libreta_ciclo_banner
    indice = view_ly.indexOf(banner)
    piezas = (
        banner, win.libreta_prestamo_button, win.libreta_prestamo_aviso,
        win.libreta_descanso_button, win.libreta_descanso_aviso, win.libreta_descanso_respuesta,
        win.libreta_vacaciones_button, win.libreta_descanso_visto_button,
        win.libreta_meta_bar, win.libreta_nivel_tarjeta, win.libreta_emp_list,
    )
    for w in piezas:
        view_ly.removeWidget(w)
    # La tarjeta del ciclo se queda guardada (oculta) solo como la llave de
    # "hay ciclo": sus tres datos se van a «Mi pago» y «Mis descansos».
    win._libreta_banner_guardado = QWidget()
    banner.setParent(win._libreta_banner_guardado)
    tiles = [t for t, _v, _c in win._libreta_ciclo_tiles]

    cuerpo = QWidget()
    columnas = QHBoxLayout(cuerpo)
    columnas.setContentsMargins(0, 0, 0, 0)
    columnas.setSpacing(14)

    # ── Izquierda: lo que lleva ──
    ventas, v_ly = _grupo("🛍  LO QUE LLEVAS")
    v_ly.addWidget(win.libreta_meta_bar)
    # Ya está dentro de su recuadro: sin el marco propio (se veía doble).
    win.libreta_emp_list.setStyleSheet(
        "QListWidget#libretaLista { border: none; background: transparent; padding: 0; }"
    )
    v_ly.addWidget(win.libreta_emp_list)
    v_ly.addStretch(1)
    columnas.addWidget(ventas, 3)

    # ── Derecha: sus cosas ──
    derecha = QVBoxLayout()
    derecha.setSpacing(12)

    avisos, a_ly = _grupo("📬  AVISOS PARA TI")
    a_ly.addWidget(win.libreta_descanso_respuesta)
    a_ly.addWidget(win.libreta_descanso_visto_button)
    derecha.addWidget(avisos)

    pago, p_ly = _grupo("💵  MI PAGO")
    datos = QHBoxLayout()
    datos.setSpacing(18)
    for tile in tiles[:2]:
        datos.addWidget(_dato(tile), 1)
    p_ly.addLayout(datos)
    p_ly.addWidget(win.libreta_prestamo_aviso)
    p_ly.addWidget(win.libreta_prestamo_button)
    derecha.addWidget(pago)

    descansos, d_ly = _grupo("🛌  MIS DESCANSOS")
    if len(tiles) > 2:
        d_ly.addWidget(_dato(tiles[2]))
    d_ly.addWidget(win.libreta_descanso_aviso)
    botones = QHBoxLayout()
    botones.setSpacing(8)
    botones.addWidget(win.libreta_descanso_button, 1)
    botones.addWidget(win.libreta_vacaciones_button, 1)
    d_ly.addLayout(botones)
    derecha.addWidget(descansos)

    win.libreta_nivel_tarjeta.set_vertical(True)
    derecha.addWidget(win.libreta_nivel_tarjeta)
    derecha.addStretch(1)
    columnas.addLayout(derecha, 2)

    view_ly.insertWidget(max(indice, 0), cuerpo)
    win.libreta_emp_cuerpo = cuerpo
    win._libreta_grupos = {
        "ventas": (ventas, (win.libreta_meta_bar, win.libreta_emp_list)),
        "avisos": (avisos, (win.libreta_descanso_respuesta,)),
        "pago": (pago, (*tiles[:2], win.libreta_prestamo_aviso, win.libreta_prestamo_button)),
        "descansos": (descansos, (*tiles[2:], win.libreta_descanso_aviso, win.libreta_descanso_button,
                                  win.libreta_vacaciones_button)),
    }
    if banner.isHidden():
        for tile in tiles:
            tile.setVisible(False)
    vigia = _Vigia(win)
    win._libreta_vigia = vigia
    for _grupo_w, contenidos in win._libreta_grupos.values():
        for w in contenidos:
            w.installEventFilter(vigia)
    banner.installEventFilter(vigia)
    sincronizar(win)


def sincronizar(win) -> None:
    """Cada recuadro se ve solo si le queda algo visible adentro."""
    for marco, contenidos in getattr(win, "_libreta_grupos", {}).values():
        marco.setVisible(any(not w.isHidden() for w in contenidos))
