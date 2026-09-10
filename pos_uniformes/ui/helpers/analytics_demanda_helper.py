"""Bloque "Lo que se perdió" de la pestaña Analítica.

El bloque de arriba dice qué se vendió. Este dice qué se pidió y no se pudo
vender: lo que la Libreta nunca podría contar porque no hubo venta.

Sale solo del uso normal del kiosko (ver `services/demanda_service.py`).
Aquí se convierte en dos listas que sirven para actuar:

  Qué pedir      producto y talla que tocaron estando en cero.
  No lo encuentran   texto que buscaron y no devolvió nada. Puede ser
                 catálogo incompleto, o un sinónimo que le falta al buscador.

Lo repetido tres veces o más va marcado: una señal suelta es ruido.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

FILAS_MAX = 15
_ROJO = "#8a2f2f"


def _tabla(primera: str, segunda: str) -> QTableWidget:
    t = QTableWidget()
    t.setColumnCount(4)
    t.setHorizontalHeaderLabels([primera, segunda, "Piezas", "Última vez"])
    t.setObjectName("dataTable")
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setMinimumHeight(220)
    encabezado = t.horizontalHeader()
    encabezado.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    for col in (1, 2, 3):
        encabezado.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    return t


def construir(window) -> QGroupBox:
    """Crea el bloque y deja las tablas colgadas de `window`."""
    caja = QGroupBox("Lo que se perdió (pedido y sin producto)")
    caja.setObjectName("infoCard")
    ly = QVBoxLayout()
    ly.setSpacing(10)

    window.demanda_resumen_label = QLabel("Todavía no hay señales registradas.")
    window.demanda_resumen_label.setObjectName("analyticsLine")
    window.demanda_resumen_label.setWordWrap(True)
    ly.addWidget(window.demanda_resumen_label)

    pista = QLabel(
        "Se anota solo desde el kiosko: nadie llena formularios. "
        "En rojo lo que ya se repitió 3 veces o más — eso no es casualidad, es que falta producto."
    )
    pista.setObjectName("guidedStepHint")
    pista.setWordWrap(True)
    ly.addWidget(pista)

    rejilla = QGridLayout()
    rejilla.setHorizontalSpacing(12)
    for indice, (atributo, titulo, primera, segunda) in enumerate(
        (
            ("demanda_pedir_table", "Qué pedir", "Producto y talla", "Veces"),
            ("demanda_buscado_table", "No lo encuentran", "Lo que buscaron", "Veces"),
        )
    ):
        tabla = _tabla(primera, segunda)
        setattr(window, atributo, tabla)
        sub = QGroupBox(titulo)
        sub.setObjectName("infoCard")
        sub_ly = QVBoxLayout()
        sub_ly.addWidget(tabla)
        sub.setLayout(sub_ly)
        rejilla.addWidget(sub, 0, indice)
    rejilla.setColumnStretch(0, 1)
    rejilla.setColumnStretch(1, 1)
    ly.addLayout(rejilla)
    caja.setLayout(ly)
    return caja


def _fecha(momento) -> str:
    return momento.astimezone().strftime("%d/%m %H:%M") if momento else ""


def _llenar(tabla: QTableWidget, faltas: list) -> None:
    faltas = list(faltas)[:FILAS_MAX]
    tabla.setRowCount(len(faltas))
    for fila, f in enumerate(faltas):
        for col, texto in enumerate((f.clave, str(f.veces), str(f.piezas), _fecha(f.ultima))):
            celda = QTableWidgetItem(texto)
            if f.urgente:
                celda.setForeground(QColor(_ROJO))
            tabla.setItem(fila, col, celda)


def pintar(window, filas: list) -> None:
    """Llena el bloque con las señales del periodo."""
    from pos_uniformes.services import demanda_service as dm

    r = dm.resumen(filas)
    if not filas:
        window.demanda_resumen_label.setText(
            "Todavía no hay señales registradas en este periodo."
        )
    else:
        window.demanda_resumen_label.setText(
            f"{r.tallas_agotadas} veces pidieron algo agotado ({r.piezas_perdidas} piezas) · "
            f"{r.busquedas_vacias} búsquedas sin resultado · "
            f"{r.carritos_vacios} piezas escaneadas y canceladas"
        )
    for atributo, faltas in (
        ("demanda_pedir_table", dm.por_producto_talla(filas)),
        ("demanda_buscado_table", dm.por_texto(filas)),
    ):
        tabla = getattr(window, atributo, None)
        if tabla is not None:
            _llenar(tabla, faltas)


def cargar_y_pintar(window, session, desde, hasta) -> None:
    """Consulta el periodo y pinta. Nunca rompe la Analítica."""
    import logging

    from pos_uniformes.services.demanda_service import listar

    try:
        filas = listar(session, _aware(desde), _aware(hasta))
    except Exception:  # noqa: BLE001 — el resto de la Analítica debe seguir
        logging.getLogger(__name__).exception("Analítica: no se pudo leer la demanda")
        filas = []
    pintar(window, filas)


def _aware(momento):
    return momento.astimezone() if getattr(momento, "tzinfo", None) is None else momento
