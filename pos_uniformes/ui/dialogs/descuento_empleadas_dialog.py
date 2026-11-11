"""E6: el dueño ajusta los niveles del descuento de empleadas y el tope del mes.

Cada renglón: «desde N comisiones en el mes → compra con X % el mes
siguiente». El primero siempre empieza en 0 (el de todas). Las reglas y la
validación viven en `incentivo_empleada_service`.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
)

from pos_uniformes.services import incentivo_empleada_service as inc

_logger = logging.getLogger(__name__)


class DescuentoEmpleadasDialog(QDialog):
    def __init__(self, niveles: list[inc.Nivel], tope: Decimal | None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Descuento de empleadas")
        self.setMinimumWidth(460)
        ly = QVBoxLayout(self)
        ayuda = QLabel(
            "Lo que cada empleada vende en un mes (en comisiones) le da el descuento "
            "con el que compra el mes siguiente. Sus propias compras no cuentan."
        )
        ayuda.setWordWrap(True)
        ly.addWidget(ayuda)

        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["Desde (comisiones al mes)", "Compra con"])
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.verticalHeader().setVisible(False)
        ly.addWidget(self.tabla)
        for n in niveles:
            self._agregar(n.comisiones_minimas, n.porcentaje)

        botones = QHBoxLayout()
        mas = QPushButton("+ Nivel")
        mas.clicked.connect(lambda: self._agregar(self._siguiente_minimo(), Decimal("0")))
        menos = QPushButton("− Quitar el último")
        menos.clicked.connect(self._quitar)
        botones.addWidget(mas)
        botones.addWidget(menos)
        botones.addStretch()
        ly.addLayout(botones)

        tope_ly = QHBoxLayout()
        tope_ly.addWidget(QLabel("Tope al mes con su nivel (precio de lista):"))
        self.tope_input = QDoubleSpinBox()
        self.tope_input.setRange(0, 999999)
        self.tope_input.setDecimals(0)
        self.tope_input.setPrefix("$")
        self.tope_input.setSpecialValueText("Sin tope")
        self.tope_input.setValue(float(tope or 0))
        tope_ly.addWidget(self.tope_input)
        ly.addLayout(tope_ly)
        nota = QLabel(f"Pasando el tope, o en la promo 3pz, compran con el {inc.fmt_pct(inc.PCT_BASE)} de siempre.")
        nota.setWordWrap(True)
        ly.addWidget(nota)

        caja = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        caja.accepted.connect(self._aceptar)
        caja.rejected.connect(self.reject)
        ly.addWidget(caja)

        self.niveles_resultado: list[inc.Nivel] = []
        self.tope_resultado = Decimal("0")

    def _agregar(self, minimo: int, pct) -> None:
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        com = QSpinBox()
        com.setRange(0, 99999)
        com.setValue(int(minimo))
        if fila == 0:
            com.setEnabled(False)  # el primero es el de todas: desde 0
        pct_in = QDoubleSpinBox()
        pct_in.setRange(0, float(inc.PCT_MAXIMO))
        pct_in.setDecimals(1)
        pct_in.setSuffix(" %")
        pct_in.setValue(float(pct))
        self.tabla.setCellWidget(fila, 0, com)
        self.tabla.setCellWidget(fila, 1, pct_in)

    def _siguiente_minimo(self) -> int:
        n = self.tabla.rowCount()
        return int(self.tabla.cellWidget(n - 1, 0).value()) + 100 if n else 0

    def _quitar(self) -> None:
        if self.tabla.rowCount() > 1:
            self.tabla.removeRow(self.tabla.rowCount() - 1)

    def leer(self) -> list[inc.Nivel]:
        return [
            inc.Nivel(
                int(self.tabla.cellWidget(r, 0).value()),
                Decimal(str(self.tabla.cellWidget(r, 1).value())).quantize(Decimal("0.1")),
            )
            for r in range(self.tabla.rowCount())
        ]

    def _aceptar(self) -> None:
        try:
            self.niveles_resultado, self.tope_resultado = inc.validar(self.leer(), self.tope_input.value())
        except inc.NivelesInvalidos as exc:
            QMessageBox.warning(self, "Revisa los niveles", str(exc))
            return
        self.accept()


def abrir_descuento_empleadas(parent) -> bool:
    """Abre el diálogo y guarda. True si se guardó."""
    from pos_uniformes.database.connection import get_session

    try:
        with get_session() as session:
            niveles = inc.niveles(session)
            tope = inc.tope(session)
    except Exception:  # noqa: BLE001
        _logger.warning("Descuento de empleadas: sin conexión", exc_info=True)
        QMessageBox.warning(parent, "Sin conexión", "Se necesita la conexión con la PC principal.")
        return False
    dlg = DescuentoEmpleadasDialog(niveles, tope, parent)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return False
    try:
        with get_session() as session:
            inc.guardar(session, dlg.niveles_resultado, dlg.tope_resultado)
            session.commit()
    except Exception as exc:  # noqa: BLE001
        _logger.exception("Descuento de empleadas: no se pudo guardar")
        QMessageBox.warning(parent, "No se guardó", f"No se pudo guardar: {exc}")
        return False
    return True
