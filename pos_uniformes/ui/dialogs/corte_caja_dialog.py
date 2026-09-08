"""Diálogos de caja: hacer corte por periodo y editar reactivo/nómina.

Los usan el dueño (Libreta → Imprimir corte) y el encargado (su pantalla
grande). El corte muestra lo que debería haber en el cajón, pide lo contado
y cuánto se queda de fondo, guarda con `caja_service.cerrar_corte` e imprime.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from PyQt6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.corte_caja_service import EstadoCaja, diferencia

logger = logging.getLogger(__name__)

_GRANDE = "font-size: 22px; font-weight: 800; padding: 8px;"
_NORMAL = "font-size: 18px; font-weight: 700; padding: 6px;"


def _spin(valor: Decimal, grande: bool) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(0.0, 9_999_999.0)
    s.setDecimals(2)
    s.setPrefix("$ ")
    s.setValue(float(valor))
    s.setStyleSheet(_GRANDE if grande else _NORMAL)
    return s


def texto_ticket_corte(corte, por_empleada: list | None = None, *, pagos: list | None = None, venta_efectivo=None) -> str:
    """Ticket térmico del corte por periodo: cifra final, fondo, pagos y
    comisiones por empleada. Sin esperado ni diferencia (solo en pantalla).

    `pagos` (EmpleadaPago) imprime la sección PAGAR HOY con nombre y monto:
    es lo que el encargado toma del cajón para cada una."""
    from datetime import datetime

    from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
        TICKET_CHAR_WIDTH as _TW,
        tk_bot,
        tk_dbl,
        tk_field,
        tk_line,
        tk_mid,
        tk_row,
        tk_top,
    )

    lines: list[str] = []
    lines.append("CORTE DE CAJA".center(_TW))
    lines.append(str(corte.periodo_label or "").center(_TW))
    lines.append(tk_top())
    tk_field("Impreso:", datetime.now().strftime("%d/%m/%Y %H:%M"), lines)
    if corte.creado_por:
        tk_field("Por:", str(corte.creado_por), lines)
    lines.append(tk_mid())
    lines.append(tk_row("Operaciones:", str(corte.operaciones)))
    if venta_efectivo is not None:
        lines.append(tk_row("VENTA (efectivo):", f"${Decimal(venta_efectivo):,.2f}"))
    lines.append(tk_row("Fondo inicial:", f"${Decimal(corte.reactivo_inicial):,.2f}"))
    if Decimal(corte.retiros_pagos or 0) > 0:
        lines.append(tk_row("Pagos empleadas:", f"-${Decimal(corte.retiros_pagos):,.2f}"))
    if Decimal(corte.otros_retiros or 0) > 0:
        lines.append(tk_row("Otros retiros:", f"-${Decimal(corte.otros_retiros):,.2f}"))
    lines.append(tk_dbl())
    lines.append(tk_row("EN CAJA:", f"${Decimal(corte.monto_final):,.2f}"))
    lines.append(tk_row("Se queda (fondo):", f"${Decimal(corte.reactivo_final):,.2f}"))
    retirado = (Decimal(corte.monto_final) - Decimal(corte.reactivo_final)).quantize(Decimal("0.01"))
    lines.append(tk_row("Se retira:", f"${retirado:,.2f}"))
    if corte.nota:
        tk_field("Nota:", str(corte.nota), lines)
    lines.append(tk_bot())
    if pagos:
        lines.append("")
        lines.append("PAGAR HOY".center(_TW))
        lines.append(tk_top())
        for p in pagos:
            nombre = (p.employee_name or p.employee_code)[: _TW - 16]
            lines.append(tk_row(f"{nombre}:", f"${Decimal(p.total):,.2f}"))
            detalle = f"{int(p.comisiones or 0)} com."
            if int(p.faltas or 0):
                detalle += f" - {int(p.faltas)} falta(s)"
            lines.append(tk_line(f"  {detalle}"))
        lines.append(tk_dbl())
        total = sum((Decimal(p.total) for p in pagos), Decimal("0.00"))
        lines.append(tk_row("TOTAL PAGOS:", f"${total:,.2f}"))
        lines.append(tk_bot())
    if por_empleada:
        lines.append("")
        lines.append("POR EMPLEADA".center(_TW))
        lines.append(tk_top())
        first = True
        for r in por_empleada:
            if not first:
                lines.append(tk_mid())
            first = False
            lines.append(tk_line((r.employee_name or r.employee_code)[: _TW - 4]))
            lines.append(tk_row(f"{r.operaciones} ops:", f"{r.comisiones} com."))
        lines.append(tk_bot())
    lines.append("")
    lines.append("Corte generado por la Libreta.".center(_TW))
    return "\n".join(lines)


def texto_estado_caja(estado: EstadoCaja) -> str:
    r = estado.resumen
    partes = [
        f"Periodo: {_periodo(estado)}",
        f"Fondo (reactivo) con que abrió: ${estado.reactivo:,.2f}",
        f"Efectivo de ventas y abonos: ${r.efectivo:,.2f}   ({r.operaciones} operaciones)",
    ]
    if r.tarjeta:
        partes.append(f"Con tarjeta (no está en el cajón): ${r.tarjeta:,.2f}")
    if estado.pagos:
        partes.append(f"Pagos a empleadas ya hechos: -${estado.pagos:,.2f}")
    partes.append(f"DEBE HABER EN EL CAJÓN: ${estado.esperado:,.2f}")
    return "\n".join(partes)


def _periodo(estado: EstadoCaja) -> str:
    h = estado.hasta.astimezone() if estado.hasta.tzinfo else estado.hasta
    if estado.desde is None:
        return f"todo lo registrado hasta {h:%d/%m %H:%M}"
    d = estado.desde.astimezone() if estado.desde.tzinfo else estado.desde
    return f"del {d:%d/%m %H:%M} al {h:%d/%m %H:%M}"


def hacer_corte_caja(parent: QWidget | None, *, creado_por: str, grande: bool = False):
    """Flujo completo: estado → captura → guarda → imprime. Devuelve el corte o None."""
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.corte_caja_service import cerrar_corte, estado_caja
    from pos_uniformes.services.libreta_service import resumir_por_empleada
    from pos_uniformes.services.corte_caja_service import operaciones_del_periodo

    try:
        with get_session() as session:
            estado = estado_caja(session)
            rows = operaciones_del_periodo(session, estado.desde, estado.hasta)
            por_empleada = resumir_por_empleada(rows)
    except Exception:  # noqa: BLE001
        logger.exception("Corte: no se pudo calcular el estado de caja")
        QMessageBox.warning(parent, "Sin conexión", "No se alcanzó la base. Inténtalo otra vez.")
        return None

    dlg = QDialog(parent)
    dlg.setWindowTitle("Hacer corte")
    ly = QVBoxLayout()
    ly.setContentsMargins(20, 18, 20, 18)
    ly.setSpacing(10)
    if grande:
        dlg.setStyleSheet("QDialog { background: #f4ede2; } QLabel { color: #2c2a27; font-size: 18px; }")
    resumen = QLabel(texto_estado_caja(estado))
    resumen.setWordWrap(True)
    ly.addWidget(resumen)

    form = QFormLayout()
    contado = _spin(estado.esperado, grande)
    form.addRow("Cuenta el cajón. ¿Cuánto hay?", contado)
    fondo = _spin(estado.reactivo, grande)
    form.addRow("¿Cuánto se queda de fondo?", fondo)
    otros = _spin(Decimal("0.00"), grande)
    form.addRow("Otros retiros (opcional):", otros)
    nota = QLineEdit()
    nota.setPlaceholderText("Nota (opcional)")
    form.addRow("", nota)
    ly.addLayout(form)

    dif = QLabel("")
    dif.setStyleSheet("font-weight: 700;")
    ly.addWidget(dif)

    def _refrescar_dif() -> None:
        esperado = estado.esperado - Decimal(str(otros.value())).quantize(Decimal("0.01"))
        d = diferencia(Decimal(str(contado.value())), esperado)
        if d == 0:
            dif.setText("✅ Cuadra exacto.")
        elif d > 0:
            dif.setText(f"Sobran ${d:,.2f}")
        else:
            dif.setText(f"Faltan ${-d:,.2f}")

    contado.valueChanged.connect(lambda _v: _refrescar_dif())
    otros.valueChanged.connect(lambda _v: _refrescar_dif())
    _refrescar_dif()

    botones = QHBoxLayout()
    cancelar = QPushButton("Cancelar")
    cancelar.setAutoDefault(False)
    cancelar.clicked.connect(dlg.reject)
    botones.addWidget(cancelar)
    ok = QPushButton("🖨 Guardar e imprimir corte")
    ok.setObjectName("primaryButton")
    ok.clicked.connect(dlg.accept)
    botones.addWidget(ok, 1)
    ly.addLayout(botones)
    dlg.setLayout(ly)
    if grande:
        dlg.resize(560, 520)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None

    try:
        with get_session() as session:
            corte = cerrar_corte(
                session,
                contado=Decimal(str(contado.value())),
                reactivo_final=Decimal(str(fondo.value())),
                otros_retiros=Decimal(str(otros.value())),
                nota=nota.text(),
                creado_por=creado_por,
                ahora=estado.hasta,
            )
            texto = texto_ticket_corte(corte, por_empleada)
    except ValueError as exc:
        QMessageBox.warning(parent, "Corte", str(exc))
        return None
    except Exception:  # noqa: BLE001
        logger.exception("Corte: no se pudo guardar")
        QMessageBox.warning(parent, "No se guardó", "Inténtalo otra vez.")
        return None
    try:
        from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets

        route_tickets(parent, "Corte de caja", [texto])
    except Exception:  # noqa: BLE001 — el corte ya quedó guardado
        logger.exception("Corte: falló la impresión")
    return corte


def editar_parametros_caja(parent: QWidget | None) -> bool:
    """Reactivo vigente y reglas de pago (solo dueño). True si guardó."""
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.corte_caja_service import cargar_parametros, guardar_parametros

    try:
        with get_session() as session:
            p = cargar_parametros(session)
    except Exception:  # noqa: BLE001
        QMessageBox.warning(parent, "Sin conexión", "No se alcanzó la base.")
        return False
    dlg = QDialog(parent)
    dlg.setWindowTitle("Caja y nómina")
    ly = QVBoxLayout()
    ly.setContentsMargins(20, 18, 20, 18)
    form = QFormLayout()
    reactivo = _spin(p.reactivo_actual, False)
    sueldo = _spin(p.sueldo_base, False)
    tarifa = _spin(p.tarifa_comision, False)
    falta = _spin(p.descuento_falta, False)
    form.addRow("Fondo de caja (reactivo) ahora:", reactivo)
    form.addRow("Sueldo base por semana:", sueldo)
    form.addRow("Pesos por comisión:", tarifa)
    form.addRow("Descuento por falta:", falta)
    ly.addLayout(form)
    hint = QLabel("El fondo se actualiza solo en cada corte; edítalo aquí únicamente para corregirlo.")
    hint.setWordWrap(True)
    hint.setStyleSheet("color: #8a8177; font-size: 12px;")
    ly.addWidget(hint)
    botones = QHBoxLayout()
    cancelar = QPushButton("Cancelar")
    cancelar.clicked.connect(dlg.reject)
    ok = QPushButton("Guardar")
    ok.setObjectName("primaryButton")
    ok.clicked.connect(dlg.accept)
    botones.addWidget(cancelar)
    botones.addWidget(ok, 1)
    ly.addLayout(botones)
    dlg.setLayout(ly)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return False
    try:
        with get_session() as session:
            guardar_parametros(
                session,
                reactivo_actual=Decimal(str(reactivo.value())),
                sueldo_base=Decimal(str(sueldo.value())),
                tarifa_comision=Decimal(str(tarifa.value())),
                descuento_falta=Decimal(str(falta.value())),
            )
    except Exception:  # noqa: BLE001
        logger.exception("Caja: no se pudieron guardar los parámetros")
        QMessageBox.warning(parent, "No se guardó", "Inténtalo otra vez.")
        return False
    return True


def confirmar_pago(parent: QWidget | None, *, employee_code: str, employee_name: str, creado_por: str, grande: bool = False):
    """Muestra el desglose del pago y, si confirma, lo registra. Devuelve EmpleadaPago o None."""
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.nomina_service import pago_pendiente, registrar_pago_con_monto

    try:
        with get_session() as session:
            d = pago_pendiente(session, employee_code)
    except Exception:  # noqa: BLE001
        logger.exception("Pago: no se pudo calcular")
        QMessageBox.warning(parent, "Sin conexión", "No se alcanzó la base. Inténtalo otra vez.")
        return None
    desde = d.desde.strftime("%d/%m") if d.desde else "inicio"
    texto = (
        f"{employee_name}\n"
        f"Periodo: {desde} → {d.hasta:%d/%m}\n\n"
        f"Sueldo base:        ${d.sueldo_base:,.2f}\n"
        f"{d.comisiones} comisiones × ${d.tarifa_comision:,.2f}:  +${d.monto_comisiones:,.2f}\n"
        + (f"{d.faltas} falta(s):        -${d.descuento_faltas:,.2f}\n" if d.faltas else "")
        + f"\nA PAGAR:  ${d.total:,.2f}"
    )
    box = QMessageBox(parent)
    box.setWindowTitle("Pagar")
    box.setText(texto)
    if grande:
        box.setStyleSheet("QLabel { font-size: 20px; font-weight: 700; } QPushButton { font-size: 18px; min-height: 48px; padding: 6px 18px; }")
    pagar = box.addButton("💵 Ya le pagué", QMessageBox.ButtonRole.YesRole)
    box.addButton("Cancelar", QMessageBox.ButtonRole.NoRole)
    box.exec()
    if box.clickedButton() is not pagar:
        return None
    try:
        with get_session() as session:
            pago = registrar_pago_con_monto(session, employee_code, creado_por=creado_por)
            session.refresh(pago)
            session.expunge(pago)
    except PermissionError as exc:
        QMessageBox.warning(parent, "Pago", str(exc))
        return None
    except Exception:  # noqa: BLE001
        logger.exception("Pago: no se pudo registrar")
        QMessageBox.warning(parent, "No se guardó", "Inténtalo otra vez.")
        return None
    return pago


def texto_previa_corte_encargado(estado: EstadoCaja, avisos: list) -> str:
    """Lo que ve el encargado antes de imprimir: venta, a quién pagar, retiro."""
    total_pagos = sum((a.total_estimado for a in avisos), Decimal("0.00"))
    retiro = (estado.resumen.efectivo - estado.pagos - total_pagos).quantize(Decimal("0.01"))
    lineas = [f"VENTA: ${estado.resumen.efectivo:,.2f}"]
    if avisos:
        lineas.append("")
        lineas.append("PAGAR HOY:")
        for a in avisos:
            lineas.append(f"  {a.employee_name.split()[0]}  ${a.total_estimado:,.2f}")
    if estado.pagos:
        lineas.append(f"Pagos ya hechos: -${estado.pagos:,.2f}")
    lineas.append("")
    lineas.append(f"SE RETIRA: ${retiro:,.2f}")
    lineas.append(f"Se queda de fondo: ${estado.reactivo:,.2f}")
    return "\n".join(lineas)


def hacer_corte_automatico(parent: QWidget | None, *, creado_por: str):
    """Corte de un botón para el encargado. Devuelve (CorteAutomatico, texto_ticket) o None."""
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.corte_caja_service import cerrar_corte_automatico, operaciones_del_periodo
    from pos_uniformes.services.libreta_service import resumir_por_empleada

    try:
        with get_session() as session:
            resultado = cerrar_corte_automatico(session, creado_por=creado_por)
            rows = operaciones_del_periodo(session, resultado.estado.desde, resultado.estado.hasta)
            texto = texto_ticket_corte(
                resultado.corte,
                resumir_por_empleada(rows),
                pagos=resultado.pagos,
                venta_efectivo=resultado.estado.resumen.efectivo,
            )
    except Exception:  # noqa: BLE001
        logger.exception("Corte automático: no se pudo guardar")
        QMessageBox.warning(parent, "No se guardó", "Inténtalo otra vez.")
        return None
    try:
        from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets

        route_tickets(parent, "Corte de caja", [texto])
    except Exception:  # noqa: BLE001 — el corte ya quedó guardado
        logger.exception("Corte automático: falló la impresión")
    return resultado, texto
