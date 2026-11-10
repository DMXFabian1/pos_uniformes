"""Ficha del cliente (E1-C3). Solo lectura: no hay botones que modifiquen."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.clientes.ficha_service import FichaCliente, FilaHistorial
from pos_uniformes.utils.date_format import format_display_datetime

ORIGEN_ETIQUETAS = {
    "venta_rapida": "Venta rapida",
    "presupuesto_kiosko": "Presupuesto (kiosko)",
    "pos_admin": "Configuracion",
    "": "Anterior",
}
PROGRAMAS_PENDIENTES = "Programas: E4. Esta ficha todavia no tiene programa de fidelizacion."
EVENTO_ETIQUETAS = {
    "alta": "Alta",
    "alta_telefono_compartido": "Alta (telefono compartido)",
    "edicion": "Edicion",
    "cambio_tipo": "Cambio de tipo",
    "desactivacion": "Desactivada",
    "reactivacion": "Reactivada",
    "archivado": "Archivada",
    "desarchivado": "Desarchivada",
}


def etiqueta_origen(origen: str | None) -> str:
    return ORIGEN_ETIQUETAS.get(origen or "", origen or "")


def _evento_legible(fila: FilaHistorial) -> FilaHistorial:
    tipo, origen, usuario, detalle = fila.columnas
    return FilaHistorial(
        fecha=fila.fecha,
        columnas=(EVENTO_ETIQUETAS.get(tipo, tipo), etiqueta_origen(origen), usuario, detalle),
    )


def _tabla(encabezados: list[str], filas: list[FilaHistorial], vacio: str) -> QWidget:
    contenedor = QWidget()
    caja = QVBoxLayout(contenedor)
    if not filas:
        aviso = QLabel(vacio)
        aviso.setObjectName("subtleLine")
        caja.addWidget(aviso)
        caja.addStretch()
        return contenedor
    tabla = QTableWidget(len(filas), len(encabezados) + 1)
    tabla.setHorizontalHeaderLabels(["Fecha", *encabezados])
    tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tabla.verticalHeader().setVisible(False)
    tabla.setObjectName("dataTable")
    for r, fila in enumerate(filas):
        tabla.setItem(r, 0, QTableWidgetItem(format_display_datetime(fila.fecha)))
        for c, valor in enumerate(fila.columnas, start=1):
            tabla.setItem(r, c, QTableWidgetItem(valor))
    tabla.resizeColumnsToContents()
    tabla.horizontalHeader().setStretchLastSection(True)
    caja.addWidget(tabla)
    return contenedor


def construir_ficha_dialog(parent: QWidget | None, ficha: FichaCliente) -> QDialog:
    dialog = QDialog(parent)
    dialog.setWindowTitle(f"Ficha {ficha.codigo}")
    dialog.setMinimumSize(760, 520)
    caja = QVBoxLayout(dialog)
    titulo = QLabel(f"{ficha.nombre}  ·  {ficha.codigo}")
    titulo.setObjectName("analyticsLine")
    caja.addWidget(titulo)

    pestanas = QTabWidget()
    pestanas.setObjectName("fichaPestanas")

    datos = QWidget()
    form = QFormLayout(datos)
    if ficha.archivado_en is not None:
        estado = f"ARCHIVADO el {format_display_datetime(ficha.archivado_en)} ({ficha.archivado_motivo})"
    else:
        estado = "ACTIVO" if ficha.activo else "INACTIVO"
    for etiqueta, valor in (
        ("Codigo", ficha.codigo),
        ("Nombre", ficha.nombre),
        ("Telefono", ficha.telefono or "Sin telefono"),
        ("Tipo", ficha.tipo or "Sin tipo"),
        ("Origen", etiqueta_origen(ficha.origen)),
        ("Alta", format_display_datetime(ficha.alta)),
        ("Estado", estado),
        ("Notas", ficha.notas or ""),
    ):
        valor_label = QLabel(valor)
        valor_label.setWordWrap(True)
        form.addRow(etiqueta, valor_label)
    pestanas.addTab(datos, "Datos")

    fidelizacion = QWidget()
    caja_fid = QVBoxLayout(fidelizacion)
    aviso = QLabel(PROGRAMAS_PENDIENTES)
    aviso.setWordWrap(True)
    caja_fid.addWidget(aviso)
    caja_fid.addStretch()
    pestanas.addTab(fidelizacion, "Fidelizacion")

    compras = QWidget()
    caja_compras = QVBoxLayout(compras)
    caja_compras.addWidget(QLabel("Libreta"))
    caja_compras.addWidget(_tabla(["Tipo", "Piezas", "Empleada", "Importe"], ficha.libreta, "Sin registros en la Libreta."))
    if ficha.libreta_privadas:
        privadas = QLabel(f"Ademas hay {ficha.libreta_privadas} registro(s) privado(s) que no se muestran.")
        privadas.setObjectName("subtleLine")
        caja_compras.addWidget(privadas)
    caja_compras.addWidget(QLabel("Ventas del POS"))
    caja_compras.addWidget(_tabla(["Folio", "Estado", "Total"], ficha.ventas, "Sin ventas del POS."))
    pestanas.addTab(compras, "Compras")

    pestanas.addTab(
        _tabla(["Folio", "Estado", "Total", "Saldo"], ficha.apartados, "Sin apartados."),
        "Apartados",
    )
    pestanas.addTab(
        _tabla(["Evento", "Origen", "Usuario", "Detalle"], [_evento_legible(e) for e in ficha.eventos], "Sin eventos."),
        "Eventos",
    )
    caja.addWidget(pestanas, 1)

    pie = QHBoxLayout()
    pie.addStretch()
    cerrar = QPushButton("Cerrar")
    cerrar.setObjectName("toolbarGhostButton")
    cerrar.clicked.connect(dialog.reject)
    pie.addWidget(cerrar)
    caja.addLayout(pie)
    return dialog
