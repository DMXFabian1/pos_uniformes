"""E7: «Ofertas y liquidación» en el POS (Daniel, 2026-11-11).

Arriba, lo que está rebajado hoy: se puede quitar o imprimir su etiqueta.
Abajo, se buscan prendas (por SKU o por nombre, todas sus tallas) y se ponen
en Oferta (con último día) o Liquidación, con un % o un precio fijo. Las
reglas viven en `rebaja_service`.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Callable

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pos_uniformes.services import rebaja_service as reb

_logger = logging.getLogger(__name__)

COLUMNAS_REBAJAS = ["Marca", "Prenda", "Talla", "Antes", "Ahora", "Rebaja", "Hasta"]
COLUMNAS_PRENDAS = ["SKU", "Prenda", "Talla", "Color", "Precio"]


def _item(texto: str, dato=None) -> QTableWidgetItem:
    it = QTableWidgetItem(texto)
    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if dato is not None:
        it.setData(Qt.ItemDataRole.UserRole, dato)
    return it


class RebajasDialog(QDialog):
    def __init__(
        self,
        parent,
        session_factory,
        *,
        usuario_id: int | None = None,
        imprimir: Callable[[reb.FilaRebaja], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._usuario_id = usuario_id
        self._imprimir = imprimir
        self.setWindowTitle("Ofertas y liquidación")
        self.resize(820, 680)
        ly = QVBoxLayout(self)

        ayuda = QLabel(
            "Una prenda en Oferta o Liquidación se cobra a su precio rebajado y no lleva ningún otro "
            "descuento (empleadas, mayoreo) ni genera Monedero. Una oferta con último día termina sola; "
            "sin fecha, sigue hasta que la quites."
        )
        ayuda.setWordWrap(True)
        ly.addWidget(ayuda)

        # ── Lo rebajado hoy ──
        ly.addWidget(QLabel("<b>Rebajado hoy</b>"))
        self.tabla_rebajas = QTableWidget(0, len(COLUMNAS_REBAJAS))
        self.tabla_rebajas.setHorizontalHeaderLabels(COLUMNAS_REBAJAS)
        self.tabla_rebajas.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_rebajas.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tabla_rebajas.verticalHeader().setVisible(False)
        self.tabla_rebajas.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        ly.addWidget(self.tabla_rebajas, 1)
        fila_botones = QHBoxLayout()
        self.boton_quitar = QPushButton("Quitar rebaja")
        self.boton_quitar.clicked.connect(self._quitar)
        self.boton_imprimir = QPushButton("🏷 Imprimir etiqueta")
        self.boton_imprimir.clicked.connect(self._imprimir_seleccion)
        self.boton_imprimir.setVisible(imprimir is not None)
        fila_botones.addWidget(self.boton_quitar)
        fila_botones.addWidget(self.boton_imprimir)
        fila_botones.addStretch()
        ly.addLayout(fila_botones)

        # ── Poner en rebaja ──
        caja = QGroupBox("Poner en rebaja")
        caja_ly = QVBoxLayout(caja)
        buscar_ly = QHBoxLayout()
        self.buscar_input = QLineEdit()
        self.buscar_input.setPlaceholderText("SKU o nombre de la prenda…")
        self.buscar_input.returnPressed.connect(self._buscar)
        boton_buscar = QPushButton("Buscar")
        boton_buscar.clicked.connect(self._buscar)
        buscar_ly.addWidget(self.buscar_input, 1)
        buscar_ly.addWidget(boton_buscar)
        caja_ly.addLayout(buscar_ly)
        self.tabla_prendas = QTableWidget(0, len(COLUMNAS_PRENDAS))
        self.tabla_prendas.setHorizontalHeaderLabels(COLUMNAS_PRENDAS)
        self.tabla_prendas.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_prendas.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tabla_prendas.verticalHeader().setVisible(False)
        self.tabla_prendas.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        caja_ly.addWidget(self.tabla_prendas, 1)
        caja_ly.addWidget(QLabel("Selecciona las tallas (Ctrl+A para todas)."))

        opciones = QHBoxLayout()
        self.tipo_combo = QComboBox()
        self.tipo_combo.addItem("Oferta", reb.OFERTA)
        self.tipo_combo.addItem("Liquidación", reb.LIQUIDACION)
        self.tipo_combo.currentIndexChanged.connect(self._tipo_cambio)
        opciones.addWidget(self.tipo_combo)
        self.radio_pct = QRadioButton("Rebaja de")
        self.radio_precio = QRadioButton("Precio fijo")
        self.radio_pct.setChecked(True)
        grupo = QButtonGroup(self)
        grupo.addButton(self.radio_pct)
        grupo.addButton(self.radio_precio)
        self.pct_input = QDoubleSpinBox()
        self.pct_input.setRange(1, 90)
        self.pct_input.setDecimals(0)
        self.pct_input.setSuffix(" %")
        self.pct_input.setValue(20)
        self.precio_input = QDoubleSpinBox()
        self.precio_input.setRange(1, 99999)
        self.precio_input.setDecimals(0)
        self.precio_input.setPrefix("$")
        opciones.addWidget(self.radio_pct)
        opciones.addWidget(self.pct_input)
        opciones.addWidget(self.radio_precio)
        opciones.addWidget(self.precio_input)
        self.hasta_label = QLabel("Último día:")
        self.hasta_input = QDateEdit(QDate.currentDate().addDays(7))
        self.hasta_input.setCalendarPopup(True)
        self.hasta_input.setDisplayFormat("dd/MM/yyyy")
        self.sin_fecha_check = QCheckBox("Sin último día")
        self.sin_fecha_check.toggled.connect(lambda si: self.hasta_input.setEnabled(not si))
        opciones.addWidget(self.hasta_label)
        opciones.addWidget(self.hasta_input)
        opciones.addWidget(self.sin_fecha_check)
        opciones.addStretch()
        caja_ly.addLayout(opciones)
        self.boton_poner = QPushButton("Poner en rebaja")
        self.boton_poner.clicked.connect(self._poner)
        caja_ly.addWidget(self.boton_poner, 0, Qt.AlignmentFlag.AlignRight)
        ly.addWidget(caja, 1)

        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        ly.addWidget(cerrar, 0, Qt.AlignmentFlag.AlignRight)

        self._filas: list[reb.FilaRebaja] = []
        self.hubo_cambios = False
        self._refrescar()

    # ─── Datos ──────────────────────────────────────────────────────────

    def _refrescar(self) -> None:
        try:
            with self._session_factory() as session:
                self._filas = reb.listar(session)
                session.commit()  # las ofertas vencidas quedan terminadas
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Rebajas: no se pudo leer")
            QMessageBox.warning(self, "Ofertas y liquidación", f"No se pudo leer la lista.\n\n{exc}")
            self._filas = []
        self.tabla_rebajas.setRowCount(len(self._filas))
        for r, f in enumerate(self._filas):
            valores = [
                f.etiqueta, f.nombre, f.talla, f"${f.precio_normal:,.2f}", f"${f.precio:,.2f}",
                f"{f.descuento_pct} %", f"{f.hasta:%d/%m/%Y}" if f.hasta else "—",
            ]
            for c, v in enumerate(valores):
                self.tabla_rebajas.setItem(r, c, _item(v, f.variante_id if c == 0 else None))

    def _filas_elegidas(self) -> list[reb.FilaRebaja]:
        renglones = sorted({i.row() for i in self.tabla_rebajas.selectedIndexes()})
        return [self._filas[r] for r in renglones if 0 <= r < len(self._filas)]

    def _buscar(self) -> None:
        texto = self.buscar_input.text()
        try:
            with self._session_factory() as session:
                prendas = reb.buscar_prendas(session, texto)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Buscar", f"No se pudo buscar.\n\n{exc}")
            return
        self.tabla_prendas.setRowCount(len(prendas))
        for r, p in enumerate(prendas):
            valores = [p.sku, p.nombre, p.talla, p.color, f"${p.precio:,.2f}"]
            for c, v in enumerate(valores):
                self.tabla_prendas.setItem(r, c, _item(v, p.variante_id if c == 0 else None))
        if not prendas:
            QMessageBox.information(self, "Buscar", "No se encontró ninguna prenda activa.")

    def _variantes_elegidas(self) -> list[int]:
        renglones = sorted({i.row() for i in self.tabla_prendas.selectedIndexes()})
        return [int(self.tabla_prendas.item(r, 0).data(Qt.ItemDataRole.UserRole)) for r in renglones]

    # ─── Acciones ───────────────────────────────────────────────────────

    def _tipo_cambio(self) -> None:
        es_oferta = self.tipo_combo.currentData() == reb.OFERTA
        self.hasta_label.setVisible(es_oferta)
        self.hasta_input.setVisible(es_oferta)
        self.sin_fecha_check.setVisible(es_oferta)

    def _poner(self) -> None:
        ids = self._variantes_elegidas()
        if not ids:
            QMessageBox.information(self, "Poner en rebaja", "Selecciona al menos una talla.")
            return
        tipo = self.tipo_combo.currentData()
        qd = self.hasta_input.date()
        hasta = (
            date(qd.year(), qd.month(), qd.day())
            if tipo == reb.OFERTA and not self.sin_fecha_check.isChecked()
            else None
        )
        kwargs = (
            {"porcentaje": Decimal(str(self.pct_input.value()))}
            if self.radio_pct.isChecked()
            else {"precio": Decimal(str(self.precio_input.value()))}
        )
        try:
            with self._session_factory() as session:
                reb.marcar(session, ids, tipo=tipo, hasta=hasta, usuario_id=self._usuario_id, **kwargs)
                session.commit()
        except reb.RebajaInvalida as exc:
            QMessageBox.warning(self, "Poner en rebaja", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Rebajas: no se pudo guardar")
            QMessageBox.critical(self, "Poner en rebaja", f"No se pudo guardar.\n\n{exc}")
            return
        self.hubo_cambios = True
        self._refrescar()

    def _quitar(self) -> None:
        filas = self._filas_elegidas()
        if not filas:
            QMessageBox.information(self, "Quitar rebaja", "Selecciona en la lista de arriba lo que quieres quitar.")
            return
        si = QMessageBox.question(
            self, "Quitar rebaja", f"¿Regresar {len(filas)} prenda(s) a su precio normal?"
        )
        if si != QMessageBox.StandardButton.Yes:
            return
        try:
            with self._session_factory() as session:
                reb.quitar(session, [f.variante_id for f in filas])
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Quitar rebaja", f"No se pudo guardar.\n\n{exc}")
            return
        self.hubo_cambios = True
        self._refrescar()

    def _imprimir_seleccion(self) -> None:
        filas = self._filas_elegidas()
        if not filas or self._imprimir is None:
            QMessageBox.information(self, "Imprimir", "Selecciona en la lista de arriba qué etiquetas imprimir.")
            return
        for f in filas:
            try:
                self._imprimir(f)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Imprimir", f"No se pudo imprimir {f.sku}.\n\n{exc}")
                return


def imprimir_etiqueta_rebaja(fila: reb.FilaRebaja, imprimir_imagen: Callable[..., bool]) -> bool:
    """Arma la etiqueta de Oferta/Liquidación de esa prenda y la manda a la
    impresora de etiquetas cuadradas (DK-1221)."""
    from pos_uniformes.utils.rebaja_label_generator import render_rebaja, ruta_por_omision

    ruta = render_rebaja(
        tipo=fila.tipo, nombre=fila.nombre, talla=fila.talla, precio=fila.precio,
        precio_antes=fila.precio_normal, hasta=fila.hasta, output_path=ruta_por_omision(fila.sku),
    )
    return imprimir_imagen(ruta, title=f"Etiqueta {fila.sku}", copies=1, paper_mode="die_cut")
