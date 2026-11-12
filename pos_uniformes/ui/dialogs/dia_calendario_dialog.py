"""Detalle de un día del calendario del kiosko (al tocar una celda).

Arriba: quién descansa, quién faltó, a quién le toca pago y qué conteos
caen ese día.
Abajo: "¿Cuánto llevas?" — se escanea el gafete. La empleada ve SOLO su
pago pendiente con desglose; el dueño (VEND-1) o el encargado (ENC-1) ven el de
todas. Lo mostrado se borra solo a los 45 s (es una pantalla compartida).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from decimal import Decimal

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.dia_calendario_service import DIAS_ES, MESES_ES, fecha_en_palabras, lineas_pago

logger = logging.getLogger(__name__)

SEGUNDOS_VISIBLE = 45
_MUTED = "#8a7358"
# Estilo moderno, igual que la caja y el calendario (Daniel, 2026-11-12).
_STYLES = (
    "QDialog { background: #f6f0e8; }"
    "QLabel { color: #2c2118; background: transparent; }"
    "#diaHoy { background: #e8692f; color: white; border-radius: 12px; padding: 0 10px;"
    "  min-height: 24px; font-size: 12px; font-weight: 800; }"
    "#diaTitulo { font-size: 26px; font-weight: 900; color: #2c2118; }"
    "#tarjeta { background: #ffffff; border: 1px solid #efe6db; border-radius: 18px; }"
    "#tarjetaTitulo { font-size: 11px; font-weight: 800; color: #a08c76; letter-spacing: 1.2px; }"
    "#tarjetaTexto { font-size: 16px; font-weight: 800; color: #2c2118; }"
    "#tarjetaTexto[vacio=\"true\"] { color: #c2b4a4; font-weight: 600; }"
    "#pagoTitulo { font-size: 16px; font-weight: 800; color: #2c2118; }"
    "#pagoSub { font-size: 13px; color: #8a7a68; }"
    "#pagoLinea { font-size: 15px; color: #3d2e22; }"
    "#pagoTotal { font-size: 24px; font-weight: 900; color: #6b1f3a; }"
    "#pagoError { font-size: 13px; font-weight: 700; color: #b0341f; }"
    "QLineEdit { background: #faf6f0; color: #2c2118; border: 1.5px solid #ece2d6;"
    "  border-radius: 14px; min-height: 48px; padding: 0 16px; font-size: 16px; }"
    "QLineEdit:focus { border-color: #6b1f3a; background: #ffffff; }"
    "#cerrarBtn { background: #6b1f3a; color: #ffffff; border: none; border-radius: 16px;"
    "  min-height: 52px; font-size: 16px; font-weight: 800; }"
    "#cerrarBtn:pressed { background: #561730; }"
    "#ocultarBtn { background: #ffffff; color: #5c4d40; border: 1px solid #ece2d6;"
    "  border-radius: 14px; min-height: 44px; font-size: 14px; font-weight: 700; padding: 0 16px; }"
    "QTableWidget#tablaPagos { background: #ffffff; border: none; font-size: 14px; color: #2c2118;"
    "  alternate-background-color: #faf6f0; gridline-color: transparent; }"
    "QTableWidget#tablaPagos QHeaderView::section { background: transparent; color: #a08c76; border: none;"
    "  border-bottom: 1px solid #ece2d6; font-size: 11px; font-weight: 800; padding: 6px; }"
)

# Cada tarjeta con su color y su emoji (más alegre, Daniel 2026-11-12):
# los mismos del calendario.
_COLORES = {
    "DESCANSA": ("#ebe3ff", "#5130a3"),
    "FALTÓ": ("#ffe0db", "#b02a17"),
    "DÍA DE PAGO": ("#d9f5e3", "#1b7341"),
    "CONTEOS": ("#ffe9cc", "#9a4a00"),
}


def _sombra(widget) -> None:
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect

    efecto = QGraphicsDropShadowEffect(widget)
    efecto.setBlurRadius(26)
    efecto.setOffset(0, 4)
    efecto.setColor(QColor(90, 40, 30, 26))
    widget.setGraphicsEffect(efecto)


def _tarjeta(titulo: str, texto: str) -> QFrame:
    caja = QFrame()
    caja.setObjectName("tarjetaColor")
    limpio = titulo.split("  ", 1)[-1].strip()
    fondo, tinta = _COLORES.get(limpio, ("#ffffff", "#5c4d40"))
    caja.setStyleSheet(f"QFrame#tarjetaColor {{ background: {fondo}; border: none; border-radius: 18px; }}")
    ly = QVBoxLayout(caja)
    ly.setContentsMargins(16, 14, 16, 16)
    ly.setSpacing(6)
    t = QLabel(titulo)
    t.setObjectName("tarjetaTitulo")
    t.setStyleSheet(f"color: {tinta};")
    ly.addWidget(t)
    x = QLabel(texto)
    x.setObjectName("tarjetaTexto")
    vacio = texto in ("Nadie", "Ninguno")
    x.setStyleSheet(f"color: {tinta};" + (" font-weight: 600;" if vacio else ""))
    if vacio:
        efecto_opaco(x)
    x.setWordWrap(True)
    ly.addWidget(x)
    ly.addStretch(1)
    return caja


def efecto_opaco(label: QLabel) -> None:
    from PyQt6.QtWidgets import QGraphicsOpacityEffect

    e = QGraphicsOpacityEffect(label)
    e.setOpacity(0.45)
    label.setGraphicsEffect(e)


def texto_conteos(conteos: list) -> str:
    if not conteos:
        return "Ninguno"
    partes = []
    for e in conteos:
        marca = " (vencido)" if getattr(e, "vencida", False) else ""
        partes.append(f"{e.escuela_nombre}{marca}")
    return ", ".join(partes)


class DiaCalendarioDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        fecha: date,
        *,
        session_factory: Callable[[], object] | None = None,
        hoy: date | None = None,
    ) -> None:
        super().__init__(parent)
        self._fecha = fecha
        self._hoy = hoy or date.today()
        self._session_factory = session_factory
        self.setWindowTitle(fecha_en_palabras(fecha))
        self.setMinimumWidth(720)
        self.setStyleSheet(_STYLES)

        ly = QVBoxLayout(self)
        ly.setContentsMargins(26, 22, 26, 22)
        ly.setSpacing(16)

        cabeza = QHBoxLayout()
        cabeza.setSpacing(10)
        titulo = QLabel("📅  " + fecha_en_palabras(fecha))
        titulo.setObjectName("diaTitulo")
        cabeza.addWidget(titulo)
        if fecha == self._hoy:
            hoy = QLabel("HOY")
            hoy.setObjectName("diaHoy")
            cabeza.addWidget(hoy, 0, Qt.AlignmentFlag.AlignVCenter)
        cabeza.addStretch(1)
        ly.addLayout(cabeza)

        resumen = self._cargar_resumen()
        fila = QHBoxLayout()
        fila.setSpacing(10)
        self.tarjeta_descansan = _tarjeta("🛌  DESCANSA", ", ".join(resumen.descansan) or "Nadie")
        self.tarjeta_faltas = _tarjeta("❌  FALTÓ", ", ".join(resumen.faltas) or "Nadie")
        self.tarjeta_pagos = _tarjeta("💵  DÍA DE PAGO", ", ".join(resumen.pagos) or "Nadie")
        self.tarjeta_conteos = _tarjeta("📋  CONTEOS", texto_conteos(resumen.conteos))
        for c in (
            self.tarjeta_descansan,
            self.tarjeta_faltas,
            self.tarjeta_pagos,
            self.tarjeta_conteos,
        ):
            fila.addWidget(c, 1)
        ly.addLayout(fila)

        # ── Consulta de pago con gafete ──────────────────────────────────
        gafete = QFrame()
        gafete.setObjectName("tarjeta")
        _sombra(gafete)
        g_ly = QVBoxLayout(gafete)
        g_ly.setContentsMargins(18, 16, 18, 18)
        g_ly.setSpacing(8)
        pago_titulo = QLabel("💰  ¿Cuánto llevas?")
        pago_titulo.setObjectName("pagoTitulo")
        g_ly.addWidget(pago_titulo)
        pago_sub = QLabel(
            "Escanea tu gafete para ver tu pago." if fecha == self._hoy
            else "Escanea tu gafete para ver lo de ese día y lo que llevas hoy."
        )
        pago_sub.setObjectName("pagoSub")
        g_ly.addWidget(pago_sub)
        self.scan_input = QLineEdit()
        self.scan_input.setPlaceholderText("Escanea tu gafete…")
        self.scan_input.returnPressed.connect(self._on_scan)
        g_ly.addWidget(self.scan_input)

        self.error_label = QLabel("")
        self.error_label.setObjectName("pagoError")
        self.error_label.setVisible(False)
        g_ly.addWidget(self.error_label)

        self.pago_box = QFrame()
        self.pago_ly = QVBoxLayout(self.pago_box)
        self.pago_ly.setContentsMargins(0, 8, 0, 0)
        self.pago_ly.setSpacing(4)
        self.pago_box.setVisible(False)
        g_ly.addWidget(self.pago_box)
        ly.addWidget(gafete)

        self._timer_ocultar = QTimer(self)
        self._timer_ocultar.setSingleShot(True)
        self._timer_ocultar.timeout.connect(self.ocultar_pago)

        pie = QHBoxLayout()
        self.ocultar_btn = QPushButton("Ocultar pago")
        self.ocultar_btn.setObjectName("ocultarBtn")
        self.ocultar_btn.setAutoDefault(False)
        self.ocultar_btn.clicked.connect(self.ocultar_pago)
        self.ocultar_btn.setVisible(False)
        pie.addWidget(self.ocultar_btn)
        pie.addStretch()
        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("cerrarBtn")
        cerrar.setAutoDefault(False)
        cerrar.setMinimumWidth(180)
        cerrar.clicked.connect(self.accept)
        pie.addWidget(cerrar)
        ly.addLayout(pie)

        QTimer.singleShot(0, self.scan_input.setFocus)

    # ── datos ────────────────────────────────────────────────────────────
    def _sesion(self):
        if self._session_factory is not None:
            return self._session_factory()
        from pos_uniformes.database.connection import get_session

        return get_session()

    def _cargar_resumen(self):
        from pos_uniformes.services.dia_calendario_service import ResumenDia, resumen_dia

        try:
            session = self._sesion()
            try:
                return resumen_dia(session, self._fecha, self._hoy)
            finally:
                session.close()
        except Exception:  # noqa: BLE001 — sin conexión: tarjetas vacías
            logger.exception("Detalle del día: no se pudo cargar")
            return ResumenDia(fecha=self._fecha)

    def _consultar_pagos(self, raw: str):
        from pos_uniformes.services.dia_calendario_service import lineas_de_ese_dia, vista_de_pagos

        session = self._sesion()
        try:
            vista = vista_de_pagos(session, raw, self._hoy)
            # Lo de ESE día va en la misma consulta (misma sesión, mismo gafete).
            self._de_ese_dia = (
                lineas_de_ese_dia(session, vista, self._fecha, self._hoy) if vista is not None else []
            )
            return vista
        finally:
            session.close()

    # ── gafete ───────────────────────────────────────────────────────────
    def _on_scan(self) -> None:
        raw = self.scan_input.text()
        self.scan_input.clear()
        if not raw.strip():
            return
        try:
            vista = self._consultar_pagos(raw)
        except Exception:  # noqa: BLE001
            logger.exception("Detalle del día: no se pudo consultar el pago")
            self._error("No hay conexión con la PC principal. Inténtalo otra vez.")
            return
        if vista is None:
            self._error("Ese código no es un gafete activo.")
            return
        self.mostrar_pagos(vista)

    def _error(self, texto: str) -> None:
        self.error_label.setText(texto)
        self.error_label.setVisible(True)
        self.scan_input.setFocus()

    def _limpiar_pago_box(self) -> None:
        while self.pago_ly.count():
            item = self.pago_ly.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)  # desaparece ya, no hasta el siguiente ciclo
                w.deleteLater()

    def _pintar_ese_dia(self, vista) -> None:
        """Arriba de «lo que llevas hoy»: lo que pasó o viene el día que se tocó."""
        de_ese_dia = [(n, ls) for n, ls in getattr(self, "_de_ese_dia", []) if ls]
        if not de_ese_dia:
            return
        if self._fecha == self._hoy:
            cuando = "Hoy"
        else:
            cuando = f"El {DIAS_ES[self._fecha.weekday()]} {self._fecha.day} de {MESES_ES[self._fecha.month - 1]}"
        enc = QLabel(cuando)
        enc.setObjectName("pagoTitulo")
        self.pago_ly.addWidget(enc)
        for nombre, lineas in de_ese_dia:
            texto = "\n".join(lineas)
            if vista.todas:
                texto = f"{nombre}: " + texto.replace("\n", "\n      ")
            lab = QLabel(texto)
            lab.setObjectName("pagoLinea")
            lab.setWordWrap(True)
            lab.setTextFormat(Qt.TextFormat.PlainText)
            self.pago_ly.addWidget(lab)
        self.ese_dia_texto = "\n".join(f"{n}: " + " | ".join(ls) for n, ls in de_ese_dia)   # para las pruebas

    def mostrar_pagos(self, vista) -> None:
        self.error_label.setVisible(False)
        self._limpiar_pago_box()
        self._pintar_ese_dia(vista)
        if vista.todas:
            enc = QLabel(f"Pagos pendientes de todas (gafete de {vista.quien})")
            enc.setObjectName("pagoTitulo")
            self.pago_ly.addWidget(enc)
            self.pago_ly.addWidget(self._tabla_todas(vista.pagos))
        else:
            p = vista.pagos[0]
            enc = QLabel(f"{p.employee_name}")
            enc.setObjectName("pagoTitulo")
            self.pago_ly.addWidget(enc)
            for linea in lineas_pago(p, self._hoy):
                lab = QLabel(linea)
                lab.setObjectName("pagoTotal" if linea.startswith("TOTAL") else "pagoLinea")
                lab.setWordWrap(True)
                self.pago_ly.addWidget(lab)
        self.pago_box.setVisible(True)
        self.ocultar_btn.setVisible(True)
        self._timer_ocultar.start(SEGUNDOS_VISIBLE * 1000)
        self.scan_input.setFocus()

    def _tabla_todas(self, pagos: list) -> QTableWidget:
        cols = ("Empleada", "Base", "Comisiones", "Faltas", "Total hoy", "Le toca")
        tabla = QTableWidget(len(pagos), len(cols))
        tabla.setObjectName("tablaPagos")
        tabla.setHorizontalHeaderLabels(list(cols))
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabla.verticalHeader().setVisible(False)
        tabla.setAlternatingRowColors(True)
        tabla.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        for i, p in enumerate(pagos):
            d = p.detalle
            base = (
                f"{d.dias_trabajados} d × ${Decimal(d.tarifa_dia):,.2f}" if getattr(d, "por_dia", False)
                else f"${Decimal(d.sueldo_base):,.2f}"
            )
            toca = "—" if p.proximo_pago is None else (
                "hoy" if p.proximo_pago == self._hoy else p.proximo_pago.strftime("%d/%m")
                + (" ⚠️" if p.proximo_pago < self._hoy else "")
            )
            valores = (
                p.employee_name.split()[0] if p.employee_name else p.employee_code,
                base,
                f"{d.comisiones} (${Decimal(d.monto_comisiones):,.2f})",
                f"{d.faltas} (−${Decimal(d.descuento_faltas):,.2f})" if int(d.faltas or 0) else "0",
                f"${Decimal(d.total):,.2f}",
                toca,
            )
            for j, v in enumerate(valores):
                it = QTableWidgetItem(v)
                if j:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 4:
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                tabla.setItem(i, j, it)
        alto = tabla.horizontalHeader().height() + 2 * tabla.frameWidth()
        for fila in range(tabla.rowCount()):
            alto += tabla.rowHeight(fila)
        tabla.setFixedHeight(min(max(alto + 6, 60), 320))
        return tabla

    def ocultar_pago(self) -> None:
        self._timer_ocultar.stop()
        self._limpiar_pago_box()
        self.pago_box.setVisible(False)
        self.ocultar_btn.setVisible(False)
        self.scan_input.setFocus()

    def done(self, r: int) -> None:  # noqa: N802 (API de Qt)
        self._timer_ocultar.stop()
        super().done(r)
