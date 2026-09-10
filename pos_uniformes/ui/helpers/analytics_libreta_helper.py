"""Bloque "Ventas reales" de la pestaña Analítica, alimentado por la Libreta.

La analítica vieja lee `venta`/`venta_detalle`, tablas que quedaron en 8
registros de abril. Lo que de verdad se vende está en la Libreta del kiosko.
Este bloque muestra eso: piezas, importe, y los cortes que sirven para decidir
qué pedir (producto, prenda, escuela, talla, hora, empleada, forma de pago).

Vive aparte para no engordar `main_window.py`: la vista llama a `construir` y
el refresco llama a `pintar`.
"""

from __future__ import annotations

from decimal import Decimal

from PyQt6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

# (atributo en la ventana, título, encabezado de la primera columna)
TABLAS = (
    ("libreta_top_productos_table", "Productos más vendidos", "Producto"),
    ("libreta_por_pieza_table", "Por tipo de prenda", "Prenda"),
    ("libreta_por_escuela_table", "Por escuela", "Escuela"),
    ("libreta_por_talla_table", "Por talla", "Talla"),
    ("libreta_por_hora_table", "Por hora del día", "Hora"),
    ("libreta_por_empleada_table", "Por empleada", "Empleada"),
)
_COLUMNAS = ("Piezas", "Importe", "Precio prom.")
FILAS_MAX = 12


def _pesos(valor) -> str:
    return f"${Decimal(valor):,.2f}"


def _tabla() -> QTableWidget:
    t = QTableWidget()
    t.setColumnCount(1 + len(_COLUMNAS))
    t.setObjectName("dataTable")
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setMinimumHeight(180)
    return t


def construir(window) -> QGroupBox:
    """Crea el bloque y deja las tablas colgadas de `window`."""
    caja = QGroupBox("Ventas reales (Libreta del kiosko)")
    caja.setObjectName("infoCard")
    ly = QVBoxLayout()
    ly.setSpacing(10)

    window.libreta_analytics_resumen_label = QLabel("Sin ventas registradas en el periodo.")
    window.libreta_analytics_resumen_label.setObjectName("analyticsLine")
    window.libreta_analytics_resumen_label.setWordWrap(True)
    ly.addWidget(window.libreta_analytics_resumen_label)

    window.libreta_analytics_pago_label = QLabel("")
    window.libreta_analytics_pago_label.setObjectName("analyticsLine")
    ly.addWidget(window.libreta_analytics_pago_label)

    rejilla = QGridLayout()
    rejilla.setHorizontalSpacing(12)
    rejilla.setVerticalSpacing(10)
    for indice, (atributo, titulo, primera) in enumerate(TABLAS):
        tabla = _tabla()
        tabla.setHorizontalHeaderLabels([primera, *_COLUMNAS])
        encabezado = tabla.horizontalHeader()
        encabezado.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 1 + len(_COLUMNAS)):
            encabezado.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        setattr(window, atributo, tabla)
        sub = QGroupBox(titulo)
        sub.setObjectName("infoCard")
        sub_ly = QVBoxLayout()
        sub_ly.addWidget(tabla)
        sub.setLayout(sub_ly)
        rejilla.addWidget(sub, indice // 2, indice % 2)
    rejilla.setColumnStretch(0, 1)
    rejilla.setColumnStretch(1, 1)
    ly.addLayout(rejilla)
    caja.setLayout(ly)
    return caja


def _llenar(tabla: QTableWidget, grupos: list) -> None:
    grupos = list(grupos)[:FILAS_MAX]
    tabla.setRowCount(len(grupos))
    for fila, g in enumerate(grupos):
        valores = (g.clave, str(g.piezas), _pesos(g.importe), _pesos(g.precio_promedio))
        for col, texto in enumerate(valores):
            tabla.setItem(fila, col, QTableWidgetItem(texto))


def pintar(window, filas: list) -> None:
    """Llena el bloque con las filas del periodo (lista de `FilaVenta`)."""
    from pos_uniformes.services import analitica_libreta_service as an

    r = an.resumen(filas)
    if not filas:
        window.libreta_analytics_resumen_label.setText(
            "Sin ventas registradas en la Libreta para este periodo."
        )
        window.libreta_analytics_pago_label.setText("")
    else:
        window.libreta_analytics_resumen_label.setText(
            f"{r.piezas} piezas · {_pesos(r.importe)} · {r.lineas} líneas de venta · "
            f"{r.productos_distintos} productos distintos · {r.escuelas_distintas} escuelas · "
            f"precio promedio por pieza {_pesos(r.ticket_promedio_por_pieza)}"
        )
        pagos = an.por_forma_pago(filas)
        window.libreta_analytics_pago_label.setText(
            "Cobro:  " + "   ·   ".join(f"{g.clave} {_pesos(g.importe)} ({g.piezas} pzas)" for g in pagos)
        )
    for atributo, cortes in (
        ("libreta_top_productos_table", an.por_producto(filas)),
        ("libreta_por_pieza_table", an.por_pieza(filas)),
        ("libreta_por_escuela_table", an.por_escuela(filas)),
        ("libreta_por_talla_table", an.por_talla(filas)),
        ("libreta_por_hora_table", an.por_hora(filas)),
        ("libreta_por_empleada_table", an.por_empleada(filas)),
    ):
        tabla = getattr(window, atributo, None)
        if tabla is not None:
            _llenar(tabla, cortes)


def cargar_y_pintar(window, session, desde, hasta) -> None:
    """Consulta la Libreta del periodo y pinta. Nunca rompe la Analítica."""
    import logging

    from pos_uniformes.services.analitica_libreta_service import filas_de_periodo

    try:
        filas = filas_de_periodo(session, _aware(desde), _aware(hasta))
    except Exception:  # noqa: BLE001 — la analítica vieja debe seguir a la vista
        logging.getLogger(__name__).exception("Analítica: no se pudo leer la Libreta")
        filas = []
    pintar(window, filas)


def _aware(momento):
    """La Libreta guarda con zona; un datetime sin zona no compara bien."""
    return momento.astimezone() if getattr(momento, "tzinfo", None) is None else momento
