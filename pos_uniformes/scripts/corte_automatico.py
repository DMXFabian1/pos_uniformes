"""Corte automático 30 minutos antes de cerrar (PC servidor, tarea programada).

Se programa a TODAS las horas posibles de corte (16:30 y 17:30); el script
decide si hoy toca a esa hora. Registra los pagos del día, cierra el periodo
con la cifra calculada, imprime el ticket del encargado en la impresora de la
tienda (cola de trabajos) y avisa por Telegram.

Uso:
    python -m pos_uniformes.scripts.corte_automatico            # decide y hace
    python -m pos_uniformes.scripts.corte_automatico --forzar   # hace aunque no sea la hora
    python -m pos_uniformes.scripts.corte_automatico --simular  # solo dice qué haría
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from decimal import Decimal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Corte automático 30 min antes de cerrar")
    parser.add_argument("--forzar", action="store_true", help="hacer el corte aunque no sea la hora")
    parser.add_argument("--simular", action="store_true", help="no guardar ni imprimir; solo decir qué haría")
    args = parser.parse_args(argv)

    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.corte_caja_service import (
        cerrar_corte_automatico,
        estado_caja,
        operaciones_del_periodo,
        pagos_que_tocan_hoy,
        ultimo_corte,
    )
    from pos_uniformes.services.horario_tienda_service import AUTO_CODE, decidir_corte_automatico

    ahora = datetime.now().astimezone()
    with get_session() as session:
        previo = ultimo_corte(session)
        estado = estado_caja(session, ahora)
        avisos = pagos_que_tocan_hoy(session, ahora.date())
        hay_movimiento = estado.resumen.operaciones > 0 or bool(avisos)
        decision = decidir_corte_automatico(
            ahora, (previo.hasta or previo.created_at) if previo else None, hay_movimiento
        )
        if not decision.hacer and not args.forzar:
            print(f"Sin corte: {decision.motivo}.")
            return 0
        if args.simular:
            print(f"Haría el corte ahora ({decision.motivo}): venta ${estado.resumen.efectivo:,.2f}, "
                  f"{len(avisos)} pago(s) hoy.")
            return 0

        from pos_uniformes.services import trabajos_service
        from pos_uniformes.services.libreta_service import resumir_por_empleada
        from pos_uniformes.services.retiros_service import retiros_del_periodo
        from pos_uniformes.ui.dialogs.corte_caja_dialog import texto_ticket_corte_encargado

        auto = cerrar_corte_automatico(session, creado_por=AUTO_CODE)
        rows = operaciones_del_periodo(session, auto.estado.desde, auto.estado.hasta)
        try:
            retiros = retiros_del_periodo(session, auto.estado.desde, auto.estado.hasta)
        except Exception:  # noqa: BLE001
            session.rollback()
            retiros = []
        texto = texto_ticket_corte_encargado(
            auto.corte, auto.estado.resumen.efectivo, auto.pagos, resumir_por_empleada(rows), retiros=retiros
        )
        impreso = False
        try:
            trabajos_service.enviar_ticket(session, texto, origen="corte_automatico", creado_por=AUTO_CODE)
            session.commit()
            impreso = True
        except Exception as exc:  # noqa: BLE001
            print(f"El corte quedó guardado pero no se pudo encolar el ticket: {exc}")

    retiro = (Decimal(auto.corte.monto_final) - Decimal(auto.corte.reactivo_final)).quantize(Decimal("0.01"))
    resumen = [f"🧾 Corte automático {ahora:%d/%m %H:%M}", f"Venta: ${auto.estado.resumen.efectivo:,.2f}"]
    for p in auto.pagos:
        resumen.append(f"Pagar a {(p.employee_name or p.employee_code).split()[0]}: ${Decimal(p.total):,.2f}")
    for r in retiros:
        resumen.append(f"Ya salió ({r.motivo}): ${Decimal(r.monto):,.2f}")
    resumen.append(f"Sacar de la venta: ${retiro:,.2f}")
    resumen.append("Ticket enviado a la impresora." if impreso else "⚠️ No se pudo imprimir el ticket.")
    mensaje = "\n".join(resumen)
    print(mensaje)
    try:
        from pos_uniformes.services import telegram_service

        if telegram_service.token_configurado() and telegram_service.chat_id_configurado():
            telegram_service.enviar_mensaje(mensaje)
    except Exception as exc:  # noqa: BLE001
        print(f"(Telegram no disponible: {exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
