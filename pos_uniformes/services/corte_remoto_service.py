"""Ejecutar el corte "a distancia": lo pide Daniel por Telegram (/corte) o la
tarea programada. Hace el corte automático, encola el ticket del encargado a
la impresora de la tienda y devuelve el texto para responder.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class ResultadoCorte:
    hecho: bool
    mensaje: str
    impreso: bool = False


def texto_estado_actual(session, ahora: datetime | None = None) -> str:
    """Qué hay en caja ahora mismo (para /estado)."""
    from pos_uniformes.services.corte_caja_service import estado_caja, pagos_que_tocan_hoy

    ahora = ahora or datetime.now().astimezone()
    e = estado_caja(session, ahora)
    avisos = pagos_que_tocan_hoy(session, ahora.date())
    desde = f"desde {e.desde.astimezone():%d/%m %H:%M}" if e.desde else "sin corte previo"
    lineas = [
        f"💰 Caja ahora ({ahora:%d/%m %H:%M}, {desde})",
        f"• Venta efectivo: ${e.resumen.efectivo:,.2f} ({e.resumen.operaciones} ops)",
    ]
    if e.resumen.tarjeta:
        lineas.append(f"• Tarjeta: ${e.resumen.tarjeta:,.2f}")
    if e.pagos:
        lineas.append(f"• Pagos ya hechos: -${e.pagos:,.2f}")
    if e.total_retiros:
        lineas.append(f"• Retiros apuntados: -${e.total_retiros:,.2f}")
    if avisos:
        lineas.append("• Pagos que tocan hoy: " + ", ".join(f"{a.employee_name.split()[0]} ${a.total_estimado:,.2f}" for a in avisos))
    lineas.append(f"• Reactivo: ${e.reactivo:,.2f} · Debe haber: ${e.esperado:,.2f}")
    return "\n".join(lineas)


def hacer_corte_y_avisar(session, *, creado_por: str, ahora: datetime | None = None) -> ResultadoCorte:
    """Corte automático + ticket a la impresora. Devuelve el mensaje para Telegram."""
    from pos_uniformes.services import trabajos_service
    from pos_uniformes.services.corte_caja_service import (
        cerrar_corte_automatico,
        estado_caja,
        operaciones_del_periodo,
        pagos_que_tocan_hoy,
    )
    from pos_uniformes.services.libreta_service import resumir_por_empleada
    from pos_uniformes.ui.dialogs.corte_caja_dialog import contar_tarjeta, pagos_previos_del_periodo, texto_ticket_corte_encargado

    ahora = ahora or datetime.now().astimezone()
    estado = estado_caja(session, ahora)
    avisos = pagos_que_tocan_hoy(session, ahora.date())
    if estado.resumen.operaciones == 0 and not avisos:
        return ResultadoCorte(False, "Sin corte: no hay ventas ni pagos desde el último corte.")

    auto = cerrar_corte_automatico(session, creado_por=creado_por, ahora=ahora)
    rows = operaciones_del_periodo(session, auto.estado.desde, auto.estado.hasta)
    try:
        from pos_uniformes.services.retiros_service import retiros_del_periodo

        retiros = retiros_del_periodo(session, auto.estado.desde, auto.estado.hasta)
    except Exception:  # noqa: BLE001
        session.rollback()
        retiros = []
    ya_pagados = pagos_previos_del_periodo(session, auto)
    # El PAPEL se queda en la tienda: va sin los movimientos privados.
    # El mensaje de Telegram (más abajo) llega solo al celular de Daniel y
    # sí lleva todo.
    from pos_uniformes.services.corte_caja_service import datos_ticket_encargado

    datos = datos_ticket_encargado(session, auto.estado.desde, auto.estado.hasta)
    texto = texto_ticket_corte_encargado(
        auto.corte, auto.estado.resumen.efectivo, auto.pagos, datos.por_empleada, retiros=datos.retiros,
        tarjeta=datos.tarjeta, tarjeta_ops=datos.tarjeta_ops, ya_pagados=ya_pagados,
    )
    impreso = False
    try:
        trabajos_service.enviar_ticket(session, texto, origen="corte_remoto", creado_por=creado_por)
        session.commit()
        impreso = True
    except Exception:  # noqa: BLE001
        session.rollback()

    retiro = (Decimal(auto.corte.monto_final) - Decimal(auto.corte.reactivo_final)).quantize(Decimal("0.01"))
    lineas = [f"🧾 Corte hecho {ahora:%d/%m %H:%M}", f"Venta en efectivo: ${auto.estado.resumen.efectivo:,.2f}"]
    if auto.estado.resumen.tarjeta:
        lineas.append(f"Con tarjeta: ${auto.estado.resumen.tarjeta:,.2f} ({contar_tarjeta(rows)} voucher(s), no está en el cajón)")
    for p in auto.pagos:
        lineas.append(f"Pagar a {(p.employee_name or p.employee_code).split()[0]}: ${Decimal(p.total):,.2f}")
    for p in ya_pagados:
        lineas.append(f"Ya pagado a {(p.employee_name or p.employee_code).split()[0]}: ${Decimal(p.total):,.2f}")
    for r in retiros:
        lineas.append(f"Ya salió ({r.motivo}): ${Decimal(r.monto):,.2f}")
    lineas.append(f"Sacar de la venta: ${retiro:,.2f}")
    lineas.append(f"Reactivo que queda: ${Decimal(auto.corte.reactivo_final):,.2f}")
    lineas.append("🖨 Ticket enviado a la impresora de la tienda." if impreso else "⚠️ El corte quedó guardado pero no se pudo encolar el ticket.")
    return ResultadoCorte(True, "\n".join(lineas), impreso)
