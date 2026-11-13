"""Ficha del cliente (E1-C3). Solo lectura: no hay botones que modifiquen.

E4-D: la pestaña «Fidelización» puede traer el panel del ADMIN con sus
acciones; sin él, se queda el aviso de antes."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.clientes.ficha_service import FichaCliente, FilaHistorial
from pos_uniformes.ui.styles import clientes_styles
from pos_uniformes.utils.date_format import format_display_datetime

ORIGEN_ETIQUETAS = {
    "venta_rapida": "Venta rapida",
    "presupuesto_kiosko": "Presupuesto (kiosko)",
    "pos_admin": "Configuracion",
    "": "Anterior",
}
#: 2026-11-12: rótulo de las ventas de la Caja antigua (solo si hay alguna).
SECCION_POS_ANTERIOR = "POS anterior (hasta abril 2026)"
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


def _telefono_legible(telefono: str) -> str:
    digitos = "".join(ch for ch in (telefono or "") if ch.isdigit())
    if len(digitos) == 10:
        return f"{digitos[:3]} {digitos[3:6]} {digitos[6:]}"
    return telefono or ""


def _chip(texto: str, tono: str) -> QLabel:
    chip = QLabel(texto)
    chip.setObjectName("cliChip")
    chip.setProperty("tono", tono)
    return chip


def _vacio(texto: str) -> QLabel:
    aviso = QLabel(texto)
    aviso.setObjectName("cliVacio")
    aviso.setAlignment(Qt.AlignmentFlag.AlignCenter)
    aviso.setWordWrap(True)
    return aviso


def _tabla(encabezados: list[str], filas: list[FilaHistorial], vacio: str) -> QWidget:
    contenedor = QWidget()
    caja = QVBoxLayout(contenedor)
    caja.setContentsMargins(0, 0, 0, 0)
    if not filas:
        caja.addWidget(_vacio(vacio))
        caja.addStretch()
        return contenedor
    tabla = QTableWidget(len(filas), len(encabezados) + 1)
    tabla.setHorizontalHeaderLabels(["Fecha", *encabezados])
    tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    tabla.verticalHeader().setVisible(False)
    tabla.verticalHeader().setDefaultSectionSize(36)
    tabla.setShowGrid(False)
    tabla.setAlternatingRowColors(True)
    tabla.setObjectName("cliTabla")
    for r, fila in enumerate(filas):
        tabla.setItem(r, 0, QTableWidgetItem(format_display_datetime(fila.fecha)))
        for c, valor in enumerate(fila.columnas, start=1):
            tabla.setItem(r, c, QTableWidgetItem(valor))
    encabezado = tabla.horizontalHeader()
    for col in range(len(encabezados)):
        encabezado.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    encabezado.setSectionResizeMode(len(encabezados), QHeaderView.ResizeMode.Stretch)
    caja.addWidget(tabla)
    return contenedor


def _campo(etiqueta: str, valor: str) -> QFrame:
    tarjeta = QFrame()
    tarjeta.setObjectName("cliCampo")
    caja = QVBoxLayout(tarjeta)
    caja.setContentsMargins(14, 10, 14, 12)
    caja.setSpacing(2)
    nombre = QLabel(etiqueta.upper())
    nombre.setObjectName("cliCampoEtiqueta")
    dato = QLabel(valor or "—")
    dato.setObjectName("cliCampoValor")
    dato.setWordWrap(True)
    dato.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    caja.addWidget(nombre)
    caja.addWidget(dato)
    return tarjeta


def _estado(ficha: FichaCliente) -> tuple[str, str, str]:
    """(texto del chip, tono, texto largo)."""
    if ficha.archivado_en is not None:
        largo = f"Archivada el {format_display_datetime(ficha.archivado_en)}"
        if ficha.archivado_motivo:
            largo += f" · {ficha.archivado_motivo}"
        return "Archivada", "archivado", largo
    if ficha.activo:
        return "Activa", "activo", "Activa"
    return "Inactiva", "inactivo", "Inactiva"


def _encabezado(ficha: FichaCliente, programa: str | None) -> QFrame:
    tarjeta = QFrame()
    tarjeta.setObjectName("cliHeaderCard")
    fila = QHBoxLayout(tarjeta)
    fila.setContentsMargins(18, 16, 18, 16)
    fila.setSpacing(16)
    avatar = QLabel(clientes_styles.iniciales(ficha.nombre))
    avatar.setObjectName("cliAvatar")
    avatar.setFixedSize(56, 56)
    avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
    fila.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)

    textos = QVBoxLayout()
    textos.setSpacing(4)
    nombre = QLabel(ficha.nombre)
    nombre.setObjectName("cliTitulo")
    nombre.setWordWrap(True)
    nombre.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    partes = [ficha.codigo]
    if ficha.telefono:
        partes.append(_telefono_legible(ficha.telefono))
    subtitulo = QLabel("  ·  ".join(partes))
    subtitulo.setObjectName("cliSubtitulo")
    subtitulo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    chips = QHBoxLayout()
    chips.setSpacing(6)
    texto_estado, tono_estado, _largo = _estado(ficha)
    chips.addWidget(_chip(texto_estado, tono_estado))
    chips.addWidget(_chip(ficha.tipo or "Sin tipo", "tipo"))
    if programa:
        chips.addWidget(_chip(f"★ {programa}", "programa"))
    chips.addStretch()
    textos.addWidget(nombre)
    textos.addWidget(subtitulo)
    textos.addSpacing(2)
    textos.addLayout(chips)
    fila.addLayout(textos, 1)
    return tarjeta


def _pestana_datos(ficha: FichaCliente) -> QWidget:
    datos = QWidget()
    caja = QVBoxLayout(datos)
    caja.setContentsMargins(4, 4, 4, 4)
    caja.setSpacing(10)
    rejilla = QGridLayout()
    rejilla.setHorizontalSpacing(10)
    rejilla.setVerticalSpacing(10)
    _texto, _tono, estado_largo = _estado(ficha)
    campos = (
        ("Código", ficha.codigo),
        ("Teléfono", _telefono_legible(ficha.telefono) or "Sin teléfono"),
        ("Tipo", ficha.tipo or "Sin tipo"),
        ("Origen del alta", etiqueta_origen(ficha.origen)),
        ("Alta", format_display_datetime(ficha.alta) if ficha.alta else "Sin fecha"),
        ("Estado", estado_largo),
    )
    for i, (etiqueta, valor) in enumerate(campos):
        rejilla.addWidget(_campo(etiqueta, valor), i // 3, i % 3)
    for col in range(3):
        rejilla.setColumnStretch(col, 1)
    caja.addLayout(rejilla)
    caja.addWidget(_campo("Notas", ficha.notas or "Sin notas"))
    caja.addStretch()
    return datos


def _seccion(texto: str) -> QLabel:
    etiqueta = QLabel(texto.upper())
    etiqueta.setObjectName("cliSeccion")
    return etiqueta


def construir_ficha_dialog(
    parent: QWidget | None, ficha: FichaCliente, *, panel_fidelizacion: QWidget | None = None
) -> QDialog:
    dialog = QDialog(parent)
    clientes_styles.aplicar(dialog)
    dialog.setWindowTitle(f"Ficha {ficha.codigo}")
    dialog.setMinimumSize(900, 680)
    caja = QVBoxLayout(dialog)
    caja.setContentsMargins(18, 18, 18, 14)
    caja.setSpacing(14)
    panel = getattr(panel_fidelizacion, "panel", None)
    caja.addWidget(_encabezado(ficha, getattr(panel, "actual", None)))

    pestanas = QTabWidget()
    pestanas.setObjectName("fichaPestanas")
    pestanas.addTab(_pestana_datos(ficha), "Datos")

    if panel_fidelizacion is not None:
        pestanas.addTab(panel_fidelizacion, "Fidelizacion")
    else:
        fidelizacion = QWidget()
        caja_fid = QVBoxLayout(fidelizacion)
        aviso = QLabel(PROGRAMAS_PENDIENTES)
        aviso.setObjectName("cliVacio")
        aviso.setWordWrap(True)
        caja_fid.addWidget(aviso)
        caja_fid.addStretch()
        pestanas.addTab(fidelizacion, "Fidelizacion")

    compras = QWidget()
    caja_compras = QVBoxLayout(compras)
    caja_compras.setSpacing(8)
    caja_compras.addWidget(_seccion("Libreta"))
    caja_compras.addWidget(_tabla(["Tipo", "Piezas", "Empleada", "Importe"], ficha.libreta, "Sin registros en la Libreta."))
    if ficha.libreta_privadas:
        privadas = QLabel(f"Ademas hay {ficha.libreta_privadas} registro(s) privado(s) que no se muestran.")
        privadas.setObjectName("cliNota")
        caja_compras.addWidget(privadas)
    # 2026-11-12 (Daniel: «la caja antigua ya no es de utilidad, todo lo
    # demás corre en libreta y kioskos»): las ventas de la Caja antigua ya no
    # crecen. La sección solo aparece si el cliente tiene alguna, y rotulada
    # como lo que es; si no, ni se pinta (antes salía siempre vacía).
    if ficha.ventas:
        caja_compras.addWidget(_seccion(SECCION_POS_ANTERIOR))
        caja_compras.addWidget(_tabla(["Folio", "Estado", "Total"], ficha.ventas, ""))
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
    cerrar.setAutoDefault(False)
    cerrar.clicked.connect(dialog.reject)
    pie.addWidget(cerrar)
    caja.addLayout(pie)
    return dialog
