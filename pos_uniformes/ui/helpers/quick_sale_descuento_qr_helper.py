"""QR de descuento de temporada en la venta (Daniel, 2026-11-16).

El campo de escaneo reconoce «DSCT-…», lo valida con los candados de
`descuento_qr_service` y abre un diálogo con tres botones grandes: 5 % ·
10 % · 15 %. El % elegido entra al motor (`descuento_qr_pct`); el motor
decide a qué líneas toca. Un chip «Descuento QR 10 %  ✕» en el total lo
quita; al terminar o cancelar la venta se limpia solo.

Nunca se muestra ni se anota el código escaneado.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout

from pos_uniformes.services import descuento_qr_service as dqr

_logger = logging.getLogger(__name__)

_TITULO = "QR de descuento"


class DescuentoQrMixin:
    """Se mezcla en QuickSaleWidget. Usa de él: satellite, _employee_code,
    _items, _en_linea, _poner_categorias, _calculo_motor, _refresh_totals,
    _calculo_fijo, _pct_descuento_programa, _etiqueta_descuento_ticket."""

    #: El % elegido para ESTA venta (None = sin QR).
    _descuento_qr_pct: Decimal | None = None

    # ─── Escaneo ─────────────────────────────────────────────────────────

    @staticmethod
    def _es_qr_descuento(raw: str) -> bool:
        return dqr.es_qr_descuento(raw)

    def _hay_conexion_qr(self) -> bool:
        if getattr(getattr(self, "satellite", None), "offline_mode", False):
            return False
        return bool(self._en_linea())

    def _on_qr_descuento(self, raw: str) -> None:
        """Valida el QR y, si es bueno, pregunta el %. El texto escaneado no
        sale de aquí: ni a la pantalla ni al log."""
        aviso = dqr.rechazo_previo(
            hay_empleada=bool(getattr(self, "_employee_code", None)),
            en_linea=self._hay_conexion_qr(),
        )
        if aviso:
            QMessageBox.warning(self, _TITULO, aviso)
            return
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                resultado = dqr.validar_codigo(session, raw)
        except Exception as exc:  # noqa: BLE001 — sin la base no se puede validar
            # Solo el tipo de error: el texto podría traer el código.
            _logger.warning("QR de descuento: no se pudo validar (%s)", type(exc).__name__)
            QMessageBox.warning(self, _TITULO, dqr.TXT_SIN_CONEXION)
            return
        if resultado == dqr.CODIGO_CONOCIDO:
            QMessageBox.warning(self, _TITULO, dqr.TXT_CODIGO_CONOCIDO)
            return
        if resultado != dqr.VALIDO:
            bloqueado = dqr.CONTADOR.fallo()
            texto = dqr.texto_bloqueado(dqr.CONTADOR.segundos_bloqueado()) if bloqueado else dqr.TXT_NO_VALIDO
            QMessageBox.warning(self, _TITULO, texto)
            return
        dqr.CONTADOR.exito()
        pct = self._elegir_pct_descuento_qr()
        if pct is None:
            return
        self._descuento_qr_pct = pct
        self._refresh_totals()

    def _base_ropa_normal(self) -> Decimal:
        try:
            self._poner_categorias(self._items)
        except Exception:  # noqa: BLE001
            _logger.warning("QR de descuento: no se pudieron leer las categorías", exc_info=True)
        return dqr.base_elegible(self._items)

    def _elegir_pct_descuento_qr(self) -> Decimal | None:
        dlg = self._dialogo_pct_descuento_qr(dqr.opciones(self._base_ropa_normal()))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return getattr(dlg, "pct_elegido", None)

    def _dialogo_pct_descuento_qr(self, opciones: list) -> QDialog:
        """Tres botones grandes; el 15 % deshabilitado dice por qué."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Descuento de temporada")
        dlg.pct_elegido = None
        ly = QVBoxLayout(dlg)
        ly.setContentsMargins(24, 20, 24, 20)
        ly.setSpacing(12)
        titulo = QLabel("¿Cuánto descuento? Solo aplica a la ropa normal (no uniformes ni ofertas).")
        titulo.setWordWrap(True)
        titulo.setStyleSheet("font-size: 15px; font-weight: 600;")
        ly.addWidget(titulo)
        dlg.botones = []
        for opcion in opciones:
            boton = QPushButton(opcion.texto)
            boton.setMinimumHeight(64)
            boton.setAutoDefault(False)
            boton.setStyleSheet("QPushButton { font-size: 24px; font-weight: 800; border-radius: 12px; }")
            boton.setEnabled(opcion.habilitada)

            def _elegir(_c=False, pct=opcion.pct) -> None:
                dlg.pct_elegido = pct
                dlg.accept()

            boton.clicked.connect(_elegir)
            ly.addWidget(boton)
            dlg.botones.append(boton)
            if not opcion.habilitada and opcion.razon:
                razon = QLabel(opcion.razon)
                razon.setWordWrap(True)
                razon.setStyleSheet("color: #8a1f11; font-size: 13px;")
                ly.addWidget(razon)
        cancelar = QPushButton("Cancelar")
        cancelar.setAutoDefault(False)
        cancelar.clicked.connect(dlg.reject)
        ly.addWidget(cancelar)
        return dlg

    # ─── Chip para quitarlo ──────────────────────────────────────────────

    def _build_chip_descuento_qr(self) -> QPushButton:
        chip = QPushButton("")
        chip.setObjectName("chipDescuentoQr")
        chip.setAutoDefault(False)
        chip.setToolTip("Quitar el descuento del QR de esta venta")
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        chip.setStyleSheet(
            "QPushButton#chipDescuentoQr { background: #fff4d6; color: #6b4a00;"
            "  border: 1.5px solid #e0a800; border-radius: 12px; padding: 6px 12px;"
            "  font-size: 13px; font-weight: 700; text-align: left; }"
        )
        chip.clicked.connect(self._quitar_descuento_qr)
        chip.setVisible(False)
        self._chip_descuento_qr = chip
        return chip

    def _quitar_descuento_qr(self) -> None:
        self._descuento_qr_pct = None
        self._refresh_totals()

    def _limpiar_descuento_qr(self) -> None:
        """Al terminar o cancelar la venta: la siguiente no hereda el QR."""
        self._descuento_qr_pct = None

    def _calculo_qr_actual(self):
        if self._descuento_qr_pct is None or not getattr(self, "_items", None):
            return None
        try:
            return self._calculo_motor()
        except Exception:  # noqa: BLE001 — el chip no detiene la venta
            return None

    def _pintar_chip_descuento_qr(self) -> None:
        chip = getattr(self, "_chip_descuento_qr", None)
        if chip is None:
            return
        if self._descuento_qr_pct is None:
            chip.setVisible(False)
            return
        chip.setText(dqr.texto_chip(self._descuento_qr_pct, self._calculo_qr_actual()))
        chip.setVisible(True)

    # ─── Ticket y pantalla ───────────────────────────────────────────────

    def _qr_del_ticket(self) -> tuple[Decimal, Decimal] | None:
        """(% aplicado, importe) del QR para el ticket, o None."""
        fijo = getattr(self, "_calculo_fijo", None)
        if fijo is not None:
            pct, importe = getattr(fijo, "qr_pct", None), getattr(fijo, "qr_importe", None)
        else:
            calculo = self._calculo_qr_actual()
            info = getattr(calculo, "descuento_qr", None)
            pct, importe = (info.pct, info.importe) if info is not None else (None, None)
        if not pct or not importe or importe <= 0:
            return None
        return Decimal(str(pct)), Decimal(str(importe))

    def _renglones_descuento_ticket(self, descuento: Decimal) -> list[tuple[str, Decimal]]:
        """«Descuento autorizado N %» por lo que puso el QR; lo demás con su
        etiqueta de siempre."""
        qr = self._qr_del_ticket()
        if qr is None:
            return [(self._etiqueta_descuento_ticket(), descuento)]
        pct, importe = qr
        importe = min(importe, descuento)
        filas = [(f"Descuento autorizado {dqr.texto_pct(pct)}:", importe)]
        resto = (descuento - importe).quantize(Decimal("0.01"))
        if resto > 0:
            filas.append((self._etiqueta_descuento_ticket(), resto))
        return filas

    def _ahorro_extra_ticket(self, descuento: Decimal) -> Decimal:
        """Lo que cuenta en «lo ahorrado» además de las ofertas: el QR y el
        mayoreo (el de empleada no se cuenta)."""
        qr = self._qr_del_ticket()
        del_qr = min(qr[1], descuento) if qr else Decimal("0")
        resto = descuento - del_qr
        mayoreo = resto if (resto > 0 and self._pct_descuento_programa()) else Decimal("0")
        return del_qr + mayoreo

    def _nombre_descuento_qr_pantalla(self) -> str | None:
        qr = self._qr_del_ticket()
        return f"Descuento QR {dqr.texto_pct(qr[0])}" if qr else None
