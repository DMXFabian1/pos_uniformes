"""Historial de cortes (solo dueño): Libreta → 🧾 Cortes.

Filtro por mes; cada corte con periodo, quién lo hizo, en caja, reactivo
que quedó, lo que se retiró, pagos y si sobró/faltó (eso solo en pantalla,
nunca en papel). Al seleccionar uno se ve el ticket tal cual y se puede
reimprimir en el formato original (dueño o encargado) o en el otro.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.historial_cortes_service import (
    FORMATO_ENCARGADO,
    diferencia_corte,
    es_del_dueno,
    es_legacy,
    formato_original,
    retirado,
    totales_cortes,
)

logger = logging.getLogger(__name__)

_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
COLUMNAS = ("Fecha", "Hora", "Periodo", "Por", "En caja (real)", "Calculado", "Reactivo", "Se retiró", "Pagos", "Ajuste / Sobró-Faltó", "Nota")
# "En caja" es lo REAL (tu cifra, el dinero que quedó). Lo que calculó el
# sistema y el ajuste van escondidos; Ctrl+Shift+R los asoma.
COLUMNAS_OCULTAS = (5, 9)
ATAJO_MODO_REAL = "Ctrl+Shift+R"


def _item(texto: str, centrado: bool = True, negrita: bool = False) -> QTableWidgetItem:
    it = QTableWidgetItem(texto)
    if centrado:
        it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    if negrita:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    return it


def _hora(corte) -> str:
    momento = corte.hasta or corte.created_at
    if momento is None:
        return ""
    if getattr(momento, "tzinfo", None):
        momento = momento.astimezone()
    return momento.strftime("%H:%M")


def texto_diferencia(corte) -> str:
    """Corte del dueño: 'ajuste ±$' (lo real contra lo calculado). Del encargado: sobró/faltó."""
    d = diferencia_corte(corte)
    if d is None:
        return "—"
    if d == 0:
        return "sin ajuste" if es_del_dueno(corte) else "cuadró ✅"
    if es_del_dueno(corte):
        return f"ajuste {'+' if d > 0 else '−'}${abs(d):,.2f}"
    return f"sobró ${d:,.2f}" if d > 0 else f"faltó ${-d:,.2f}"


def texto_real(corte) -> str:
    return "—" if es_legacy(corte) else f"${Decimal(corte.monto_esperado or 0):,.2f}"


def filas_tabla(cortes: list) -> list[tuple[str, ...]]:
    """Filas de texto para la tabla (puro, testeable)."""
    filas = []
    for c in cortes:
        filas.append((
            c.fecha.strftime("%d/%m/%Y"),
            _hora(c),
            str(c.periodo_label or ""),
            str(c.creado_por or ""),
            f"${Decimal(c.monto_final):,.2f}",
            texto_real(c),
            "—" if es_legacy(c) else f"${Decimal(c.reactivo_final or 0):,.2f}",
            "—" if es_legacy(c) else f"${retirado(c):,.2f}",
            f"${Decimal(c.retiros_pagos or 0):,.2f}",
            texto_diferencia(c),
            str(c.nota or ""),
        ))
    return filas


def venta_congruente(corte, datos) -> Decimal:
    """La venta que cuadra con la cifra real (la del dueño): si ajustó, la
    derivada (cifra − reactivo + pagos + gastos); si no, la de las ventas."""
    from pos_uniformes.ui.dialogs.corte_caja_dialog import _con_ajuste

    if not _con_ajuste(corte):
        return Decimal(datos.venta_efectivo or 0)
    pagos = Decimal(getattr(corte, "retiros_pagos", 0) or 0)
    gastos = Decimal(getattr(corte, "otros_retiros", 0) or 0)
    return (Decimal(corte.monto_final) - Decimal(corte.reactivo_inicial or 0) + pagos + gastos).quantize(Decimal("0.01"))


def texto_ticket_reimpresion(corte, datos, formato: str) -> str:
    """Ticket del corte reconstruido, marcado como reimpresión. Congruente
    con lo que se imprimió: nunca la venta real si hubo ajuste."""
    from pos_uniformes.ui.dialogs.corte_caja_dialog import texto_ticket_corte, texto_ticket_corte_encargado

    if formato == FORMATO_ENCARGADO:
        return texto_ticket_corte_encargado(
            corte, venta_congruente(corte, datos), datos.pagos, datos.por_empleada, retiros=datos.retiros, reimpresion=True,
            tarjeta=getattr(datos, "tarjeta", None), tarjeta_ops=getattr(datos, "tarjeta_ops", None),
        )
    return texto_ticket_corte(
        corte, datos.por_empleada, pagos=datos.pagos, venta_efectivo=datos.venta_efectivo, retiros=datos.retiros, reimpresion=True,
        tarjeta=getattr(datos, "tarjeta", None), tarjeta_ops=getattr(datos, "tarjeta_ops", None),
    )


class HistorialCortesDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, hoy: date | None = None, creado_por: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Cortes anteriores")
        self._hoy = hoy or date.today()
        self._creado_por = str(creado_por or "").strip().upper()
        self._cortes: list = []
        self._datos_cache: dict[tuple[int, bool], object] = {}
        self.resize(1080, 680)

        self.mes_combo = QComboBox()
        y, m = self._hoy.year, self._hoy.month
        for _ in range(12):
            self.mes_combo.addItem(f"{_MESES[m - 1].capitalize()} {y}", (y, m))
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        self.mes_combo.currentIndexChanged.connect(lambda _i: self.recargar())
        self.refresh_button = QPushButton("Actualizar")
        self.refresh_button.clicked.connect(self.recargar)

        filtros = QHBoxLayout()
        filtros.addWidget(QLabel("Mes:"))
        filtros.addWidget(self.mes_combo)
        filtros.addWidget(self.refresh_button)
        filtros.addStretch()

        self.totales_label = QLabel("")
        self.totales_label.setWordWrap(True)
        self.totales_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #73341c;")

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setObjectName("libretaTabla")
        self.tabla.setHorizontalHeaderLabels(list(COLUMNAS))
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.itemSelectionChanged.connect(self._mostrar_seleccionado)
        self._modo_real = False
        for col in COLUMNAS_OCULTAS:
            self.tabla.setColumnHidden(col, True)
        QShortcut(QKeySequence(ATAJO_MODO_REAL), self, activated=self.alternar_modo_real)

        self.previa = QPlainTextEdit()
        self.previa.setReadOnly(True)
        fuente = QFont("Courier New")
        fuente.setStyleHint(QFont.StyleHint.Monospace)
        fuente.setPointSize(11)
        self.previa.setFont(fuente)
        self.previa.setPlaceholderText("Selecciona un corte para ver su ticket.")
        self.previa.setMinimumWidth(360)

        self.formato_check = QCheckBox("Formato del encargado (ticket simple)")
        self.formato_check.toggled.connect(lambda _v: self._mostrar_seleccionado())
        self.reprint_button = QPushButton("🖨 Reimprimir corte")
        self.reprint_button.setObjectName("primaryButton")
        self.reprint_button.setEnabled(False)
        self.reprint_button.clicked.connect(self.reimprimir)

        # Borrar: solo Daniel (VEND-1). Un corte doble o equivocado se quita
        # y el periodo se recompone (ver historial_cortes_service.borrar_corte).
        self.delete_button = QPushButton("🗑 Borrar corte")
        self.delete_button.setObjectName("secondaryButton")
        self.delete_button.setEnabled(False)
        self.delete_button.setVisible(self._creado_por == "VEND-1")
        self.delete_button.clicked.connect(self.borrar)

        derecha = QVBoxLayout()
        derecha.addWidget(QLabel("Ticket:"))
        derecha.addWidget(self.previa, 1)
        derecha.addWidget(self.formato_check)
        derecha.addWidget(self.reprint_button)
        derecha.addWidget(self.delete_button)

        centro = QHBoxLayout()
        centro.addWidget(self.tabla, 3)
        centro.addLayout(derecha, 2)

        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        pie = QHBoxLayout()
        pie.addStretch()
        pie.addWidget(cerrar)

        ly = QVBoxLayout()
        ly.setContentsMargins(16, 14, 16, 14)
        ly.setSpacing(8)
        ly.addLayout(filtros)
        ly.addWidget(self.totales_label)
        ly.addLayout(centro, 1)
        ly.addLayout(pie)
        self.setLayout(ly)
        self.recargar()

    # ----------------------------------------------------------------- datos
    def _rango(self) -> tuple[date, date]:
        from pos_uniformes.services.nomina_service import rango_mes

        y, m = self.mes_combo.currentData()
        return rango_mes(y, m)

    def recargar(self) -> None:
        from pos_uniformes.services.historial_cortes_service import listar_cortes_mes

        desde, hasta = self._rango()
        self._datos_cache.clear()
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                cortes = listar_cortes_mes(session, desde, hasta)
                for c in cortes:
                    session.expunge(c)
        except Exception:  # noqa: BLE001
            logger.exception("Historial de cortes: fallo la consulta")
            cortes = []
            self.totales_label.setText("Sin conexión con la PC principal.")
        self.pintar(cortes)

    def pintar(self, cortes: list) -> None:
        self._cortes = list(cortes)
        self.previa.clear()
        self.reprint_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        filas = filas_tabla(self._cortes)
        self.tabla.setRowCount(len(filas))
        for i, fila in enumerate(filas):
            for j, texto in enumerate(fila):
                self.tabla.setItem(i, j, _item(texto, centrado=j not in (2, 10), negrita=(j == 4)))
        if self._cortes:
            t = totales_cortes(self._cortes)
            self.totales_label.setText(
                f"{t.cortes} corte(s) en el mes · Se retiró: ${t.retirado:,.2f}"
                f" · Pagos a empleadas: ${t.pagos:,.2f} · Otros retiros: ${t.otros_retiros:,.2f}"
            )
        elif not self.totales_label.text().startswith("Sin conexión"):
            self.totales_label.setText("No hay cortes en este mes.")

    def alternar_modo_real(self) -> None:
        """Ctrl+Shift+R: asoma lo que calculó el sistema y el ajuste."""
        self._modo_real = not self._modo_real
        for col in COLUMNAS_OCULTAS:
            self.tabla.setColumnHidden(col, not self._modo_real)
        self.setWindowTitle("Cortes anteriores" + ("  ·  con lo calculado" if self._modo_real else ""))

    def corte_seleccionado(self):
        fila = self.tabla.currentRow()
        if fila < 0 or fila >= len(self._cortes):
            return None
        return self._cortes[fila]

    def _datos(self, corte):
        # El ticket del encargado se queda en la tienda: sin los movimientos
        # privados. La cache va por formato porque el papel cambia.
        para_encargado = self._formato() == FORMATO_ENCARGADO
        clave = (corte.id, para_encargado)
        if clave in self._datos_cache:
            return self._datos_cache[clave]
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.historial_cortes_service import datos_para_reimprimir

        with get_session() as session:
            datos = datos_para_reimprimir(session, corte, para_encargado=para_encargado)
            for p in datos.pagos:
                session.expunge(p)
            for r in datos.retiros:
                session.expunge(r)
        self._datos_cache[clave] = datos
        return datos

    def _formato(self) -> str:
        return FORMATO_ENCARGADO if self.formato_check.isChecked() else "dueno"

    def _mostrar_seleccionado(self) -> None:
        corte = self.corte_seleccionado()
        if corte is None:
            self.previa.clear()
            self.reprint_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            return
        self.delete_button.setEnabled(True)
        if self.sender() is self.tabla:
            # Al cambiar de corte, el formato arranca como salió originalmente.
            self.formato_check.blockSignals(True)
            self.formato_check.setChecked(formato_original(corte) == FORMATO_ENCARGADO)
            self.formato_check.blockSignals(False)
        try:
            texto = texto_ticket_reimpresion(corte, self._datos(corte), self._formato())
        except Exception:  # noqa: BLE001
            logger.exception("Historial de cortes: no se pudo armar el ticket")
            self.previa.setPlainText("No se pudo leer el detalle del corte. Revisa la conexión.")
            self.reprint_button.setEnabled(False)
            return
        self.previa.setPlainText(texto)
        self.reprint_button.setEnabled(True)

    def borrar(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        corte = self.corte_seleccionado()
        if corte is None or self._creado_por != "VEND-1":
            return
        texto = (
            f"¿Borrar el corte del {corte.fecha:%d/%m/%Y} a las {_hora(corte)} "
            f"({str(corte.creado_por or '')}, en caja ${Decimal(corte.monto_final):,.2f})?\n\n"
            "Lo vendido en ese tramo pasa al siguiente corte (o al que está abierto). "
            "Si era el último, el reactivo regresa al que tenía antes. No se puede deshacer."
        )
        if QMessageBox.question(self, "Borrar corte", texto) != QMessageBox.StandardButton.Yes:
            return
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services.historial_cortes_service import borrar_corte

            with get_session() as session:
                resumen = borrar_corte(session, corte.id, creado_por=self._creado_por)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Historial de cortes: no se pudo borrar")
            QMessageBox.warning(self, "No se borró", str(exc) or "Inténtalo otra vez.")
            return
        aviso = "Corte borrado."
        if resumen.get("reactivo_restaurado") is not None:
            aviso += f" Reactivo de vuelta en ${resumen['reactivo_restaurado']:,.2f}."
        self.totales_label.setText(aviso)
        self.recargar()

    def reimprimir(self) -> None:
        corte = self.corte_seleccionado()
        texto = self.previa.toPlainText()
        if corte is None or not texto.strip():
            return
        try:
            from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets

            route_tickets(self, "Corte de caja (reimpresión)", [texto])
        except Exception:  # noqa: BLE001
            logger.exception("Historial de cortes: falló la reimpresión")
