"""Ticket térmico del corte de la Libreta (vista del dueño).

Un solo botón imprime el cierre del periodo: EN CAJA, ventas
efectivo/tarjeta, apartados, abonos y el desglose por empleada — el cierre
físico del día para archivar.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

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


def build_corte_ticket_text(
    *,
    periodo_label: str,
    cortes: list,
    por_empleada: list,
    generado_por: str = "",
    efectivo_real: Decimal | None = None,
    nota: str = "",
) -> str:
    """Arma el texto del ticket de corte con los agregados ya calculados
    (CorteDia y ResumenEmpleada de libreta_service)."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    total_en_caja = sum((c.monto_en_caja for c in cortes), Decimal("0.00"))
    total_ventas = sum((c.monto_ventas for c in cortes), Decimal("0.00"))
    total_neto = sum((c.monto_neto_ventas for c in cortes), Decimal("0.00"))
    total_apartados = sum((c.monto_apartados for c in cortes), Decimal("0.00"))
    total_abonos = sum((c.monto_abonos for c in cortes), Decimal("0.00"))
    total_piezas = sum(c.piezas for c in cortes)
    total_ops = sum(c.operaciones for c in cortes)

    lines: list[str] = []
    lines.append("CORTE DE LIBRETA".center(_TW))
    lines.append(periodo_label.center(_TW))

    lines.append(tk_top())
    tk_field("Impreso:", now, lines)
    if generado_por:
        tk_field("Por:", generado_por, lines)
    lines.append(tk_mid())
    lines.append(tk_row("Operaciones:", str(total_ops)))
    lines.append(tk_row("Piezas:", str(total_piezas)))
    lines.append(tk_mid())
    lines.append(tk_row("Ventas:", f"${total_ventas:,.2f}"))
    lines.append(tk_row("Neto (tras tarjeta):", f"${total_neto:,.2f}"))
    lines.append(tk_row("Apartados:", f"${total_apartados:,.2f}"))
    lines.append(tk_row("Abonos:", f"${total_abonos:,.2f}"))
    lines.append(tk_dbl())
    lines.append(tk_row("EN CAJA (esperado):", f"${total_en_caja:,.2f}"))
    if efectivo_real is not None:
        # El cierre formal: lo contado de verdad y la diferencia — solo el
        # dueño puede capturar/editar este número (la barra es suya).
        lines.append(tk_row("CONTADO REAL:", f"${efectivo_real:,.2f}"))
        diferencia = efectivo_real - total_en_caja
        if diferencia == 0:
            lines.append(tk_row("DIFERENCIA:", "$0.00 OK"))
        elif diferencia > 0:
            lines.append(tk_row("SOBRANTE:", f"${diferencia:,.2f}"))
        else:
            lines.append(tk_row("FALTANTE:", f"${-diferencia:,.2f}"))
    if nota:
        tk_field("Nota:", nota, lines)
    lines.append(tk_bot())

    if len(cortes) > 1:
        lines.append("")
        lines.append("POR DIA".center(_TW))
        lines.append(tk_top())
        for corte in cortes:
            lines.append(tk_row(f"{corte.dia_label}:", f"${corte.monto_en_caja:,.2f}"))
        lines.append(tk_bot())

    if por_empleada:
        lines.append("")
        lines.append("POR EMPLEADA".center(_TW))
        lines.append(tk_top())
        first = True
        for resumen in por_empleada:
            if not first:
                lines.append(tk_mid())
            first = False
            nombre = resumen.employee_name or resumen.employee_code
            lines.append(tk_line(nombre[: _TW - 4]))
            lines.append(
                tk_row(
                    f"{resumen.operaciones} ops · {resumen.piezas} pzas:",
                    f"{resumen.comisiones} com.",
                )
            )
            lines.append(tk_row("Monto:", f"${resumen.monto_total:,.2f}"))
        lines.append(tk_bot())

    lines.append("")
    lines.append("Corte generado por la Libreta.".center(_TW))
    return "\n".join(lines)
