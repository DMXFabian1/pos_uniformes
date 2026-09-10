"""Diálogos de caja: hacer corte por periodo y editar reactivo/nómina.

Los usan el dueño (Libreta → Imprimir corte) y el encargado (su pantalla
grande). El corte muestra lo que debería haber en el cajón, pide lo contado
y cuánto se queda de fondo, guarda con `caja_service.cerrar_corte` e imprime.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from types import SimpleNamespace

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
from pos_uniformes.services.nomina_service import OWNER_CODE

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


def _seccion_retiros(retiros: list, lines: list[str], tk_top, tk_mid, tk_row, tk_dbl, tk_bot, _TW) -> None:
    if not retiros:
        return
    lines.append("")
    lines.append("RETIROS DEL CAJON".center(_TW))
    lines.append(tk_top())
    for r in retiros:
        lines.append(tk_row(f"{str(r.motivo)[: _TW - 16]}:", f"${Decimal(r.monto):,.2f}"))
    if len(retiros) > 1:
        lines.append(tk_dbl())
        lines.append(tk_row("Total retiros:", f"${sum((Decimal(r.monto) for r in retiros), Decimal('0.00')):,.2f}"))
    lines.append(tk_bot())


def _tk():
    from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
        TICKET_CHAR_WIDTH,
        tk_bot,
        tk_dbl,
        tk_field,
        tk_line,
        tk_mid,
        tk_row,
        tk_top,
    )

    return TICKET_CHAR_WIDTH, tk_top, tk_mid, tk_dbl, tk_bot, tk_row, tk_line, tk_field


def _nombre_pila(p) -> str:
    return (getattr(p, "employee_name", "") or getattr(p, "employee_code", "") or "?").split()[0]


def _bloque_cuenta(lines, *, corte, venta, tarjeta, tarjeta_ops, pagos_restar, retiros, sacar) -> None:
    """La cuenta de un corte, de arriba abajo (pedido de Daniel 2026-09-09):

        Reactivo en caja        (primera línea; se queda igual)
        Venta en efectivo
        Con tarjeta (N) / VENTA TOTAL   (solo si hubo tarjeta)
        ── Venta en efectivo − pagos − gastos ══ SACAR DE LA VENTA

    Sin "EN CAJA" ni "Se retira": la venta es la que manda y todo lo que
    sale del cajón se ve como resta."""
    _TW, tk_top, tk_mid, tk_dbl, tk_bot, tk_row, tk_line, _tk_field = _tk()
    venta = Decimal(venta or 0).quantize(Decimal("0.01"))
    tarjeta_monto = Decimal(tarjeta or 0).quantize(Decimal("0.01"))
    reactivo_ini = Decimal(getattr(corte, "reactivo_inicial", 0) or 0)
    reactivo_fin = Decimal(getattr(corte, "reactivo_final", 0) or 0)
    con_reactivo = reactivo_ini > 0 or reactivo_fin > 0

    lines.append(tk_top())
    if con_reactivo:
        lines.append(tk_row("Reactivo en caja:", f"${reactivo_ini:,.2f}"))
        lines.append(tk_mid())
    lines.append(tk_row("Venta en efectivo:", f"${venta:,.2f}"))
    if tarjeta_monto > 0:
        cuantas = f" ({tarjeta_ops})" if tarjeta_ops else ""
        lines.append(tk_row(f"Con tarjeta{cuantas}:", f"${tarjeta_monto:,.2f}"))
        lines.append(tk_row("VENTA TOTAL:", f"${(venta + tarjeta_monto):,.2f}"))
        lines.append(tk_line("  (la tarjeta no esta en el cajon)"))
    restas = list(pagos_restar or []) or list(retiros or [])
    if restas:
        lines.append(tk_mid())
        lines.append(tk_row("Venta en efectivo:", f"${venta:,.2f}"))
        for p in pagos_restar or []:
            lines.append(tk_row(f"Pago a {_nombre_pila(p)}:"[: _TW - 14], f"-${Decimal(p.total):,.2f}"))
        for r in retiros or []:
            lines.append(tk_row(f"Gasto ({str(r.motivo)[: _TW - 24]}):", f"-${Decimal(r.monto):,.2f}"))
    if con_reactivo:
        lines.append(tk_dbl())
        lines.append(tk_row("SACAR DE LA VENTA:", f"${Decimal(sacar):,.2f}"))
    lines.append(tk_bot())
    if con_reactivo:
        if reactivo_fin < reactivo_ini:
            lines.append(tk_top())
            lines.append(tk_line("OJO: los pagos fueron mas que"))
            lines.append(tk_line("la venta. Se tomo del reactivo."))
            lines.append(tk_row("Reactivo que queda:", f"${reactivo_fin:,.2f}"))
            lines.append(tk_bot())
        else:
            lines.append("El reactivo de la caja se queda igual.".center(_TW))


def _bloque_pagos(lines, pagos: list, ya_pagados: list, *, total: bool, titulo: str | None = None) -> None:
    """PAGAR A X (desglose) · YA PAGADO A X (hora) (desglose). Si no hay nada, lo dice."""
    _TW, tk_top, tk_mid, tk_dbl, tk_bot, tk_row, tk_line, _tk_field = _tk()
    lines.append("")
    if titulo:
        lines.append(titulo.center(_TW))
    lines.append(tk_top())
    idx = 0
    for p in pagos:
        if idx:
            lines.append(tk_mid())
        idx += 1
        lines.append(tk_row(f"PAGAR A {_nombre_pila(p).upper()}:"[: _TW - 14], f"${Decimal(p.total):,.2f}"))
        _desglose_pago(p, lines, tk_row)
    for p in ya_pagados:
        if idx:
            lines.append(tk_mid())
        idx += 1
        hora = _hora_local(getattr(p, "created_at", None)).strftime("%H:%M") if getattr(p, "created_at", None) else ""
        lines.append(tk_row(f"YA PAGADO A {_nombre_pila(p).upper()}:"[: _TW - 14], f"${Decimal(p.total):,.2f}"))
        if hora:
            lines.append(tk_line(f"  (se le pago a las {hora})"))
        _desglose_pago(p, lines, tk_row)
    if not pagos and not ya_pagados:
        lines.append(tk_line("Hoy no se paga a nadie."))
    elif total and len(pagos) + len(ya_pagados) > 1:
        lines.append(tk_dbl())
        suma = sum((Decimal(p.total) for p in list(pagos) + list(ya_pagados)), Decimal("0.00"))
        lines.append(tk_row("TOTAL PAGOS:", f"${suma:,.2f}"))
    lines.append(tk_bot())


def texto_ticket_corte(corte, por_empleada: list | None = None, *, pagos: list | None = None, venta_efectivo=None, retiros: list | None = None, reimpresion: bool = False, tarjeta=None, tarjeta_ops: int | None = None) -> str:
    """Ticket del dueño (CORTE DE CAJA): misma cuenta simple que el del
    encargado + POR EMPLEADA con operaciones. Sin esperado ni diferencia.

    Si el dueño ajustó su cifra, la "venta en efectivo" que se imprime es la
    que cuadra con su cifra (cifra − reactivo + pagos + gastos): el ticket
    siempre suma y nada delata el ajuste."""
    from datetime import datetime

    _TW, tk_top, tk_mid, tk_dbl, tk_bot, tk_row, tk_line, tk_field = _tk()
    pagos = list(pagos or [])
    retiros = list(retiros or [])
    lines: list[str] = []
    lines.append("CORTE DE CAJA".center(_TW))
    lines.append(str(corte.periodo_label or "").center(_TW))
    if reimpresion:
        lines.append("* REIMPRESION *".center(_TW))
    lines.append(tk_top())
    if reimpresion and getattr(corte, "created_at", None):
        tk_field("Corte:", _hora_local(corte.created_at).strftime("%d/%m/%Y %H:%M"), lines)
    tk_field("Impreso:", datetime.now().strftime("%d/%m/%Y %H:%M"), lines)
    if corte.creado_por:
        tk_field("Por:", str(corte.creado_por), lines)
    if corte.nota:
        tk_field("Nota:", str(corte.nota), lines)
    lines.append(tk_bot())

    con_reactivo = Decimal(corte.reactivo_inicial or 0) > 0 or Decimal(corte.reactivo_final or 0) > 0
    # Sumas persistidas en el corte (valen aunque no se pasen las listas).
    total_pagos = Decimal(getattr(corte, "retiros_pagos", 0) or 0) or sum((Decimal(p.total) for p in pagos), Decimal("0.00"))
    total_gastos = Decimal(getattr(corte, "otros_retiros", 0) or 0) or sum((Decimal(r.monto) for r in retiros), Decimal("0.00"))
    if con_reactivo and (_con_ajuste(corte) or venta_efectivo is None):
        venta = Decimal(corte.monto_final) - Decimal(corte.reactivo_inicial or 0) + total_pagos + total_gastos
    elif venta_efectivo is not None:
        venta = Decimal(venta_efectivo)
    else:
        venta = Decimal(corte.monto_final)
    sacar = (Decimal(corte.monto_final) - Decimal(corte.reactivo_final or 0)).quantize(Decimal("0.01"))
    # Sin las listas (p.ej. corte viejo o ticket rápido) las restas salen como totales.
    pagos_restar = pagos or ([SimpleNamespace(employee_name="empleadas", total=total_pagos)] if total_pagos > 0 else [])
    gastos_restar = retiros or ([SimpleNamespace(motivo="otros", monto=total_gastos)] if total_gastos > 0 else [])
    _bloque_cuenta(lines, corte=corte, venta=venta, tarjeta=tarjeta, tarjeta_ops=tarjeta_ops, pagos_restar=pagos_restar, retiros=gastos_restar, sacar=sacar)
    if not con_reactivo:
        lines.append(tk_row("Total del dia:", f"${Decimal(corte.monto_final):,.2f}"))
    if pagos:
        _bloque_pagos(lines, pagos, [], total=True, titulo="PAGOS A EMPLEADAS")
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


def _con_ajuste(corte) -> bool:
    """True si la cifra del dueño no es la real (solo cortes por periodo con esperado guardado)."""
    esperado = getattr(corte, "monto_esperado", None)
    if esperado is None or getattr(corte, "hasta", None) is None and getattr(corte, "desde", None) is None:
        return False
    return Decimal(esperado or 0) > 0 and Decimal(corte.monto_final) != Decimal(esperado)


def pagos_previos_del_periodo(session, resultado) -> list:
    """Pagos del periodo que NO registró este corte (ya se pagaron antes)."""
    from pos_uniformes.services.corte_caja_service import pagos_registrados_del_periodo

    nuevos = {id(p) for p in resultado.pagos} | {getattr(p, "id", None) for p in resultado.pagos}
    return [
        p for p in pagos_registrados_del_periodo(session, resultado.estado.desde, resultado.estado.hasta)
        if id(p) not in nuevos and getattr(p, "id", None) not in nuevos
    ]


def contar_tarjeta(rows: list) -> int:
    """Cuántas operaciones (venta/abono) fueron con tarjeta = vouchers a cuadrar."""
    return sum(1 for r in rows or [] if getattr(r, "pago_tarjeta", False) and str(getattr(r, "tipo", "")) in ("venta", "abono"))


def _hora_local(momento):
    return momento.astimezone() if getattr(momento, "tzinfo", None) else momento


def _desglose_pago(p, lines: list[str], tk_row) -> None:
    """Sueldo + comisiones × tarifa − faltas, para que se sepa por qué es esa cantidad."""
    dias = getattr(p, "dias_trabajados", None)
    if dias is not None:
        lines.append(tk_row(f"  {int(dias)} dia(s) x ${Decimal(p.tarifa_dia or 0):,.2f}:", f"${Decimal(p.sueldo_base):,.2f}"))
    else:
        lines.append(tk_row("  Sueldo:", f"${Decimal(p.sueldo_base):,.2f}"))
    com = int(p.comisiones or 0)
    tarifa = Decimal(p.tarifa_comision or 0)
    tarifa_txt = f"${tarifa:,.0f}" if tarifa == tarifa.to_integral() else f"${tarifa:,.2f}"
    lines.append(tk_row(f"  {com} comisiones x {tarifa_txt}:", f"+${Decimal(p.monto_comisiones):,.2f}"))
    faltas = int(p.faltas or 0)
    if faltas:
        lines.append(tk_row(f"  {faltas} falta(s):", f"-${Decimal(p.descuento_faltas):,.2f}"))


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
    if estado.retiros:
        partes.append(f"Retiros apuntados (proveedor, renta...): -${estado.retiros:,.2f}")
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
    from pos_uniformes.services.corte_caja_service import (
        cerrar_corte,
        estado_caja,
        operaciones_del_periodo,
        pagos_registrados_del_periodo,
    )
    from pos_uniformes.services.libreta_service import resumir_por_empleada

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

    # Solo Daniel: dejar el papel sin la linea "Con tarjeta". Es por corte
    # (arranca apagada); en pantalla la sigue viendo.
    from PyQt6.QtWidgets import QCheckBox

    sin_tarjeta = QCheckBox("Ocultar los cobros con tarjeta (no salen en el ticket)")
    sin_tarjeta.setVisible(str(creado_por or "").strip().upper() == OWNER_CODE)
    if grande:
        sin_tarjeta.setStyleSheet("font-size: 17px;")
    ly.addWidget(sin_tarjeta)

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
            if sin_tarjeta.isChecked():
                # Privados: desaparecen de TODO lo que ve el encargado (su
                # ticket, su pantalla y su celular), no solo de este papel.
                from pos_uniformes.services.libreta_service import marcar_privadas_del_periodo

                ocultos = marcar_privadas_del_periodo(
                    session, estado.desde, estado.hasta, creado_por=creado_por
                )
            else:
                ocultos = 0
            pagos_periodo = pagos_registrados_del_periodo(session, estado.desde, estado.hasta)
            from pos_uniformes.services.retiros_service import retiros_del_periodo

            retiros_periodo = retiros_del_periodo(session, estado.desde, estado.hasta)
            texto = texto_ticket_corte(
                corte, por_empleada, pagos=pagos_periodo, venta_efectivo=estado.resumen.efectivo, retiros=retiros_periodo,
                tarjeta=None if sin_tarjeta.isChecked() else estado.resumen.tarjeta,
                tarjeta_ops=None if sin_tarjeta.isChecked() else contar_tarjeta(rows),
            )
    except ValueError as exc:
        QMessageBox.warning(parent, "Corte", str(exc))
        return None
    except Exception:  # noqa: BLE001
        logger.exception("Corte: no se pudo guardar")
        QMessageBox.warning(parent, "No se guardó", "Inténtalo otra vez.")
        return None
    if ocultos:
        QMessageBox.information(
            parent,
            "Movimientos ocultos",
            f"{ocultos} cobro(s) con tarjeta quedaron ocultos para el encargado: "
            "ese dinero no aparece en su ticket, su pantalla ni su celular.\n\n"
            "Las comisiones de la empleada sí siguen contando: su pago no cambia.",
        )
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


def confirmar_pago(parent: QWidget | None, *, employee_code: str, employee_name: str, creado_por: str, grande: bool = False, fecha=None):
    """Muestra el desglose del pago y, si confirma, lo registra. Devuelve EmpleadaPago o None.

    `fecha` permite pagar adelantado o registrar un pago que se hizo otro día:
    el ciclo se reinicia desde esa fecha y las comisiones se cuentan hasta ella."""
    from datetime import date as _date

    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.nomina_service import pago_pendiente, registrar_pago_con_monto

    fecha = fecha or _date.today()
    try:
        with get_session() as session:
            d = pago_pendiente(session, employee_code, fecha)
    except Exception:  # noqa: BLE001
        logger.exception("Pago: no se pudo calcular")
        QMessageBox.warning(parent, "Sin conexión", "No se alcanzó la base. Inténtalo otra vez.")
        return None
    desde = d.desde.strftime("%d/%m") if d.desde else "inicio"
    cuando = "" if fecha == _date.today() else f"Fecha del pago: {fecha:%d/%m/%Y}\n"
    base_txt = (
        f"{d.dias_trabajados} día(s) × ${d.tarifa_dia:,.2f}:  ${d.sueldo_base:,.2f}\n"
        if d.por_dia
        else f"Sueldo base:        ${d.sueldo_base:,.2f}\n"
    )
    texto = (
        f"{employee_name}\n"
        f"{cuando}"
        f"Periodo: {desde} → {d.hasta:%d/%m}\n\n"
        f"{base_txt}"
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
            pago = registrar_pago_con_monto(session, employee_code, creado_por=creado_por, fecha=fecha)
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
    retiro = (estado.resumen.efectivo - estado.pagos - total_pagos - estado.total_retiros).quantize(Decimal("0.01"))
    lineas = [f"VENTA: ${estado.resumen.efectivo:,.2f}"]
    if avisos:
        lineas.append("")
        lineas.append("PAGAR HOY:")
        for a in avisos:
            lineas.append(f"  {a.employee_name.split()[0]}  ${a.total_estimado:,.2f}")
    if estado.pagos:
        lineas.append(f"Pagos ya hechos: -${estado.pagos:,.2f}")
    if estado.total_retiros:
        lineas.append(f"Ya salió del cajón: -${estado.total_retiros:,.2f}")
    lineas.append("")
    lineas.append(f"SE RETIRA: ${retiro:,.2f}")
    lineas.append(f"Se queda de fondo: ${estado.reactivo:,.2f}")
    return "\n".join(lineas)


def hacer_corte_automatico(parent: QWidget | None, *, creado_por: str):
    """Corte de un botón para el encargado. Devuelve (CorteAutomatico, texto_ticket) o None."""
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.corte_caja_service import cerrar_corte_automatico, datos_ticket_encargado

    try:
        with get_session() as session:
            resultado = cerrar_corte_automatico(session, creado_por=creado_por)
            # Sin los movimientos privados del dueño (dinero, piezas y comisiones).
            datos = datos_ticket_encargado(session, resultado.estado.desde, resultado.estado.hasta)
            texto = texto_ticket_corte_encargado(
                resultado.corte,
                resultado.estado.resumen.efectivo,
                resultado.pagos,
                datos.por_empleada,
                retiros=datos.retiros,
                tarjeta=datos.tarjeta,
                tarjeta_ops=datos.tarjeta_ops,
                ya_pagados=pagos_previos_del_periodo(session, resultado),
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


def texto_ticket_corte_encargado(
    corte, venta_efectivo, pagos: list, por_empleada: list | None = None, retiros: list | None = None,
    reimpresion: bool = False, tarjeta=None, tarjeta_ops: int | None = None, ya_pagados: list | None = None,
) -> str:
    """Ticket simple para León: la cuenta (reactivo · venta · restas ·
    SACAR), a quién pagar con desglose y las comisiones.

    `pagos` = los que ESTE corte registra; `ya_pagados` = pagos hechos antes
    dentro del periodo (ya salieron del cajón): salen como YA PAGADO y se
    restan igual, para que nunca diga "no se paga a nadie" restando dinero."""
    from datetime import datetime

    _TW, tk_top, tk_mid, tk_dbl, tk_bot, tk_row, tk_line, _tk_field = _tk()
    pagos = list(pagos or [])
    ya_pagados = list(ya_pagados or [])
    sacar = (Decimal(corte.monto_final) - Decimal(corte.reactivo_final)).quantize(Decimal("0.01"))

    lines: list[str] = []
    lines.append("CORTE".center(_TW))
    lines.append(str(corte.periodo_label or "").center(_TW))
    if reimpresion and getattr(corte, "created_at", None):
        lines.append("* REIMPRESION *".center(_TW))
        lines.append(("Corte: " + _hora_local(corte.created_at).strftime("%d/%m/%Y %H:%M")).center(_TW))
    lines.append(datetime.now().strftime("%d/%m/%Y %H:%M").center(_TW))
    lines.append("")
    _bloque_cuenta(lines, corte=corte, venta=venta_efectivo, tarjeta=tarjeta, tarjeta_ops=tarjeta_ops,
                   pagos_restar=pagos + ya_pagados, retiros=retiros, sacar=sacar)
    _bloque_pagos(lines, pagos, ya_pagados, total=False)
    if por_empleada:
        lines.append("")
        lines.append("COMISIONES".center(_TW))
        lines.append(tk_top())
        first = True
        for r in por_empleada:
            if not first:
                lines.append(tk_mid())
            first = False
            lines.append(tk_row(f"{_nombre_pila(r)}:", f"{r.comisiones} com."))
        lines.append(tk_bot())
    return "\n".join(lines)


def apuntar_retiro(parent: QWidget | None, *, creado_por: str, grande: bool = False):
    """Saqué dinero del cajón: monto + motivo. Devuelve CajaRetiro o None."""
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.retiros_service import MOTIVOS_RAPIDOS, registrar_retiro

    dlg = QDialog(parent)
    dlg.setWindowTitle("Saqué dinero del cajón")
    ly = QVBoxLayout()
    ly.setContentsMargins(20, 18, 20, 18)
    ly.setSpacing(10)
    if grande:
        dlg.setStyleSheet("QDialog { background: #f4ede2; } QLabel { color: #2c2a27; font-size: 18px; }")
    ly.addWidget(QLabel("¿Cuánto sacaste?"))
    monto = _spin(Decimal("0.00"), grande)
    ly.addWidget(monto)
    ly.addWidget(QLabel("¿Para qué?"))
    motivo = QLineEdit()
    motivo.setPlaceholderText("Ej. Proveedor de playeras, renta, cambio...")
    if grande:
        motivo.setStyleSheet(_GRANDE)
    fila = QHBoxLayout()
    for m in MOTIVOS_RAPIDOS:
        b = QPushButton(m)
        b.setAutoDefault(False)
        b.clicked.connect(lambda _c=False, t=m: motivo.setText(t))
        if grande:
            b.setMinimumHeight(44)
            b.setStyleSheet("font-size: 16px; font-weight: 700;")
        fila.addWidget(b)
    ly.addLayout(fila)
    ly.addWidget(motivo)
    botones = QHBoxLayout()
    cancelar = QPushButton("Cancelar")
    cancelar.setAutoDefault(False)
    cancelar.clicked.connect(dlg.reject)
    ok = QPushButton("💸 Apuntar retiro")
    ok.setObjectName("primaryButton")
    ok.clicked.connect(dlg.accept)
    if grande:
        for b in (cancelar, ok):
            b.setMinimumHeight(52)
            b.setStyleSheet("font-size: 18px; font-weight: 700;")
    botones.addWidget(cancelar)
    botones.addWidget(ok, 1)
    ly.addLayout(botones)
    dlg.setLayout(ly)
    if grande:
        dlg.resize(560, 360)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    try:
        with get_session() as session:
            retiro = registrar_retiro(session, monto=Decimal(str(monto.value())), motivo=motivo.text(), creado_por=creado_por)
            session.refresh(retiro)
            session.expunge(retiro)
    except (ValueError, PermissionError) as exc:
        QMessageBox.warning(parent, "Retiro", str(exc))
        return None
    except Exception:  # noqa: BLE001
        logger.exception("Retiro: no se pudo guardar")
        QMessageBox.warning(parent, "No se guardó", "Inténtalo otra vez.")
        return None
    return retiro
