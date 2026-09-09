"""Corte de 30 minutos antes de cerrar (PC servidor, tarea programada).

Se programa a TODAS las horas posibles de corte (16:30 y 17:30); el script
decide si hoy toca a esa hora.

Desde 2026-09-09 NO cierra la caja solo: manda a Telegram lo que hay y
espera a que Daniel conteste `/corte` (o `/nocorte`). Con `--recordar` (20
min después) se lo recuerda UNA vez si no contestó; si sigue sin contestar,
la caja se queda sin corte y salta la alerta de "cierre sin corte".

Uso:
    python -m pos_uniformes.scripts.corte_automatico             # propone por Telegram
    python -m pos_uniformes.scripts.corte_automatico --recordar  # recuerda una vez
    python -m pos_uniformes.scripts.corte_automatico --hacer     # lo hace sin preguntar
    python -m pos_uniformes.scripts.corte_automatico --forzar    # aunque no sea la hora
    python -m pos_uniformes.scripts.corte_automatico --simular   # solo dice qué haría
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Corte de 30 min antes de cerrar")
    parser.add_argument("--forzar", action="store_true", help="considerar la hora aunque no toque")
    parser.add_argument("--simular", action="store_true", help="no guardar ni imprimir; solo decir qué haría")
    parser.add_argument("--hacer", action="store_true", help="cerrar e imprimir sin preguntar (comportamiento viejo)")
    parser.add_argument("--recordar", action="store_true", help="recordar una vez la propuesta sin contestar")
    args = parser.parse_args(argv)

    if args.recordar:
        return _recordar()

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
            que = "Haría el corte" if args.hacer else "Propondría el corte"
            print(f"{que} ahora ({decision.motivo}): venta ${estado.resumen.efectivo:,.2f}, "
                  f"{len(avisos)} pago(s) hoy.")
            return 0

        if not args.hacer:
            # Lo normal: preguntar primero. Nada se guarda ni se imprime.
            from pos_uniformes.services.corte_propuesta_service import anotar_propuesta
            from pos_uniformes.services.corte_remoto_service import texto_propuesta_corte

            mensaje = texto_propuesta_corte(session, ahora)
            anotar_propuesta(ahora)
            _mandar(mensaje)
            print(mensaje)
            return 0

        from pos_uniformes.services.corte_remoto_service import hacer_corte_y_avisar

        resultado = hacer_corte_y_avisar(session, creado_por=AUTO_CODE, ahora=ahora)
    print(resultado.mensaje)
    _mandar(resultado.mensaje)
    return 0


def _mandar(mensaje: str) -> None:
    try:
        from pos_uniformes.services import telegram_service

        if telegram_service.token_configurado() and telegram_service.chat_id_configurado():
            telegram_service.enviar_mensaje(mensaje)
    except Exception as exc:  # noqa: BLE001
        print(f"(Telegram no disponible: {exc})")


def _recordar() -> int:
    """Reenvía UNA vez la propuesta que quedó sin contestar."""
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.corte_caja_service import ultimo_corte
    from pos_uniformes.services.corte_propuesta_service import (
        anotar_recordatorio,
        leer,
        toca_recordar,
    )
    from pos_uniformes.services.corte_remoto_service import texto_propuesta_corte

    ahora = datetime.now().astimezone()
    propuesta = leer()
    with get_session() as session:
        previo = ultimo_corte(session)
        hecho = previo.hasta or previo.created_at if previo else None
        hubo_corte_despues = bool(
            hecho and propuesta.momento and _local(hecho) >= _local(propuesta.momento)
        )
        if not toca_recordar(propuesta, hoy=ahora.date(), hubo_corte_despues=hubo_corte_despues):
            print("Nada que recordar.")
            return 0
        mensaje = "⏰ Sigue pendiente el corte.\n\n" + texto_propuesta_corte(session, ahora)
    anotar_recordatorio()
    _mandar(mensaje)
    print(mensaje)
    return 0


def _local(momento):
    return momento.astimezone().replace(tzinfo=None) if momento.tzinfo else momento


if __name__ == "__main__":
    sys.exit(main())
