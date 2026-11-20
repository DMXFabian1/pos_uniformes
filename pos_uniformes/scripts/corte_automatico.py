"""Corte de 30 minutos antes de cerrar (PC servidor, tarea programada).

Se programa a TODAS las horas posibles de corte (16:30 y 17:30); el script
decide si hoy toca a esa hora.

Desde 2026-09-09 NO cierra la caja solo: manda a Telegram lo que hay y
espera a que Daniel conteste `/corte` (o `/nocorte`). Con `--recordar` (20
min después) se lo recuerda UNA vez si no contestó.

Y con `--cerrar` (un rato después de cerrar la tienda) lo hace solo si siguió
sin contestar — porque en el kiosko el botón del corte únicamente sale con su
gafete, así que si él no está, nadie más puede cerrar el día.

Uso:
    python -m pos_uniformes.scripts.corte_automatico             # propone por Telegram
    python -m pos_uniformes.scripts.corte_automatico --recordar  # recuerda una vez
    python -m pos_uniformes.scripts.corte_automatico --cerrar    # lo hace si no contestó
    python -m pos_uniformes.scripts.corte_automatico --hacer     # lo hace sin preguntar
    python -m pos_uniformes.scripts.corte_automatico --forzar    # aunque no sea la hora
    python -m pos_uniformes.scripts.corte_automatico --simular   # solo dice qué haría
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from pos_uniformes.services.telegram_formato import encabezado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Corte de 30 min antes de cerrar")
    parser.add_argument("--forzar", action="store_true", help="considerar la hora aunque no toque")
    parser.add_argument("--simular", action="store_true", help="no guardar ni imprimir; solo decir qué haría")
    parser.add_argument("--hacer", action="store_true", help="cerrar e imprimir sin preguntar (comportamiento viejo)")
    parser.add_argument("--recordar", action="store_true", help="recordar una vez la propuesta sin contestar")
    parser.add_argument("--cerrar", action="store_true", help="hacerlo solo si ya cerró y no contestó")
    args = parser.parse_args(argv)

    if args.recordar:
        return _recordar()
    if args.cerrar:
        return _cerrar_si_nadie_contesto(simular=args.simular)

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
        hay_movimiento = estado.resumen.hubo_movimiento or bool(avisos)
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
            from pos_uniformes.services.corte_propuesta_service import anotar_propuesta, cancelada_hoy

            if cancelada_hoy(ahora.date()):
                print("Sin propuesta: Daniel ya dijo /nocorte hoy.")
                return 0
            from pos_uniformes.services.corte_remoto_service import texto_propuesta_corte

            from pos_uniformes.services.corte_remoto_service import propuesta_de_corte

            mensaje, botones = propuesta_de_corte(session, ahora)
            mid = _mandar_y_dar_id(mensaje, botones)
            anotar_propuesta(ahora, message_id=mid)
            print(mensaje)
            return 0

        from pos_uniformes.services.corte_remoto_service import hacer_corte_y_avisar

        resultado = hacer_corte_y_avisar(session, creado_por=AUTO_CODE, ahora=ahora)
    print(resultado.mensaje)
    _mandar(resultado.mensaje)
    return 0


def _mandar(mensaje: str, botones: str | None = None) -> bool:
    """Lo manda por Telegram y, si no hay línea, lo deja en la cola de alertas
    (el bot lo manda cuando vuelva). Antes la propuesta y «Cerré el día por
    ti» se perdían sin internet (auditoría 2026-11-07, #20)."""
    try:
        from pos_uniformes.services import telegram_service

        if not (telegram_service.token_configurado() and telegram_service.chat_id_configurado()):
            # La tarea no ve el token: a la cola, que el bot sí lo tiene. Un
            # corte hecho no se queda sin aviso (2026-11-20).
            print("(Telegram sin configurar aquí; lo dejo en la cola)")
            return _encolar(mensaje, botones)
        telegram_service.enviar_mensaje(mensaje, botones=botones, conservar=True)
        return True
    except Exception as exc:  # noqa: BLE001
        if _probablemente_salio(exc):
            print(f"(Telegram tardó en contestar: {exc}; no lo repito)")
            return True
        print(f"(Telegram no disponible: {exc}; lo dejo en la cola)")
    return _encolar(mensaje, botones)


def _probablemente_salio(exc: BaseException) -> bool:
    """Se acabó el tiempo esperando la respuesta: el mensaje ya salió. Encolarlo
    lo mandaba dos veces (dos propuestas con botones; 2026-11-20)."""
    try:
        from pos_uniformes.services import telegram_service

        return bool(telegram_service._ya_se_mando(exc))
    except Exception:  # noqa: BLE001
        return False


def _mandar_y_dar_id(mensaje: str, botones: str | None = None) -> int:
    """Como `_mandar`, pero devuelve el id del mensaje para poder reemplazarlo
    después (el recordatorio y el corte hecho). 0 si se fue a la cola."""
    try:
        from pos_uniformes.services import telegram_service

        if not (telegram_service.token_configurado() and telegram_service.chat_id_configurado()):
            print("(Telegram sin configurar aquí; lo dejo en la cola)")
            _encolar(mensaje, botones)
            return 0
        if len(mensaje) <= telegram_service._MAX:
            return telegram_service.enviar_y_dar_id(mensaje, botones=botones, conservar=True)
        telegram_service.enviar_mensaje(mensaje, botones=botones, conservar=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        if _probablemente_salio(exc):
            print(f"(Telegram tardó en contestar: {exc}; no lo repito)")
            return 0
        print(f"(Telegram no disponible: {exc}; lo dejo en la cola)")
    _encolar(mensaje, botones)
    return 0


def _encolar(mensaje: str, botones: str | None = None) -> bool:
    try:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services import alertas_service

        with get_session() as session:
            return alertas_service.encolar(session, mensaje, botones or "")
    except Exception as exc:  # noqa: BLE001
        print(f"(Tampoco se pudo encolar: {exc})")
        return False


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
        from pos_uniformes.services.corte_remoto_service import propuesta_de_corte

        texto_, botones = propuesta_de_corte(session, ahora)
        # Un solo encabezado: el del recordatorio toma el lugar del de la
        # propuesta (formato común del bot, 2026-11-20).
        mensaje = _con_encabezado(
            encabezado("⏰", "Sigue pendiente el corte", ahora, hora=True), texto_
        )
    # El recordatorio REEMPLAZA a la propuesta: sale nuevo (para que suene)
    # y la de antes se quita. Antes quedaban las dos con sus botones.
    from pos_uniformes.services.corte_propuesta_service import retirar_mensaje

    mid = _mandar_y_dar_id(mensaje, botones)
    if mid:
        retirar_mensaje(ahora.date(), salvo=mid)
    anotar_recordatorio(mid)
    print(mensaje)
    return 0


def _cerrar_si_nadie_contesto(*, simular: bool = False) -> int:
    """Hace el corte que quedó sin contestar, ya pasada la hora de cerrar.

    Es el último eslabón: propuesta → recordatorio → esto. Solo actúa si todo
    el camino normal pasó y él no contestó, y lo dice claramente para que no
    parezca que la cifra la decidió alguien.
    """
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.corte_caja_service import estado_caja, ultimo_corte
    from pos_uniformes.services.corte_propuesta_service import (
        MINUTOS_DESPUES_DE_CERRAR,
        leer,
        toca_cerrar_solo,
    )
    from pos_uniformes.services.horario_tienda_service import AUTO_CODE, hora_cierre, hora_corte

    ahora = datetime.now().astimezone()
    propuesta = leer()
    cierre = hora_cierre(ahora.date())
    minutos = (
        ahora - datetime.combine(ahora.date(), cierre).astimezone()
    ).total_seconds() / 60

    with get_session() as session:
        previo = ultimo_corte(session)
        hecho = (previo.hasta or previo.created_at) if previo else None
        hubo_corte_despues = bool(
            hecho and propuesta.momento and _local(hecho) >= _local(propuesta.momento)
        )
        estado = estado_caja(session, ahora)
        hubo_movimiento = estado.resumen.hubo_movimiento
        if not toca_cerrar_solo(
            propuesta,
            hoy=ahora.date(),
            minutos_tras_cierre=minutos,
            hubo_corte_despues=hubo_corte_despues,
            hubo_movimiento=hubo_movimiento,
        ):
            razon = (
                "No toca cerrar solo "
                f"(propuesta de {propuesta.fecha}, recordado={propuesta.recordado}, "
                f"cancelado={propuesta.cancelado}, corte={hubo_corte_despues}, "
                f"movimiento={hubo_movimiento}, {minutos:.0f} min tras cerrar; "
                f"se esperan {MINUTOS_DESPUES_DE_CERRAR})."
            )
            print(razon)
            # Lo normal (ya hay corte, dijo /nocorte, no hubo ventas) no se
            # avisa. Lo raro sí: que hoy no hubiera propuesta, o que el
            # recordatorio no haya corrido. Antes se quedaba en una consola
            # oculta y un día sin corte no lo sabía nadie (2026-10-10).
            raro = not (propuesta.hay and propuesta.fecha == ahora.date()) or not propuesta.recordado
            if raro and not hubo_corte_despues and not propuesta.cancelado and hubo_movimiento:
                # Formato común del bot (2026-11-20); «/corte» pasó a botón.
                _mandar(
                    encabezado("⚠️", "No cerré el día solo", ahora, hora=True) + "\n"
                    + (f"Hoy no se propuso el corte (¿no corrió la tarea de las {hora_corte(ahora.date()):%H:%M}?)"
                       if not (propuesta.hay and propuesta.fecha == ahora.date())
                       else "El recordatorio no corrió; lo intento en un rato")
                    + ".\n\nSi quieres, hazlo con el botón.",
                    botones=_boton_corte(),
                )
            return 0
        if simular:
            print(f"Haría el corte solo: venta ${estado.resumen.efectivo:,.2f}.")
            return 0

        from pos_uniformes.services.corte_remoto_service import hacer_corte_y_avisar

        try:
            resultado = hacer_corte_y_avisar(session, creado_por=AUTO_CODE, ahora=ahora)
        except Exception as exc:  # noqa: BLE001 — antes el error se quedaba en una consola oculta
            print(f"El cierre automático falló: {exc}")
            _mandar(_texto_cierre_fallido(str(exc)), botones=_boton_corte())
            return 1

    if not resultado.hecho:
        # No decir «Cerré el día» de un corte que no se hizo.
        print(resultado.mensaje)
        _mandar(_texto_cierre_fallido(resultado.mensaje), botones=_boton_corte())
        return 1
    from pos_uniformes.services.corte_propuesta_service import retirar_mensaje

    # El encabezado del cierre toma el lugar del de «Corte hecho» y el porqué
    # va al pie (formato común del bot, 2026-11-20).
    mensaje = (
        _con_encabezado(encabezado("🌙", "Cerré el día por ti", ahora, hora=True), resultado.mensaje)
        + "\n\nNo contestaste la propuesta y en el kiosko nadie más puede hacer el corte. "
        "Es la cifra real, sin ajustes. Si algo no cuadra, lo arreglas "
        "desde «Cortes anteriores» cuando puedas."
    )
    print(mensaje)
    # El recordatorio se quita solo cuando el aviso salió o quedó en la cola:
    # si no, el día quedaba cerrado sin rastro en el chat (2026-11-20).
    if _mandar(mensaje):
        retirar_mensaje(ahora.date())  # queda un solo mensaje del corte
    return 0


def _texto_cierre_fallido(motivo: str, ahora: datetime | None = None) -> str:
    """Formato común del bot (2026-11-20). El motivo suele ser un mensaje del
    corte con su propio encabezado: se le quita para no dejar uno debajo de
    otro. «Hazlo con /corte» pasó a botón (`_boton_corte`)."""
    from pos_uniformes.services.telegram_formato import mensaje

    motivo = _sin_encabezado(motivo)
    return mensaje(
        "⚠️", "No pude cerrar el día", cuando=ahora or datetime.now().astimezone(), hora=True,
        principal="Quise cerrar el día por ti y no pude:",
        detalle=motivo[:300],
        pie="Lo vendido sigue esperando corte. Hazlo con el botón cuando puedas.",
    )


def _boton_corte() -> str | None:
    """«🧾 Hacer el corte…»: el mismo botón de 🧾 Cortes (`co:nuevo`), que
    enseña la propuesta con sus botones. Antes estos avisos decían «manda
    /corte» (2026-11-20). Sin él, el aviso sale igual."""
    try:
        from pos_uniformes.services import telegram_service

        return telegram_service.teclado([[("🧾 Hacer el corte…", "co:nuevo")]])
    except Exception:  # noqa: BLE001
        return None


def _sin_encabezado(texto: str) -> str:
    """El texto sin su primera línea si esa es un encabezado del formato."""
    from pos_uniformes.services.telegram_formato import es_encabezado

    primera, _, resto = (texto or "").partition("\n")
    return resto.lstrip("\n") if es_encabezado(primera) else (texto or "")


def _con_encabezado(cabeza: str, texto: str) -> str:
    """`cabeza` en lugar del encabezado de `texto` (o encima, si no trae)."""
    from pos_uniformes.services.telegram_formato import es_encabezado

    primera, _, resto = (texto or "").partition("\n")
    if es_encabezado(primera):
        return cabeza + ("\n" + resto if resto else "")
    return cabeza + "\n\n" + (texto or "")


def _local(momento):
    return momento.astimezone().replace(tzinfo=None) if momento.tzinfo else momento


if __name__ == "__main__":
    sys.exit(main())
