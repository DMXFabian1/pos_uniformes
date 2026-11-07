"""Diálogos de caja: hacer corte por periodo y editar reactivo/nómina.

Los usan el dueño (Libreta → Imprimir corte) y el encargado (su pantalla
grande). El corte muestra lo que debería haber en el cajón, pide lo contado
y cuánto se queda de fondo, guarda con `caja_service.cerrar_corte` e imprime.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from types import SimpleNamespace

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.corte_caja_service import EstadoCaja, diferencia
from pos_uniformes.services.nomina_service import OWNER_CODE
from pos_uniformes.services.nombres_empleadas_service import mostrar as _nombre_de
from pos_uniformes.services.nombres_empleadas_service import nombres_por_codigo

logger = logging.getLogger(__name__)

_GRANDE = "font-size: 22px; font-weight: 800; padding: 8px;"
_NORMAL = "font-size: 18px; font-weight: 700; padding: 6px;"


# La ventana de «Hacer corte» (rediseño 2026-11-06). Solo colores y formas;
# los tamaños de letra van en cada widget.
_ESTILO_CORTE = """
QDialog#corteDialog { background: #f4ede2; }
QDialog#corteDialog QLabel { color: #2c2a27; }
QDialog#corteDialog QScrollArea { background: transparent; border: none; }
QDialog#corteDialog QScrollArea > QWidget > QWidget { background: transparent; }
QDialog#corteDialog QLabel#cortePeriodo { color: #8a8177; font-size: 13px; }
QFrame#corteCifra { background: #fbf7f0; border: 1px solid #e6dccb; border-radius: 12px; }
QFrame#corteCifra[acento="true"] { background: #6b1f3a; border: none; }
QDialog#corteDialog QFrame#corteCifra[acento="true"] QLabel { color: #ffffff; }
QDialog#corteDialog QLabel#corteCifraTitulo { color: #8a8177; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
QDialog#corteDialog QFrame#corteCifra[acento="true"] QLabel#corteCifraTitulo { color: #e9cfd6; }
QDialog#corteDialog QLabel#corteCifraValor { font-size: 22px; font-weight: 800; }
QDialog#corteDialog QLabel#corteCifraPie { color: #8a8177; font-size: 12px; }
QFrame#corteCard { background: #fbf7f0; border: 1px solid #e6dccb; border-radius: 12px; }
QDialog#corteDialog QLabel#corteCardTitulo { color: #8a8177; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
QDialog#corteDialog QLabel#cortePregunta { font-size: 16px; font-weight: 700; }
QDialog#corteDialog QLabel#corteAviso { color: #8a8177; font-size: 13px; }
QDialog#corteDialog QLabel#corteAviso[estado="igual"] { color: #1c7c54; font-weight: 700; }
QDialog#corteDialog QLabel#corteAviso[estado="mas"], QLabel#corteAviso[estado="menos"] { color: #a35a00; font-weight: 700; }
QDoubleSpinBox#dinero, QLineEdit#corteTexto { background: #ffffff; color: #2c2a27; border: 1px solid #d9cdb8;
                                             border-radius: 10px; padding: 6px 12px; }
QDoubleSpinBox#dinero:focus, QLineEdit#corteTexto:focus { border: 2px solid #6b1f3a; }
QPushButton#corteMas { background: transparent; color: #6b1f3a; border: none; font-size: 14px;
                       font-weight: 700; text-align: left; padding: 6px 2px; }
QFrame#corteResultado { background: #e7f3ec; border: 1px solid #bfdccb; border-radius: 12px; }
QDialog#corteDialog QLabel#corteResultadoTitulo { color: #1c7c54; font-size: 12px; font-weight: 700; letter-spacing: 1px; }
QDialog#corteDialog QLabel#corteResultadoValor { color: #1c7c54; font-size: 30px; font-weight: 800; }
QDialog#corteDialog QLabel#corteResultadoPie { color: #2c2a27; font-size: 14px; }
QPushButton#cortePrimario { background: #8b4a2b; color: #ffffff; border: none; border-radius: 12px;
                            font-size: 17px; font-weight: 800; padding: 14px 20px; }
QPushButton#cortePrimario:hover { background: #a2583a; }
QPushButton#corteCancelar { background: #fbf7f0; color: #8b4a2b; border: 1px solid #e6dccb; border-radius: 12px;
                            font-size: 15px; font-weight: 700; padding: 14px 20px; }
"""


def _spin(valor: Decimal, grande: bool) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setObjectName("dinero")
    s.setRange(0.0, 9_999_999.0)
    s.setDecimals(2)
    s.setPrefix("$ ")
    s.setGroupSeparatorShown(True)
    s.setValue(float(valor))
    # Sin flechitas: nadie sube una venta de centavo en centavo. Se escribe.
    s.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    s.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    s.setStyleSheet(_GRANDE if grande else _NORMAL)
    return s


def _cifra(titulo: str, valor: str, pie: str = "", *, acento: bool = False) -> QFrame:
    """Una tarjeta chica con un número: ABRIÓ CON · VENTA · DEBE HABER."""
    caja = QFrame()
    caja.setObjectName("corteCifra")
    caja.setProperty("acento", "true" if acento else "false")
    ly = QVBoxLayout(caja)
    ly.setContentsMargins(14, 10, 14, 10)
    ly.setSpacing(2)
    t = QLabel(titulo.upper())
    t.setObjectName("corteCifraTitulo")
    v = QLabel(valor)
    v.setObjectName("corteCifraValor")
    ly.addWidget(t)
    ly.addWidget(v)
    if pie:
        p = QLabel(pie)
        p.setObjectName("corteCifraPie")
        ly.addWidget(p)
    return caja


def _card(titulo: str) -> tuple[QFrame, QVBoxLayout]:
    caja = QFrame()
    caja.setObjectName("corteCard")
    ly = QVBoxLayout(caja)
    ly.setContentsMargins(16, 12, 16, 14)
    ly.setSpacing(8)
    if titulo:
        t = QLabel(titulo.upper())
        t.setObjectName("corteCardTitulo")
        ly.addWidget(t)
    return caja, ly


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


def _bloque_cuenta(lines, *, corte, venta, tarjeta, tarjeta_ops, pagos_restar, retiros, sacar, tarjeta_neto=None, entradas=None) -> None:
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
        # Lo que LLEGA por la terminal (neto del 4.5%) es la cifra que manda
        # (Daniel 2026-09-14); lo cobrado no va en el papel.
        from pos_uniformes.services.libreta_service import aplicar_comision_terminal

        llega = Decimal(tarjeta_neto if tarjeta_neto is not None else aplicar_comision_terminal(tarjeta_monto)).quantize(Decimal("0.01"))
        cuantas = f" ({tarjeta_ops})" if tarjeta_ops else ""
        lines.append(tk_row(f"Tarjeta, llega{cuantas}:", f"${llega:,.2f}"))
        lines.append(tk_row("VENTA TOTAL:", f"${(venta + llega):,.2f}"))
        lines.append(tk_line("  (la tarjeta no esta en el cajon)"))
    entradas = list(entradas or [])
    restas = list(pagos_restar or []) or list(retiros or []) or entradas
    if restas:
        lines.append(tk_mid())
        lines.append(tk_row("Venta en efectivo:", f"${venta:,.2f}"))
        # Lo que entró sin ser venta (el fondo de papá para la nómina) se
        # suma antes de restar los pagos: los pagos salen completos del cajón
        # y aquí se ve de dónde salieron (2026-10-20).
        for e in entradas:
            lines.append(tk_row(f"Entro ({str(e.motivo)[: _TW - 24]}):", f"+${Decimal(e.monto):,.2f}"))
        for p in pagos_restar or []:
            lines.append(tk_row(f"Pago a {_nombre_pila(p)}:"[: _TW - 14], f"-${Decimal(p.total):,.2f}"))
        for r in retiros or []:
            lines.append(tk_row(f"Gasto ({str(r.motivo)[: _TW - 24]}):", f"-${Decimal(r.monto):,.2f}"))
    if con_reactivo:
        lines.append(tk_dbl())
        lines.append(tk_row("SACAR DE LA VENTA:", f"${Decimal(sacar):,.2f}"))
    if entradas and pagos_restar:
        entro = sum((Decimal(e.monto) for e in entradas), Decimal("0.00"))
        pagos_total = sum((Decimal(p.total) for p in pagos_restar), Decimal("0.00"))
        cubierto = min(entro, pagos_total)
        if cubierto > 0:
            lines.append(tk_line(f"  (de los pagos, ${cubierto:,.2f} salio"))
            lines.append(tk_line("   de lo que entro, no de venta)"))
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


def texto_ticket_corte(corte, por_empleada: list | None = None, *, pagos: list | None = None, venta_efectivo=None, retiros: list | None = None, reimpresion: bool = False, tarjeta=None, tarjeta_ops: int | None = None, tarjeta_neto=None, entradas: list | None = None) -> str:
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
        tk_field("Por:", _nombre_de(corte.creado_por), lines)
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
    _bloque_cuenta(lines, corte=corte, venta=venta, tarjeta=tarjeta, tarjeta_ops=tarjeta_ops, pagos_restar=pagos_restar, retiros=gastos_restar, sacar=sacar, tarjeta_neto=tarjeta_neto, entradas=entradas)
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
            lines.append(tk_line(_nombre_de(r.employee_name or r.employee_code)[: _TW - 4]))
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


def contado_desde_venta(estado: EstadoCaja, venta: Decimal, otros_retiros: Decimal) -> Decimal:
    """Lo que debe quedar en el cajón si la venta en efectivo fue `venta`.

    reactivo + venta + entradas (no venta) − pagos ya hechos − retiros
    apuntados − otros retiros. (Puro para poder probarlo.)"""
    total = (
        Decimal(estado.reactivo)
        + Decimal(venta)
        + Decimal(getattr(estado, "entradas", 0) or 0)
        - Decimal(estado.pagos)
        - Decimal(estado.retiros)
        - Decimal(otros_retiros or 0)
    )
    return max(total, Decimal("0.00")).quantize(Decimal("0.01"))


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
    # El préstamo sí se restaba del total pero no salía en el papel: la cuenta
    # del ticket no cerraba a simple vista (Daniel, 2026-10-26).
    prestamo = Decimal(getattr(p, "descuento_prestamos", 0) or 0)
    if prestamo:
        lines.append(tk_row("  Prestamo:", f"-${prestamo:,.2f}"))


def texto_estado_caja(estado: EstadoCaja) -> str:
    r = estado.resumen
    partes = [
        f"Periodo: {_periodo(estado)}",
        f"Fondo (reactivo) con que abrió: ${estado.reactivo:,.2f}",
        f"VENTA EN EFECTIVO: ${r.efectivo:,.2f}   ({r.operaciones} operaciones)",
    ]
    if r.tarjeta:
        partes.append(f"Con tarjeta llega ${r.tarjeta_neto:,.2f} (cobrado ${r.tarjeta:,.2f}; no está en el cajón)")
    if estado.entradas:
        partes.append(f"Entró al cajón sin ser venta (fondo de papá...): +${estado.entradas:,.2f}")
    if estado.pagos:
        partes.append(f"Pagos a empleadas ya hechos: -${estado.pagos:,.2f}")
    if estado.retiros:
        partes.append(f"Retiros apuntados (proveedor, renta...): -${estado.retiros:,.2f}")
    partes.append(f"En el cajón debe haber: ${estado.esperado:,.2f}")
    return "\n".join(partes)


def texto_estado_caja_sin_totales(estado: EstadoCaja) -> str:
    """El encabezado del corte cuando los pagos y retiros van desglosados abajo."""
    r = estado.resumen
    partes = [
        f"Periodo: {_periodo(estado)}",
        f"Fondo (reactivo) con que abrió: ${estado.reactivo:,.2f}",
        f"VENTA EN EFECTIVO: ${r.efectivo:,.2f}   ({r.operaciones} operaciones)",
    ]
    if r.tarjeta:
        partes.append(f"Con tarjeta llega ${r.tarjeta_neto:,.2f} (cobrado ${r.tarjeta:,.2f}; no está en el cajón)")
    if estado.entradas:
        partes.append(f"Entró al cajón sin ser venta (fondo de papá...): +${estado.entradas:,.2f}")
    return "\n".join(partes)


def _cuando(momento) -> str:
    if momento is None:
        return ""
    m = momento.astimezone() if getattr(momento, "tzinfo", None) else momento
    return m.strftime("%d/%m %H:%M")


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
            nombres_por_codigo(session)
            estado = estado_caja(session)
            rows = operaciones_del_periodo(session, estado.desde, estado.hasta)
            por_empleada = resumir_por_empleada(rows)
            from pos_uniformes.services.corte_caja_service import cargar_parametros, pagos_que_tocan_hoy

            parametros = cargar_parametros(session)
            # Lo que YA salió del cajón en el periodo, uno por uno: Daniel
            # desmarca lo que no salió (2026-09-18: "el pago a Evelyn lo hice
            # ayer, así que no tomé el dinero hoy, pero los otros gastos sí").
            from pos_uniformes.services.retiros_service import retiros_del_periodo

            pagos_hechos = [
                (p.id, _nombre_de(p.employee_name or p.employee_code, corto=True), Decimal(p.total), _cuando(p.created_at), bool(p.en_cajon))
                for p in pagos_registrados_del_periodo(session, estado.desde, estado.hasta, solo_en_cajon=False)
            ]
            try:
                retiros_hechos = [
                    (r.id, str(r.motivo or "Retiro"), Decimal(r.monto), _cuando(r.created_at), bool(r.en_cajon))
                    for r in retiros_del_periodo(session, estado.desde, estado.hasta, solo_en_cajon=False)
                ]
            except Exception:  # noqa: BLE001
                session.rollback()
                retiros_hechos = []
            try:
                from pos_uniformes.services.entradas_service import entradas_del_periodo

                entradas_hechas = [
                    (str(e.motivo or "Entrada"), Decimal(e.monto), _cuando(e.created_at))
                    for e in entradas_del_periodo(session, estado.desde, estado.hasta)
                ]
            except Exception:  # noqa: BLE001 — base sin la tabla todavía
                session.rollback()
                entradas_hechas = []
            # Los pagos que caen hoy y nadie ha registrado: se ofrecen aquí
            # mismo (Daniel 2026-09-13: "al hacer corte no me descontó los pagos").
            try:
                avisos_hoy = pagos_que_tocan_hoy(session, estado.hasta.date())
            except Exception:  # noqa: BLE001
                session.rollback()
                avisos_hoy = []
    except Exception:  # noqa: BLE001
        logger.exception("Corte: no se pudo calcular el estado de caja")
        QMessageBox.warning(parent, "Sin conexión", "No se alcanzó la base. Inténtalo otra vez.")
        return None

    # ── La ventana (rediseño 2026-11-06: «necesito que mejoremos esta ventana») ──
    # Antes: un bloque de texto, cuatro cajas negras con flechitas y todo al
    # mismo nivel. Ahora: las tres cifras arriba, UNA pregunta grande (la venta)
    # con su respuesta en vivo, el fondo, lo raro plegado en «Más opciones» y
    # abajo, en grande, lo que queda en el cajón. Nada se quitó.
    dlg = QDialog(parent)
    dlg.setObjectName("corteDialog")
    dlg.setWindowTitle("Hacer corte")
    dlg.setStyleSheet(_ESTILO_CORTE)
    tam_etiqueta = "font-size: 16px;" if grande else "font-size: 14px;"

    cuerpo = QWidget()
    ly = QVBoxLayout(cuerpo)
    ly.setContentsMargins(22, 18, 22, 10)
    ly.setSpacing(12)

    periodo = QLabel(f"Periodo: {_periodo(estado)}")
    periodo.setObjectName("cortePeriodo")
    ly.addWidget(periodo)

    r = estado.resumen
    cifras = QHBoxLayout()
    cifras.setSpacing(10)
    cifras.addWidget(_cifra("Abrió con", f"${estado.reactivo:,.2f}", "fondo (reactivo)"), 1)
    cifras.addWidget(_cifra(
        "Venta en efectivo", f"${r.efectivo:,.2f}",
        f"{r.operaciones} operación{'es' if r.operaciones != 1 else ''}",
    ), 1)
    cifra_esperado = _cifra("Debe haber en el cajón", f"${estado.esperado:,.2f}", acento=True)
    cifras.addWidget(cifra_esperado, 1)
    ly.addLayout(cifras)
    notas_arriba = []
    if r.tarjeta:
        notas_arriba.append(
            f"💳 Con tarjeta llega ${r.tarjeta_neto:,.2f} (cobrado ${r.tarjeta:,.2f}); no está en el cajón."
        )
    if estado.entradas and not entradas_hechas:
        notas_arriba.append(f"➕ Entró al cajón sin ser venta: ${estado.entradas:,.2f}")
    if not (pagos_hechos or retiros_hechos):
        if estado.pagos:
            notas_arriba.append(f"Pagos a empleadas ya hechos: −${estado.pagos:,.2f}")
        if estado.retiros:
            notas_arriba.append(f"Retiros apuntados: −${estado.retiros:,.2f}")
    for texto_nota in notas_arriba:
        n = QLabel(texto_nota)
        n.setObjectName("corteAviso")
        n.setWordWrap(True)
        ly.addWidget(n)

    # Desglose de lo que ya salió: marcado = salió del cajón en este periodo.
    casillas_hechos: list[tuple[QCheckBox, str, int, Decimal]] = []   # (casilla, "pago"/"retiro", id, monto)
    esperado_lbl = None
    if pagos_hechos or retiros_hechos or entradas_hechas:
        card, cly = _card("Lo que ya salió del cajón en este periodo")
        pista = QLabel("Marcado = salió de este cajón. Desmarca lo que se pagó con otro dinero.")
        pista.setObjectName("corteAviso")
        pista.setWordWrap(True)
        cly.addWidget(pista)
        for filas, tipo in ((pagos_hechos, "pago"), (retiros_hechos, "retiro")):
            for rid, quien, monto, cuando, en_cajon in filas:
                # El nombre va primero (las pruebas y la vista lo buscan así).
                cb = QCheckBox(f"{quien}  ·  ${monto:,.2f}  ·  {cuando}")
                cb.setToolTip("Pago a empleada" if tipo == "pago" else "Retiro apuntado")
                cb.setChecked(en_cajon)
                cb.setProperty("en_cajon_inicial", en_cajon)
                cb.setStyleSheet(tam_etiqueta)
                cly.addWidget(cb)
                casillas_hechos.append((cb, tipo, rid, monto))
        for motivo_e, monto_e, cuando_e in entradas_hechas:
            lbl_e = QLabel(f"➕ Entró ({motivo_e})  ·  ${monto_e:,.2f}  ·  {cuando_e}")
            lbl_e.setStyleSheet(tam_etiqueta)
            cly.addWidget(lbl_e)
        if pagos_hechos or retiros_hechos:
            esperado_lbl = QLabel("")
            esperado_lbl.setObjectName("corteAviso")
            esperado_lbl.setWordWrap(True)
            cly.addWidget(esperado_lbl)
        ly.addWidget(card)

    # Pagos que tocan hoy: marcados = "ya le pagué del cajón", se registran
    # al guardar y se restan de lo que debe quedar.
    casillas_pago: list[tuple[QCheckBox, object]] = []
    if avisos_hoy:
        card, cly = _card("Pagos que tocan hoy")
        pista = QLabel("Marca los que salieron del cajón; se registran al guardar el corte.")
        pista.setObjectName("corteAviso")
        pista.setWordWrap(True)
        cly.addWidget(pista)
        for aviso in avisos_hoy:
            nombre = _nombre_de(aviso.employee_name or aviso.employee_code, corto=True)
            cb = QCheckBox(f"{nombre}  ·  ${Decimal(aviso.total_estimado):,.2f}  ({aviso.comisiones} comisiones)")
            cb.setChecked(True)
            cb.setStyleSheet(tam_etiqueta)
            cly.addWidget(cb)
            casillas_pago.append((cb, aviso))
        ly.addWidget(card)

    # La pregunta: se pregunta por la VENTA (Daniel 2026-09-10), es la cifra
    # con la que se razona el corte. Lo que debe haber en el cajón se calcula.
    card, cly = _card("")
    pregunta = QLabel("¿Cuánto se vendió en efectivo?")
    pregunta.setObjectName("cortePregunta")
    cly.addWidget(pregunta)
    venta = _spin(estado.resumen.efectivo, True)
    venta.setMinimumHeight(52)
    cly.addWidget(venta)
    dif = QLabel("")
    dif.setObjectName("corteAviso")
    dif.setWordWrap(True)
    cly.addWidget(dif)
    fondo_fila = QHBoxLayout()
    fondo_lbl = QLabel("Se queda de fondo para mañana")
    fondo_lbl.setStyleSheet(tam_etiqueta)
    fondo_fila.addWidget(fondo_lbl, 1)
    fondo = _spin(estado.reactivo, False)
    fondo.setFixedWidth(190)
    fondo_fila.addWidget(fondo)
    cly.addLayout(fondo_fila)
    ly.addWidget(card)

    # Lo que casi nunca se usa, plegado: no estorba y sigue a un toque.
    from pos_uniformes.services.entradas_service import MOTIVO_POR_DEFECTO

    mas_btn = QPushButton("▸  Más opciones  (otros retiros, dinero que entró, nota)")
    mas_btn.setObjectName("corteMas")
    mas_btn.setAutoDefault(False)
    mas_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    ly.addWidget(mas_btn)
    mas_card, mly = _card("Más opciones")
    form = QFormLayout()
    form.setHorizontalSpacing(14)
    form.setVerticalSpacing(10)
    otros = _spin(Decimal("0.00"), False)
    form.addRow("Otros retiros que salieron hoy:", otros)
    # Lo que papá dejó para la nómina: entra al cajón, los pagos salen
    # completos y el sobrante se queda (Daniel, 2026-10-20).
    entro = _spin(Decimal("0.00"), False)
    form.addRow("Entró dinero que no es venta:", entro)
    entro_motivo = QLineEdit()
    entro_motivo.setObjectName("corteTexto")
    entro_motivo.setPlaceholderText(MOTIVO_POR_DEFECTO)
    form.addRow("¿De dónde entró?", entro_motivo)
    nota = QLineEdit()
    nota.setObjectName("corteTexto")
    nota.setPlaceholderText("Algo que quieras dejar escrito en el corte")
    form.addRow("Nota:", nota)
    for i_fila in range(form.rowCount()):
        etiqueta = form.itemAt(i_fila, QFormLayout.ItemRole.LabelRole)
        if etiqueta is not None and etiqueta.widget() is not None:
            etiqueta.widget().setStyleSheet(tam_etiqueta)
    mly.addLayout(form)
    # Solo Daniel: dejar el papel sin la linea "Con tarjeta". Es por corte
    # (arranca apagada); en pantalla la sigue viendo.
    sin_tarjeta = QCheckBox("Ocultar los cobros con tarjeta (no salen en el ticket)")
    # Llega como la dejó la última vez (2026-09-10).
    sin_tarjeta.setChecked(bool(getattr(parametros, "ocultar_tarjeta", False)))
    sin_tarjeta.setVisible(str(creado_por or "").strip().upper() == OWNER_CODE)
    sin_tarjeta.setStyleSheet(tam_etiqueta)
    mly.addWidget(sin_tarjeta)
    mas_card.setVisible(False)
    ly.addWidget(mas_card)

    def _alternar_mas() -> None:
        abrir = not mas_card.isVisible()
        mas_card.setVisible(abrir)
        mas_btn.setText(
            "▾  Menos opciones" if abrir
            else "▸  Más opciones  (otros retiros, dinero que entró, nota)"
        )

    mas_btn.clicked.connect(_alternar_mas)
    dlg.mas_opciones = mas_card        # para las pruebas
    dlg.mas_btn = mas_btn

    # Abajo, en grande: lo que queda en el cajón.
    resultado = QFrame()
    resultado.setObjectName("corteResultado")
    rly = QGridLayout(resultado)
    rly.setContentsMargins(16, 12, 16, 12)
    rly.setHorizontalSpacing(16)
    res_titulo = QLabel("EN EL CAJÓN QUEDAN")
    res_titulo.setObjectName("corteResultadoTitulo")
    res_valor = QLabel("")
    res_valor.setObjectName("corteResultadoValor")
    res_pie = QLabel("")
    res_pie.setObjectName("corteResultadoPie")
    res_pie.setWordWrap(True)
    res_pie.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    rly.addWidget(res_titulo, 0, 0)
    rly.addWidget(res_valor, 1, 0)
    rly.addWidget(res_pie, 0, 1, 2, 1)
    rly.setColumnStretch(1, 1)
    dlg.resultado_valor = res_valor    # para las pruebas
    dlg.resultado_pie = res_pie
    dlg.aviso_venta = dif

    def _pagos_marcados() -> list:
        return [a for cb, a in casillas_pago if cb.isChecked()]

    def _fuera_del_cajon() -> tuple[list[int], list[int], Decimal]:
        """(pagos desmarcados, retiros desmarcados, cuánto NO se resta)."""
        pagos_ids, retiros_ids, monto = [], [], Decimal("0.00")
        for cb, tipo, rid, m in casillas_hechos:
            if cb.isChecked():
                continue
            (pagos_ids if tipo == "pago" else retiros_ids).append(rid)
            monto += m
        return pagos_ids, retiros_ids, monto.quantize(Decimal("0.01"))

    def _dentro_del_cajon() -> tuple[list[int], list[int]]:
        pagos_ids = [rid for cb, tipo, rid, _m in casillas_hechos if cb.isChecked() and tipo == "pago"]
        retiros_ids = [rid for cb, tipo, rid, _m in casillas_hechos if cb.isChecked() and tipo == "retiro"]
        return pagos_ids, retiros_ids

    def _contado() -> Decimal:
        """Lo que queda en el cajón con la venta capturada."""
        base = contado_desde_venta(
            estado, Decimal(str(venta.value())), Decimal(str(otros.value()))
        )
        pagos_nuevos = sum((Decimal(a.total_estimado) for a in _pagos_marcados()), Decimal("0.00"))
        base += Decimal(str(entro.value()))
        # `estado` ya viene con lo guardado en la base; aquí solo se corrige lo
        # que Daniel cambió en las casillas: lo que desmarcó nunca salió de
        # aquí (se regresa) y lo que volvió a marcar sí salió (se resta).
        regresa = sum((m for cb, _t, _i, m in casillas_hechos if not cb.isChecked() and cb.property("en_cajon_inicial")), Decimal("0.00"))
        resta = sum((m for cb, _t, _i, m in casillas_hechos if cb.isChecked() and not cb.property("en_cajon_inicial")), Decimal("0.00"))
        return max(base - pagos_nuevos + regresa - resta, Decimal("0.00")).quantize(Decimal("0.01"))

    def _refrescar_dif() -> None:
        v = Decimal(str(venta.value())).quantize(Decimal("0.01"))
        d = diferencia(v, estado.resumen.efectivo)
        if esperado_lbl is not None:
            _p, _r, no_salio = _fuera_del_cajon()
            marcados = sum((m for cb, _t, _i, m in casillas_hechos if cb.isChecked()), Decimal("0.00"))
            entradas_total = Decimal(getattr(estado, "entradas", 0) or 0) + Decimal(str(entro.value()))
            esperado_lbl.setText(
                (f"Entró sin ser venta: +${entradas_total:,.2f}\n" if entradas_total else "")
                + f"Salió del cajón en este periodo: −${marcados:,.2f}"
                + (f"  (no se resta ${no_salio:,.2f} que no salió de aquí)" if no_salio else "")
            )
            cifra_esperado.findChild(QLabel, "corteCifraValor").setText(
                f"${(estado.reactivo + estado.resumen.efectivo + entradas_total - marcados):,.2f}"
            )
        if d == 0:
            dif.setText("✅ Es la venta registrada.")
            dif.setProperty("estado", "igual")
        elif d > 0:
            dif.setText(f"${d:,.2f} más que lo registrado (${estado.resumen.efectivo:,.2f}).")
            dif.setProperty("estado", "mas")
        else:
            dif.setText(f"${-d:,.2f} menos que lo registrado (${estado.resumen.efectivo:,.2f}).")
            dif.setProperty("estado", "menos")
        dif.style().unpolish(dif)
        dif.style().polish(dif)
        queda = _contado()
        res_valor.setText(f"${queda:,.2f}")
        sacar = max(queda - Decimal(str(fondo.value())), Decimal("0.00")).quantize(Decimal("0.01"))
        res_pie.setText(
            f"Se saca de la venta: ${sacar:,.2f}\n"
            f"Se queda de fondo: ${Decimal(str(fondo.value())):,.2f}"
        )

    venta.valueChanged.connect(lambda _v: _refrescar_dif())
    fondo.valueChanged.connect(lambda _v: _refrescar_dif())
    otros.valueChanged.connect(lambda _v: _refrescar_dif())
    entro.valueChanged.connect(lambda _v: _refrescar_dif())
    for cb, _a in casillas_pago:
        cb.toggled.connect(lambda _v: _refrescar_dif())
    for cb, _t, _i, _m in casillas_hechos:
        cb.toggled.connect(lambda _v: _refrescar_dif())
    _refrescar_dif()

    # Con muchos pagos o retiros la ventana crecía más que la pantalla: el
    # cuerpo scrollea y los botones se quedan siempre a la vista.
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(cuerpo)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    raiz = QVBoxLayout(dlg)
    raiz.setContentsMargins(0, 0, 0, 0)
    raiz.setSpacing(0)
    raiz.addWidget(area, 1)
    # El resultado va FUERA del scroll: con muchos pagos arriba, lo que queda
    # en el cajón y los botones se quedan siempre a la vista.
    pie_fijo = QVBoxLayout()
    pie_fijo.setContentsMargins(22, 6, 22, 0)
    pie_fijo.addWidget(resultado)
    raiz.addLayout(pie_fijo)
    botones = QHBoxLayout()
    botones.setContentsMargins(22, 8, 22, 18)
    botones.setSpacing(10)
    cancelar = QPushButton("Cancelar")
    cancelar.setObjectName("corteCancelar")
    cancelar.setAutoDefault(False)
    cancelar.clicked.connect(dlg.reject)
    botones.addWidget(cancelar)
    ok = QPushButton("🖨  Guardar e imprimir corte")
    ok.setObjectName("cortePrimario")
    ok.setDefault(True)
    ok.clicked.connect(dlg.accept)
    botones.addWidget(ok, 1)
    raiz.addLayout(botones)
    dlg.resize(640, 720 if (casillas_hechos or casillas_pago) else 600)
    venta.setFocus()
    venta.selectAll()
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None

    try:
        with get_session() as session:
            # Primero los pagos marcados, con la hora del corte para que caigan
            # DENTRO del periodo que se cierra (mismo cuidado que el corte automático).
            from pos_uniformes.services.nomina_service import registrar_pago_con_monto

            for aviso in _pagos_marcados():
                registrar_pago_con_monto(
                    session, aviso.employee_code, creado_por=creado_por,
                    fecha=estado.hasta.date(), momento=estado.hasta,
                )
            if Decimal(str(entro.value())) > 0:
                from pos_uniformes.services.entradas_service import registrar_entrada

                registrar_entrada(
                    session, monto=Decimal(str(entro.value())), motivo=entro_motivo.text(),
                    creado_por=creado_por, momento=estado.hasta,
                )
            # Lo que Daniel desmarcó no salió del cajón: queda anotado y el
            # esperado del corte se calcula sin eso (y al revés si volvió a marcar).
            from pos_uniformes.services.corte_caja_service import marcar_fuera_del_cajon

            fuera_p, fuera_r, _no_salio = _fuera_del_cajon()
            marcar_fuera_del_cajon(session, pagos_ids=fuera_p, retiros_ids=fuera_r, en_cajon=False)
            dentro_p, dentro_r = _dentro_del_cajon()
            marcar_fuera_del_cajon(session, pagos_ids=dentro_p, retiros_ids=dentro_r, en_cajon=True)
            corte = cerrar_corte(
                session,
                contado=_contado(),
                reactivo_final=Decimal(str(fondo.value())),
                otros_retiros=Decimal(str(otros.value())),
                nota=nota.text(),
                creado_por=creado_por,
                ahora=estado.hasta,
            )
            from pos_uniformes.services.corte_caja_service import recordar_ocultar_tarjeta

            recordar_ocultar_tarjeta(session, sin_tarjeta.isChecked())
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
            try:
                from pos_uniformes.services.entradas_service import entradas_del_periodo

                entradas_periodo = entradas_del_periodo(session, estado.desde, estado.hasta)
            except Exception:  # noqa: BLE001
                session.rollback()
                entradas_periodo = []
            # Formato por defecto: el ticket SIMPLE (Daniel 2026-09-10), el
            # mismo que sale del encargado y de /corte. El completo (con
            # operaciones por empleada) se saca desde 🧾 Cortes.
            texto = texto_ticket_corte_encargado(
                corte,
                Decimal(str(venta.value())),          # la venta que se reporta
                [],                                    # este corte no registra pagos
                por_empleada,
                retiros=retiros_periodo,
                tarjeta=None if sin_tarjeta.isChecked() else estado.resumen.tarjeta,
                tarjeta_ops=None if sin_tarjeta.isChecked() else contar_tarjeta(rows),
                tarjeta_neto=None if sin_tarjeta.isChecked() else estado.resumen.tarjeta_neto,
                ya_pagados=pagos_periodo,              # los del periodo ya salieron del cajón
                entradas=entradas_periodo,
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

        from pos_uniformes.database.models import TipoTrabajo

        route_tickets(parent, "Corte de caja", [texto], tipo=TipoTrabajo.CORTE)
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
        # El préstamo SE TIENE que ver: ya venía restado del total, así que sin
        # esta línea el pago aparecía más chico sin decir por qué, y eso se lee
        # como un error del programa (Daniel, 2026-10-04).
        + (f"Préstamo:           -${d.prestamo_cubierto:,.2f}\n" if d.prestamo_cubierto else "")
        + f"\nA PAGAR:  ${d.total:,.2f}"
        + (
            f"\n\nLe siguen quedando ${d.prestamo_sin_cubrir:,.2f} del préstamo\n"
            "para el próximo pago."
            if d.prestamo_sin_cubrir
            else ""
        )
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
    entradas = Decimal(getattr(estado, "entradas", 0) or 0)
    retiro = (estado.resumen.efectivo + entradas - estado.pagos - total_pagos - estado.total_retiros).quantize(Decimal("0.01"))
    lineas = [f"VENTA: ${estado.resumen.efectivo:,.2f}"]
    if entradas:
        lineas.append(f"Entró sin ser venta: +${entradas:,.2f}")
    if avisos:
        lineas.append("")
        lineas.append("PAGAR HOY:")
        for a in avisos:
            prest = Decimal(getattr(a, "prestamos", 0) or 0)
            resta = f"  (ya sin ${prest:,.2f} del préstamo)" if prest else ""
            lineas.append(f"  {a.employee_name.split()[0]}  ${a.total_estimado:,.2f}{resta}")
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
                tarjeta_neto=getattr(datos, "tarjeta_neto", None),
                ya_pagados=pagos_previos_del_periodo(session, resultado),
            )
    except Exception:  # noqa: BLE001
        logger.exception("Corte automático: no se pudo guardar")
        QMessageBox.warning(parent, "No se guardó", "Inténtalo otra vez.")
        return None
    try:
        from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets

        from pos_uniformes.database.models import TipoTrabajo

        route_tickets(parent, "Corte de caja", [texto], tipo=TipoTrabajo.CORTE)
    except Exception:  # noqa: BLE001 — el corte ya quedó guardado
        logger.exception("Corte automático: falló la impresión")
    return resultado, texto


def texto_ticket_corte_encargado(
    corte, venta_efectivo, pagos: list, por_empleada: list | None = None, retiros: list | None = None,
    reimpresion: bool = False, tarjeta=None, tarjeta_ops: int | None = None, ya_pagados: list | None = None, tarjeta_neto=None,
    entradas: list | None = None,
) -> str:
    """Ticket simple para el encargado: la cuenta (reactivo · venta · restas ·
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
    _bloque_cuenta(lines, corte=corte, venta=venta_efectivo, tarjeta=tarjeta, tarjeta_ops=tarjeta_ops, tarjeta_neto=tarjeta_neto,
                   pagos_restar=pagos + ya_pagados, retiros=retiros, sacar=sacar, entradas=entradas)
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
