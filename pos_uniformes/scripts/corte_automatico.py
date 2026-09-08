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

        from pos_uniformes.services.corte_remoto_service import hacer_corte_y_avisar

        resultado = hacer_corte_y_avisar(session, creado_por=AUTO_CODE, ahora=ahora)
    print(resultado.mensaje)
    try:
        from pos_uniformes.services import telegram_service

        if telegram_service.token_configurado() and telegram_service.chat_id_configurado():
            telegram_service.enviar_mensaje(resultado.mensaje)
    except Exception as exc:  # noqa: BLE001
        print(f"(Telegram no disponible: {exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
