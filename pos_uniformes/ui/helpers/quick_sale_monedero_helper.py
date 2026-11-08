"""Monedero en Venta rápida: identificar al cliente, ver su saldo, usarlo y
mostrar el cashback.

Las reglas viven en services/monedero_service.py; aquí solo hay pantalla.

- Se identifica escaneando el QR del cliente (`CLI-…`) en el mismo campo de
  los productos, o buscándolo por nombre/teléfono con «👛 Cliente».
- Buscarlo por nombre liga la venta (gana cashback) y deja consultar, pero
  para USAR saldo hay que escanear su QR.
- Usar saldo exige conexión: la venta se confirma en línea en una sola
  transacción ANTES de imprimir. Sin conexión no hay canje, ni con
  autorización.
- Sin usar saldo la venta sigue por la cola local de siempre; el cashback se
  acredita al subir (si se escaneó sin red, queda «pendiente»).
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

_logger = logging.getLogger(__name__)

_CERO = Decimal("0.00")
_RE_QR_CLIENTE = re.compile(r"CLI-[A-Z0-9]+")


def lineas_ticket_monedero(info: dict, tk_row) -> list[str]:
    """Renglones del monedero bajo el total del ticket.

    info: canje, por_cobrar, metodo, cashback, cashback_pendiente, saldo."""
    lineas: list[str] = []
    canje = Decimal(str(info.get("canje") or 0))
    if canje > 0:
        lineas.append(tk_row("Pagado con monedero:", f"-${canje:,.2f}"))
        metodo = info.get("metodo") or "Efectivo"
        lineas.append(tk_row(f"{metodo}:", f"${Decimal(str(info.get('por_cobrar') or 0)):,.2f}"))
    cashback = Decimal(str(info.get("cashback") or 0))
    if cashback > 0:
        if info.get("cashback_pendiente"):
            lineas.append(tk_row("Cashback (al sincronizar):", f"${cashback:,.2f}"))
        else:
            lineas.append(tk_row("Cashback ganado:", f"${cashback:,.2f}"))
    if info.get("saldo") is not None:
        lineas.append(tk_row("Saldo en monedero:", f"${Decimal(str(info['saldo'])):,.2f}"))
    return lineas


def _es_error_de_red(exc: BaseException) -> bool:
    from sqlalchemy import exc as sa_exc

    return isinstance(exc, (sa_exc.OperationalError, sa_exc.InterfaceError, sa_exc.DisconnectionError))


class MonederoVentaMixin:
    """Se mezcla en QuickSaleWidget. Usa de él: _items, _compute_totals,
    _refresh_totals, _vaciar_carrito, _normalize_scan, satellite, etc."""

    # ─── Identificación ──────────────────────────────────────────────────

    def _es_qr_cliente(self, raw: str) -> bool:
        return bool(_RE_QR_CLIENTE.fullmatch(self._codigo_cliente_de(raw)))

    def _codigo_cliente_de(self, raw: str) -> str:
        from pos_uniformes.services.sale_selected_client_service import normalize_scanned_client_code

        return normalize_scanned_client_code(self._normalize_scan(raw))

    def _en_linea(self) -> bool:
        return bool(getattr(self.satellite, "_db_online", True))

    def _identificar_cliente(self, codigo: str, *, por_qr: bool, cliente_id: int | None = None) -> None:
        """Liga el cliente a la venta en curso y lee su monedero."""
        if not self._en_linea():
            self._cliente_sin_conexion(codigo, por_qr)
            return
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.database.models import Cliente
            from pos_uniformes.services import monedero_service as mon
            from pos_uniformes.services.sale_selected_client_service import find_active_sale_client_by_code

            with get_session() as session:
                cliente = (
                    session.get(Cliente, int(cliente_id))
                    if cliente_id is not None
                    else find_active_sale_client_by_code(session, codigo)
                )
                if cliente is None or not cliente.activo:
                    self._flash_scan_hint(f"Cliente {codigo} no encontrado")
                    return
                r = mon.resumen_cliente(session, cliente.id)
        except Exception as exc:  # noqa: BLE001
            if _es_error_de_red(exc):
                self._avisar_sin_conexion()
                self._cliente_sin_conexion(codigo, por_qr)
                return
            _logger.exception("Monedero: no se pudo leer al cliente %s", codigo)
            QMessageBox.warning(self, "Monedero", f"No se pudo leer el monedero del cliente.\n\n{exc}")
            return
        self._cliente = {
            "id": r.cliente_id,
            "codigo": r.codigo,
            "nombre": r.nombre,
            "por_qr": bool(por_qr),
            "en_linea": True,
            "tiene_monedero": r.tiene_monedero,
            "estado": r.estado,
            "disponible": r.disponible,
            "tasa": r.tasa,
            "proximo_vencimiento": r.proximo_vencimiento,
            "monto_proximo_vencimiento": r.monto_proximo_vencimiento,
        }
        self._usar_saldo = False
        self._refresh_totals()
        self._flash_scan_hint(f"Cliente: {r.nombre}")

    def _cliente_sin_conexion(self, codigo: str, por_qr: bool) -> None:
        if not codigo or not por_qr:
            QMessageBox.information(self, "Monedero", "Sin conexión al servidor: no se puede buscar al cliente.")
            return
        # Se guarda el código: al subir la venta se liga al cliente y gana su
        # cashback. El saldo no se puede ver ni usar.
        self._cliente = {
            "id": None, "codigo": codigo, "nombre": codigo, "por_qr": True, "en_linea": False,
            "tiene_monedero": False, "estado": "activo", "disponible": _CERO, "tasa": None,
            "proximo_vencimiento": None, "monto_proximo_vencimiento": _CERO,
        }
        self._usar_saldo = False
        self._refresh_totals()
        self._flash_scan_hint("Sin conexión: el cashback se acreditará al sincronizar")

    def _on_buscar_cliente(self) -> None:
        texto, ok = QInputDialog.getText(self, "Buscar cliente", "Nombre, teléfono o código del cliente:")
        texto = (texto or "").strip()
        if not ok or not texto:
            return
        if not self._en_linea():
            QMessageBox.information(self, "Monedero", "Sin conexión al servidor: no se puede buscar al cliente.")
            return
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services import monedero_service as mon

            with get_session() as session:
                encontrados = [(c.id, c.codigo_cliente, c.nombre, c.telefono or "") for c in mon.buscar_clientes(session, texto, 30)]
        except Exception as exc:  # noqa: BLE001
            if _es_error_de_red(exc):
                self._avisar_sin_conexion()
            QMessageBox.warning(self, "Monedero", f"No se pudo buscar al cliente.\n\n{exc}")
            return
        if not encontrados:
            QMessageBox.information(self, "Buscar cliente", "No se encontró ningún cliente activo.")
            return
        if len(encontrados) == 1:
            elegido = encontrados[0]
        else:
            etiquetas = [f"{nombre} · {codigo}" + (f" · {tel}" if tel else "") for _id, codigo, nombre, tel in encontrados]
            etiqueta, ok = QInputDialog.getItem(self, "Buscar cliente", "Elige al cliente:", etiquetas, 0, False)
            if not ok:
                return
            elegido = encontrados[etiquetas.index(etiqueta)]
        self._identificar_cliente(elegido[1], por_qr=False, cliente_id=elegido[0])

    def _quitar_cliente(self) -> None:
        self._cliente = None
        self._usar_saldo = False
        self._refresh_totals()

    # ─── Cálculos ────────────────────────────────────────────────────────

    def _puede_usar_saldo(self) -> bool:
        c = self._cliente
        return bool(
            c and c["en_linea"] and c["por_qr"] and c["estado"] == "activo" and c["disponible"] > 0
        )

    def _canje_actual(self, total: Decimal) -> Decimal:
        if not self._usar_saldo or not self._puede_usar_saldo() or not self._items:
            return _CERO
        from pos_uniformes.services.monedero_service import canje_ajustado

        return canje_ajustado(total, self._cliente["disponible"])

    def _cashback_estimado(self, total: Decimal, canje: Decimal) -> Decimal:
        c = self._cliente
        if not c or not c.get("tasa") or c["estado"] != "activo":
            return _CERO
        from pos_uniformes.services.monedero_service import calcular_cashback, importe_elegible

        return calcular_cashback(importe_elegible(total, canje), c["tasa"])

    def _datos_cliente_para_cola(self, tipo: str, total: Decimal) -> dict:
        """Lo que la cola necesita para ligar la venta al cliente."""
        c = self._cliente
        if not c:
            return {}
        estimado = self._cashback_estimado(total, _CERO) if tipo == "venta" else _CERO
        return {
            "cliente_id": c["id"],
            "cliente_codigo": c["codigo"],
            "cashback_estimado": str(estimado),
        }

    def _monedero_para_ticket(self, total: Decimal, tarjeta: bool) -> dict | None:
        """Renglones del ticket de una venta SIN canje (va por la cola)."""
        c = self._cliente
        if not c:
            return None
        estimado = self._cashback_estimado(total, _CERO)
        if estimado <= 0:
            return None
        return {"cashback": estimado, "cashback_pendiente": True}

    # ─── Barra del cliente ───────────────────────────────────────────────

    def _build_cliente_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("clienteBar")
        bar.setStyleSheet(
            "QFrame#clienteBar { background: #fff7ec; border: 1.5px solid #e8d5bd; border-radius: 12px; }"
            "QLabel { font-size: 14px; color: #2c2a27; }"
            "QPushButton { font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 8px;"
            " border: 1px solid #d9c3a5; background: white; }"
            "QPushButton:checked { background: #73341c; color: white; border-color: #73341c; }"
            "QPushButton:disabled { color: #b9aa98; }"
        )
        ly = QHBoxLayout()
        ly.setContentsMargins(14, 8, 10, 8)
        ly.setSpacing(8)
        self._cliente_label = QLabel("")
        self._cliente_label.setTextFormat(Qt.TextFormat.RichText)
        ly.addWidget(self._cliente_label, 1)
        self._btn_usar_saldo = QPushButton("Usar saldo")
        self._btn_usar_saldo.setCheckable(True)
        self._btn_usar_saldo.setAutoDefault(False)
        self._btn_usar_saldo.clicked.connect(self._toggle_usar_saldo)
        ly.addWidget(self._btn_usar_saldo)
        btn_mov = QPushButton("Movimientos")
        btn_mov.setAutoDefault(False)
        btn_mov.clicked.connect(self._ver_movimientos)
        self._btn_movimientos = btn_mov
        ly.addWidget(btn_mov)
        btn_quitar = QPushButton("Quitar")
        btn_quitar.setAutoDefault(False)
        btn_quitar.clicked.connect(self._quitar_cliente)
        ly.addWidget(btn_quitar)
        bar.setLayout(ly)
        bar.setVisible(False)
        self._cliente_bar = bar
        return bar

    def _pintar_cliente_bar(self) -> None:
        bar = getattr(self, "_cliente_bar", None)
        if bar is None:
            return
        c = self._cliente
        bar.setVisible(c is not None)
        if c is None:
            return
        _s, _d, total = self._compute_totals()
        canje = self._canje_actual(total)
        partes = [f"👛 <b>{c['nombre']}</b> · {c['codigo']}"]
        if not c["en_linea"]:
            partes.append("<span style='color:#9a5b00'>sin conexión: saldo no disponible</span>")
        elif c["estado"] != "activo":
            partes.append(f"<span style='color:#a12'>monedero {c['estado']}</span>")
        else:
            partes.append(f"Saldo <b>${c['disponible']:,.2f}</b>")
            if c.get("proximo_vencimiento") and c.get("monto_proximo_vencimiento", _CERO) > 0:
                vence = c["proximo_vencimiento"].astimezone().strftime("%d/%m/%Y")
                partes.append(f"<span style='color:#8a7a68'>${c['monto_proximo_vencimiento']:,.2f} vence {vence}</span>")
        if self._items:
            estimado = self._cashback_estimado(total, canje)
            if estimado > 0:
                partes.append(f"Gana <b>${estimado:,.2f}</b>")
            elif not c.get("tasa") and c["en_linea"]:
                partes.append("<span style='color:#8a7a68'>cashback no configurado</span>")
        self._cliente_label.setText(" · ".join(partes))
        puede = self._puede_usar_saldo()
        self._btn_usar_saldo.setEnabled(puede)
        self._btn_usar_saldo.setChecked(self._usar_saldo and puede)
        if c["en_linea"] and not c["por_qr"] and c["disponible"] > 0:
            self._btn_usar_saldo.setToolTip("Para usar saldo escanea el QR del cliente")
        else:
            self._btn_usar_saldo.setToolTip("")
        self._btn_movimientos.setEnabled(bool(c["en_linea"] and c["tiene_monedero"]))

    def _toggle_usar_saldo(self) -> None:
        self._usar_saldo = bool(self._btn_usar_saldo.isChecked()) and self._puede_usar_saldo()
        self._refresh_totals()

    def _ver_movimientos(self) -> None:
        c = self._cliente
        if not c or not c["id"]:
            return
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services import monedero_service as mon

            with get_session() as session:
                monedero = mon.monedero_de_cliente(session, c["id"])
                filas = [] if monedero is None else [
                    (f.movimiento.created_at, f.etiqueta, Decimal(f.movimiento.monto), f.saldo_contable,
                     f.movimiento.expira_at)
                    for f in mon.historial(session, monedero.id)[:100]
                ]
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Monedero", f"No se pudieron leer los movimientos.\n\n{exc}")
            return
        mostrar_movimientos(self, f"Monedero de {c['nombre']}", filas)

    # ─── Venta con saldo (en línea) ──────────────────────────────────────

    def _cobrar_con_monedero(self, tarjeta: bool, con_copia: bool, *, sin_ticket: bool = False) -> None:
        """Confirma la venta con saldo en la base ANTES de imprimir.

        Si no hay conexión o el saldo ya no alcanza, no se registra nada y el
        carrito queda igual para cobrarlo de otra forma."""
        from pos_uniformes.services import monedero_service as mon

        _s, _d, total = self._compute_totals()
        total = Decimal(str(total)).quantize(Decimal("0.01"))
        canje = self._canje_actual(total)
        c = self._cliente
        if canje <= 0 or not c:
            return
        if not self._en_linea():
            QMessageBox.warning(self, "Monedero", mon.MENSAJE_SIN_CONEXION)
            return
        import uuid as _uuid

        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.libreta_service import registrar_venta_con_monedero

        origen = None
        try:
            from pos_uniformes.services.satellite_identity_service import get_satellite_id

            origen = get_satellite_id()
        except Exception:  # noqa: BLE001
            pass
        items = [
            {"sku": it["sku"], "nombre": it["nombre"], "talla": it["talla"],
             "cantidad": int(it["cantidad"]), "precio": str(it["precio"])}
            for it in self._items
        ]
        try:
            with get_session() as session:
                try:
                    _venta, _mov, cashback = registrar_venta_con_monedero(
                        session,
                        employee_code=str(self._employee_code or ""),
                        employee_name=str(self._employee_name or self._employee_code or ""),
                        items=items,
                        monto_total=total,
                        monto_monedero=canje,
                        cliente_id=int(c["id"]),
                        operacion_uuid=str(_uuid.uuid4()),
                        pago_tarjeta=bool(tarjeta),
                        descuento_empleada=bool(self._discount_active),
                        origen=origen,
                    )
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                saldo = mon.resumen_cliente(session, int(c["id"])).disponible
                cashback_monto = Decimal(cashback.monto) if cashback is not None else _CERO
        except Exception as exc:  # noqa: BLE001
            if _es_error_de_red(exc):
                self._avisar_sin_conexion()
                QMessageBox.warning(self, "Monedero", mon.MENSAJE_SIN_CONEXION)
            elif isinstance(exc, (mon.MonederoError, PermissionError)):
                QMessageBox.warning(self, "Monedero", str(exc))
                self._identificar_cliente(c["codigo"], por_qr=c["por_qr"], cliente_id=c["id"])
            else:
                _logger.exception("Monedero: falló la venta con saldo")
                QMessageBox.warning(self, "Monedero", f"No se registró la venta.\n\n{exc}")
            return

        info = {
            "canje": canje,
            "por_cobrar": total - canje,
            "metodo": "Tarjeta" if tarjeta else "Efectivo",
            "cashback": cashback_monto,
            "saldo": saldo,
        }
        tickets: list[str] = []
        if not sin_ticket:
            tickets.append(self._build_venta_text(monedero=info))
            if self._discount_active:
                tickets.append(self._build_employee_copy_text(terminal_commission=tarjeta))
            elif con_copia:
                tickets.append(self._build_venta_text(store_copy=True, terminal_commission=tarjeta, monedero=info))
        # Ya quedó registrada: el carrito se vacía aunque no se imprima.
        self._vaciar_carrito()
        if sin_ticket:
            self._avisar_sin_ticket()
        else:
            from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets

            route_tickets(self, "Ticket de venta", tickets)
        self._scan_input.setFocus()


def mostrar_movimientos(parent, titulo: str, filas: list[tuple]) -> None:
    """Tabla de movimientos: fecha, concepto, monto, saldo, vence."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(titulo)
    dlg.resize(640, 460)
    ly = QVBoxLayout(dlg)
    tabla = QTableWidget(len(filas), 5)
    tabla.setHorizontalHeaderLabels(["Fecha", "Concepto", "Monto", "Saldo", "Vence"])
    tabla.verticalHeader().setVisible(False)
    tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    for i, (cuando, concepto, monto, saldo, vence) in enumerate(filas):
        tabla.setItem(i, 0, QTableWidgetItem(cuando.astimezone().strftime("%d/%m/%Y %H:%M") if cuando else ""))
        tabla.setItem(i, 1, QTableWidgetItem(concepto))
        m = QTableWidgetItem(f"{'+' if monto > 0 else '-'}${abs(monto):,.2f}")
        m.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tabla.setItem(i, 2, m)
        s = QTableWidgetItem(f"${saldo:,.2f}")
        s.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tabla.setItem(i, 3, s)
        tabla.setItem(i, 4, QTableWidgetItem(vence.astimezone().strftime("%d/%m/%Y") if vence and monto > 0 else ""))
    if not filas:
        ly.addWidget(QLabel("Sin movimientos todavía."))
    ly.addWidget(tabla)
    nota = QLabel("El saldo de la columna es el del libro; lo vencido deja de estar disponible en su fecha.")
    nota.setWordWrap(True)
    nota.setStyleSheet("color: #8a7a68; font-size: 12px;")
    ly.addWidget(nota)
    cerrar = QPushButton("Cerrar")
    cerrar.clicked.connect(dlg.accept)
    ly.addWidget(cerrar, alignment=Qt.AlignmentFlag.AlignRight)
    dlg.exec()
