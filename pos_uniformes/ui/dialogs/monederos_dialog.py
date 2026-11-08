"""Administración de monederos de clientes (POS principal, solo ADMIN).

Configuración del cashback, consulta de clientes y sus movimientos, ajustes
manuales con motivo, bloqueo, anulación de ventas que movieron el monedero,
reporte y proceso de vencimientos. Todas las reglas están en
services/monedero_service.py; cada acción vuelve a validar que el usuario
sea ADMIN.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.database.connection import get_session
from pos_uniformes.services import monedero_service as mon

_logger = logging.getLogger(__name__)


def open_monederos_dialog(parent, *, usuario_id: int) -> None:
    dlg = MonederosDialog(parent, usuario_id=usuario_id)
    dlg.exec()


def _item(texto: str, derecha: bool = False) -> QTableWidgetItem:
    it = QTableWidgetItem(texto)
    if derecha:
        it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return it


def _fecha(momento) -> str:
    if momento is None:
        return ""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone().strftime("%d/%m/%Y %H:%M")


class MonederosDialog(QDialog):
    def __init__(self, parent, *, usuario_id: int) -> None:
        super().__init__(parent)
        self.usuario_id = int(usuario_id)
        self.setWindowTitle("Monederos de clientes")
        self.resize(900, 620)
        ly = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._tab_config(), "Configuración")
        tabs.addTab(self._tab_clientes(), "Clientes")
        tabs.addTab(self._tab_anular(), "Anular venta")
        tabs.addTab(self._tab_reporte(), "Reporte")
        ly.addWidget(tabs)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        ly.addWidget(cerrar, alignment=Qt.AlignmentFlag.AlignRight)
        self._cargar_config()

    # ─── Utilidades ──────────────────────────────────────────────────────

    def _ejecutar(self, accion, *, exito: str | None = None):
        """Corre `accion(session)` en una transacción; commit si sale bien."""
        try:
            with get_session() as session:
                try:
                    resultado = accion(session)
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
        except (mon.MonederoError, PermissionError) as exc:
            QMessageBox.warning(self, "Monedero", str(exc))
            return None
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Monederos: operación fallida")
            QMessageBox.critical(self, "Monedero", f"No se pudo completar la operación.\n\n{exc}")
            return None
        if exito:
            QMessageBox.information(self, "Monedero", exito)
        return resultado

    def _leer(self, consulta):
        try:
            with get_session() as session:
                return consulta(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Monedero", f"No se pudo leer la información.\n\n{exc}")
            return None

    # ─── Configuración ───────────────────────────────────────────────────

    def _tab_config(self) -> QWidget:
        w = QWidget()
        ly = QVBoxLayout(w)
        self._config_estado = QLabel("")
        self._config_estado.setWordWrap(True)
        ly.addWidget(self._config_estado)
        form = QFormLayout()
        self._tasa = QDoubleSpinBox()
        self._tasa.setRange(0, 100)
        self._tasa.setDecimals(2)
        self._tasa.setSuffix(" %")
        form.addRow("Cashback sobre lo pagado con dinero:", self._tasa)
        self._habilitado = QCheckBox("Cashback habilitado")
        form.addRow("", self._habilitado)
        self._nota = QLineEdit()
        self._nota.setPlaceholderText("Motivo del cambio (opcional)")
        form.addRow("Nota:", self._nota)
        ly.addLayout(form)
        guardar = QPushButton("Guardar configuración")
        guardar.clicked.connect(self._guardar_config)
        ly.addWidget(guardar, alignment=Qt.AlignmentFlag.AlignLeft)
        reglas = QLabel(
            "Reglas fijas: el cashback se calcula sobre el total final menos lo pagado con monedero, "
            "se trunca al centavo y vence a los 12 meses de acreditado. Un cambio de tasa aplica a "
            "ventas desde ese momento (nunca hacia atrás). Apartados y abonos no generan ni aceptan saldo."
        )
        reglas.setWordWrap(True)
        reglas.setStyleSheet("color: #6b6258;")
        ly.addWidget(reglas)
        ly.addStretch()
        return w

    def _cargar_config(self) -> None:
        def _consulta(session):
            c = mon.config_vigente(session)
            return None if c is None else (Decimal(c.tasa_cashback), bool(c.habilitado), c.vigente_desde)

        datos = self._leer(_consulta)
        if datos is None:
            self._config_estado.setText(
                "⚠️ El cashback NO está configurado: ninguna venta genera saldo hasta que fijes una tasa."
            )
            return
        tasa, habilitado, desde = datos
        self._tasa.setValue(float(tasa))
        self._habilitado.setChecked(habilitado)
        if habilitado:
            self._config_estado.setText(f"Cashback activo: {tasa}% desde {_fecha(desde)}.")
        else:
            self._config_estado.setText(f"⚠️ Cashback deshabilitado (última tasa {tasa}%, {_fecha(desde)}).")

    def _guardar_config(self) -> None:
        tasa = Decimal(str(self._tasa.value())).quantize(Decimal("0.01"))
        habilitado = self._habilitado.isChecked()
        pregunta = (
            f"¿Aplicar {tasa}% de cashback a partir de ahora?" if habilitado
            else "¿Deshabilitar el cashback a partir de ahora?"
        )
        if QMessageBox.question(self, "Monedero", pregunta) != QMessageBox.StandardButton.Yes:
            return
        hecho = self._ejecutar(
            lambda s: mon.guardar_config(
                s, tasa=tasa, habilitado=habilitado, usuario_id=self.usuario_id, nota=self._nota.text()
            ),
            exito="Configuración guardada.",
        )
        if hecho is not None:
            self._nota.clear()
            self._cargar_config()

    # ─── Clientes ────────────────────────────────────────────────────────

    def _tab_clientes(self) -> QWidget:
        w = QWidget()
        ly = QVBoxLayout(w)
        fila = QHBoxLayout()
        self._buscar = QLineEdit()
        self._buscar.setPlaceholderText("Nombre, teléfono o código CLI-…")
        self._buscar.returnPressed.connect(self._buscar_clientes)
        fila.addWidget(self._buscar, 1)
        btn = QPushButton("Buscar")
        btn.clicked.connect(self._buscar_clientes)
        fila.addWidget(btn)
        ly.addLayout(fila)
        self._tabla_clientes = QTableWidget(0, 5)
        self._tabla_clientes.setHorizontalHeaderLabels(["Código", "Nombre", "Saldo disponible", "Próximo a vencer", "Estado"])
        self._tabla_clientes.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tabla_clientes.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._tabla_clientes.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tabla_clientes.verticalHeader().setVisible(False)
        ly.addWidget(self._tabla_clientes, 1)
        acciones = QHBoxLayout()
        for texto, fn in (
            ("Movimientos", self._ver_movimientos),
            ("Ajustar saldo…", self._ajustar),
            ("Bloquear / desbloquear…", self._cambiar_estado),
        ):
            b = QPushButton(texto)
            b.clicked.connect(fn)
            acciones.addWidget(b)
        acciones.addStretch()
        ly.addLayout(acciones)
        return w

    def _buscar_clientes(self) -> None:
        texto = self._buscar.text()

        def _consulta(session):
            filas = []
            for c in mon.buscar_clientes(session, texto, 100):
                r = mon.resumen_cliente(session, c.id)
                filas.append(r)
            return filas

        filas = self._leer(_consulta) or []
        self._clientes = filas
        self._tabla_clientes.setRowCount(len(filas))
        for i, r in enumerate(filas):
            self._tabla_clientes.setItem(i, 0, _item(r.codigo))
            self._tabla_clientes.setItem(i, 1, _item(r.nombre))
            self._tabla_clientes.setItem(i, 2, _item(f"${r.disponible:,.2f}" if r.tiene_monedero else "—", True))
            vence = (
                f"${r.monto_proximo_vencimiento:,.2f} el {_fecha(r.proximo_vencimiento)[:10]}"
                if r.proximo_vencimiento else ""
            )
            self._tabla_clientes.setItem(i, 3, _item(vence))
            self._tabla_clientes.setItem(i, 4, _item(r.estado if r.tiene_monedero else "sin monedero"))

    def _cliente_elegido(self):
        fila = self._tabla_clientes.currentRow()
        clientes = getattr(self, "_clientes", [])
        if fila < 0 or fila >= len(clientes):
            QMessageBox.information(self, "Monedero", "Elige un cliente de la lista.")
            return None
        return clientes[fila]

    def _ver_movimientos(self) -> None:
        r = self._cliente_elegido()
        if r is None:
            return
        from pos_uniformes.ui.helpers.quick_sale_monedero_helper import mostrar_movimientos

        def _consulta(session):
            m = mon.monedero_de_cliente(session, r.cliente_id)
            if m is None:
                return []
            return [
                (f.movimiento.created_at, f"{f.etiqueta} — {f.movimiento.motivo}", Decimal(f.movimiento.monto),
                 f.saldo_contable, f.movimiento.expira_at)
                for f in mon.historial(session, m.id)
            ]

        filas = self._leer(_consulta)
        if filas is not None:
            mostrar_movimientos(self, f"Monedero de {r.nombre} ({r.codigo})", filas)

    def _ajustar(self) -> None:
        r = self._cliente_elegido()
        if r is None:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Ajuste de saldo — {r.nombre}")
        form = QFormLayout(dlg)
        tipo = QCheckBox("En contra (descontar saldo)")
        monto = QLineEdit()
        monto.setPlaceholderText("0.00")
        motivo = QPlainTextEdit()
        motivo.setFixedHeight(70)
        ref = QLineEdit()
        form.addRow("Monto $:", monto)
        form.addRow("", tipo)
        form.addRow("Motivo (obligatorio):", motivo)
        form.addRow("Referencia:", ref)
        botones = QHBoxLayout()
        ok = QPushButton("Aplicar ajuste")
        cancelar = QPushButton("Cancelar")
        ok.clicked.connect(dlg.accept)
        cancelar.clicked.connect(dlg.reject)
        botones.addWidget(ok)
        botones.addWidget(cancelar)
        form.addRow(botones)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            valor = Decimal(monto.text().strip().replace("$", "").replace(",", "")).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            QMessageBox.warning(self, "Monedero", "Monto inválido.")
            return
        if valor <= 0:
            QMessageBox.warning(self, "Monedero", "Escribe un monto mayor a cero; el sentido lo marca la casilla.")
            return
        firmado = -valor if tipo.isChecked() else valor
        texto = "en contra" if firmado < 0 else "a favor"
        if QMessageBox.question(
            self, "Monedero", f"¿Aplicar ajuste {texto} de ${valor:,.2f} a {r.nombre}?"
        ) != QMessageBox.StandardButton.Yes:
            return
        hecho = self._ejecutar(
            lambda s: mon.ajustar(
                s, cliente_id=r.cliente_id, monto=firmado, motivo=motivo.toPlainText(),
                usuario_id=self.usuario_id, referencia=ref.text() or None,
            ),
            exito="Ajuste aplicado.",
        )
        if hecho is not None:
            self._buscar_clientes()

    def _cambiar_estado(self) -> None:
        r = self._cliente_elegido()
        if r is None:
            return
        opciones = [mon.ACTIVO, mon.BLOQUEADO, mon.CERRADO]
        estado, ok = QInputDialog.getItem(self, "Estado del monedero", f"Nuevo estado para {r.nombre}:", opciones,
                                          opciones.index(r.estado) if r.estado in opciones else 0, False)
        if not ok or estado == r.estado:
            return
        motivo, ok = QInputDialog.getText(self, "Estado del monedero", "Motivo (obligatorio):")
        if not ok:
            return
        hecho = self._ejecutar(
            lambda s: mon.cambiar_estado(s, cliente_id=r.cliente_id, estado=estado, motivo=motivo,
                                         usuario_id=self.usuario_id),
            exito=f"Monedero {estado}.",
        )
        if hecho is not None:
            self._buscar_clientes()

    # ─── Anular venta ────────────────────────────────────────────────────

    def _tab_anular(self) -> QWidget:
        w = QWidget()
        ly = QVBoxLayout(w)
        explica = QLabel(
            "Para ventas de la Libreta que movieron el monedero (cashback o pago con saldo). "
            "Se anula COMPLETA: se revierte el cashback, se devuelve el saldo usado con su vencimiento "
            "original, se regresa el stock y se quita de la Libreta. Si el cliente ya gastó el cashback "
            "de esta venta no se puede anular sin antes hacer un ajuste."
        )
        explica.setWordWrap(True)
        ly.addWidget(explica)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Núm. de operación de la Libreta:"))
        self._op_id = QSpinBox()
        self._op_id.setRange(1, 2_000_000_000)
        fila.addWidget(self._op_id)
        ver = QPushButton("Ver")
        ver.clicked.connect(self._ver_operacion)
        fila.addWidget(ver)
        fila.addStretch()
        ly.addLayout(fila)
        self._op_detalle = QLabel("")
        self._op_detalle.setWordWrap(True)
        self._op_detalle.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ly.addWidget(self._op_detalle)
        self._btn_anular = QPushButton("Anular venta…")
        self._btn_anular.setEnabled(False)
        self._btn_anular.clicked.connect(self._anular)
        ly.addWidget(self._btn_anular, alignment=Qt.AlignmentFlag.AlignLeft)
        ly.addStretch()
        return w

    def _ver_operacion(self) -> None:
        from pos_uniformes.database.models import Cliente, LibretaVenta

        op_id = int(self._op_id.value())

        def _consulta(session):
            v = session.get(LibretaVenta, op_id)
            if v is None:
                return None
            cliente = session.get(Cliente, v.cliente_id) if v.cliente_id else None
            movs = [(m.tipo, Decimal(m.monto)) for m in mon.movimientos_de_operacion(session, v.id)]
            return (v.tipo, Decimal(v.monto_total), Decimal(v.monto_monedero or 0), v.created_at,
                    v.employee_name or v.employee_code, cliente.nombre if cliente else "—", movs)

        datos = self._leer(_consulta)
        if not datos:
            self._op_detalle.setText("No existe esa operación.")
            self._btn_anular.setEnabled(False)
            return
        tipo, total, monedero, cuando, empleada, cliente, movs = datos
        lineas = [
            f"<b>{tipo.capitalize()} #{op_id}</b> · {_fecha(cuando)} · {empleada}",
            f"Cliente: {cliente} · Total ${total:,.2f} · Pagado con monedero ${monedero:,.2f}",
        ]
        if movs:
            lineas.append("Movimientos: " + ", ".join(
                f"{mon.ETIQUETAS_TIPO.get(t, t)} {'+' if m > 0 else '-'}${abs(m):,.2f}" for t, m in movs))
        else:
            lineas.append("Esta operación no movió el monedero: se borra desde la Libreta, como siempre.")
        self._op_detalle.setText("<br>".join(lineas))
        self._btn_anular.setEnabled(bool(movs))

    def _anular(self) -> None:
        from pos_uniformes.services.libreta_service import anular_operacion_con_monedero

        op_id = int(self._op_id.value())
        motivo, ok = QInputDialog.getText(self, "Anular venta", f"Motivo de la anulación de la operación #{op_id}:")
        if not ok:
            return
        if QMessageBox.question(
            self, "Anular venta", f"¿Anular COMPLETA la operación #{op_id}? No se puede deshacer."
        ) != QMessageBox.StandardButton.Yes:
            return
        r = self._ejecutar(
            lambda s: anular_operacion_con_monedero(s, op_id, usuario_id=self.usuario_id, motivo=motivo)
        )
        if r is None:
            return
        QMessageBox.information(
            self, "Anular venta",
            f"Operación #{op_id} anulada.\nCashback revertido: ${r.cashback_revertido:,.2f}\n"
            f"Saldo devuelto al cliente: ${r.saldo_devuelto:,.2f}",
        )
        self._op_detalle.setText("")
        self._btn_anular.setEnabled(False)

    # ─── Reporte ─────────────────────────────────────────────────────────

    def _tab_reporte(self) -> QWidget:
        w = QWidget()
        ly = QVBoxLayout(w)
        fila = QHBoxLayout()
        hoy = QDate.currentDate()
        self._desde = QDateEdit(hoy.addDays(-30))
        self._hasta = QDateEdit(hoy)
        for d in (self._desde, self._hasta):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd/MM/yyyy")
        fila.addWidget(QLabel("Desde"))
        fila.addWidget(self._desde)
        fila.addWidget(QLabel("Hasta"))
        fila.addWidget(self._hasta)
        gen = QPushButton("Generar")
        gen.clicked.connect(self._generar_reporte)
        fila.addWidget(gen)
        fila.addStretch()
        venc = QPushButton("Procesar vencimientos ahora")
        venc.clicked.connect(self._procesar_vencimientos)
        fila.addWidget(venc)
        ly.addLayout(fila)
        self._reporte = QPlainTextEdit()
        self._reporte.setReadOnly(True)
        self._reporte.setStyleSheet("font-family: Menlo, Consolas, monospace; font-size: 12px;")
        ly.addWidget(self._reporte, 1)
        return w

    def _generar_reporte(self) -> None:
        local = datetime.now().astimezone().tzinfo
        desde = datetime.combine(self._desde.date().toPyDate(), time.min, tzinfo=local)
        hasta = datetime.combine(self._hasta.date().toPyDate(), time.min, tzinfo=local) + timedelta(days=1)

        def _consulta(session):
            r = mon.reporte(session, desde, hasta)
            ajustes = [
                (_fecha(a.created_at), Decimal(a.monto), a.motivo, a.usuario_id) for a in r.ajustes
            ]
            return r, ajustes

        datos = self._leer(_consulta)
        if datos is None:
            return
        r, ajustes = datos
        n = r.operaciones_por_tipo
        lineas = [
            f"Periodo: {desde:%d/%m/%Y} – {(hasta - timedelta(days=1)):%d/%m/%Y}",
            "",
            f"Cashback generado      ${r.cashback_generado:>12,.2f}   ({n.get(mon.CASHBACK, 0)} movs)",
            f"Saldo utilizado (neto) ${r.saldo_utilizado:>12,.2f}   ({n.get(mon.CANJE, 0)} canjes)",
            f"Cashback revertido     ${r.reversiones:>12,.2f}",
            f"Saldo expirado         ${r.expirado:>12,.2f}",
            f"Ajustes a favor        ${r.por_tipo.get(mon.AJUSTE_ABONO, Decimal(0)):>12,.2f}",
            f"Ajustes en contra      ${-r.por_tipo.get(mon.AJUSTE_CARGO, Decimal(0)):>12,.2f}",
            "",
            f"Saldo vigente hoy (pasivo)        ${r.saldo_vigente_total:>12,.2f}",
            f"Vence en los próximos {r.dias_proximo} días     ${r.proximo_a_vencer:>12,.2f}",
            f"Clientes con monedero             {r.clientes_con_monedero:>13,}",
        ]
        if ajustes:
            lineas += ["", "Ajustes manuales:"]
            lineas += [f"  {f}  {'+' if m > 0 else '-'}${abs(m):,.2f}  usuario {u}  {mot}" for f, m, mot, u in ajustes]
        self._reporte.setPlainText("\n".join(lineas))

    def _procesar_vencimientos(self) -> None:
        n = self._ejecutar(lambda s: mon.procesar_vencimientos(s))
        if n is not None:
            QMessageBox.information(self, "Monedero", f"Vencimientos asentados: {n}.")
