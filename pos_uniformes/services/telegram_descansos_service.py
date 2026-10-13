"""Aprobar o rechazar un día de descanso desde el celular, VIENDO la semana.

Ella lo pide en la Libreta y a Daniel le llega el aviso con los botones, igual
que los préstamos. La diferencia está en qué se necesita para contestar: en un
préstamo es un monto, y aquí es cómo queda la tienda ese día. Por eso el aviso
trae el panorama —quién más descansa, la semana completa, qué tan movido suele
ser ese día, y si ella tiene pago o conteo— en vez de mandar a mirarlo a otro
lado (Daniel, 2026-10-05: "me gustaría ver el calendario para ver si conviene").

Un descanso aprobado MUEVE su descanso fijo de esa semana: cambia de día, no
gana uno extra.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

#: Prefijo de los botones de esta pantalla.
PREFIJO = "dc:"

_ABREV = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


def _en_plural(nombre_dia: str) -> str:
    """«los sábados», no «los sábado». De lunes a viernes no cambian."""
    if nombre_dia in ("sábado", "domingo"):
        return nombre_dia + "s"
    return nombre_dia


def _teclado(filas):
    from pos_uniformes.services import telegram_service

    return telegram_service.teclado(filas)


def es_de_descansos(dato: str) -> bool:
    return str(dato or "").startswith(PREFIJO)


def _pila(solicitud) -> str:
    return str(solicitud.employee_name or solicitud.employee_code).split()[0]


def encabezado(s, hoy) -> list[str]:
    """Quién pide qué. Un intercambio dice las dos mitades y si la compañera
    ya aceptó: Daniel no aprueba algo que una de las dos no ha dicho."""
    nombre = s.employee_name or s.employee_code
    if getattr(s, "tipo", "cambio") == "intercambio":
        otra = s.companera_name or s.companera_code
        acepto = "✔️ las dos aceptaron" if s.companera_acepto_at else f"⏳ falta que {otra.split()[0]} acepte"
        return [
            f"🔄 {nombre} y {otra} se quieren cambiar el descanso "
            f"({_cuando_es(s.fecha, hoy)}):",
            f"· {nombre.split()[0]} descansaría el {contexto_dia(s)}",
            f"· {otra.split()[0]} descansaría el {_dia(s.fecha_companera)}",
            acepto,
        ]
    lineas = [
        f"🛌 {nombre} pide descansar el {contexto_dia(s)} ({_cuando_es(s.fecha, hoy)})",
        f"Para: {s.motivo}",
    ]
    if getattr(s, "fecha_fijo", None):
        lineas.append(f"Su descanso del {_dia(s.fecha_fijo)} pasaría a trabajo.")
    return lineas


def _dia(fecha) -> str:
    _DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    return f"{_DIAS[fecha.weekday()]} {fecha:%d/%m}"


def _cuando_es(fecha, hoy) -> str:
    dias = (fecha - hoy).days
    if dias == 0:
        return "HOY"
    if dias == 1:
        return "mañana"
    return f"en {dias} días"


# ── La lista: /descansos ─────────────────────────────────────────────────────

def texto_y_botones(session: Session, *, hoy=None) -> tuple[str, str]:
    """Lo que está esperando respuesta, con un botón por solicitud."""
    from datetime import date as _date

    from pos_uniformes.services import descansos_service as ds

    hoy = hoy or _date.today()
    pendientes = ds.pendientes(session, hoy=hoy)
    if not pendientes:
        texto = "No hay días de descanso esperando respuesta. ✅"
        olvidadas = ds.sin_responder_que_ya_pasaron(session, hoy=hoy)
        if olvidadas:
            # Desde el lado de ella, no contestar se siente igual que un "no".
            quienes = ", ".join(sorted({_pila(s) for s in olvidadas}))
            texto += (
                f"\n\n⚠️ Pero {len(olvidadas)} se quedaron sin contestar hasta que el día "
                f"pasó ({quienes}). Eso se siente como un «no» que nadie dijo."
            )
        return texto, _teclado([[("‹ Menú", "m:raiz")]])

    lineas = ["🛌 Días de descanso por responder:", ""]
    filas = []
    for s in pendientes:
        dia = f"{_ABREV[s.fecha.weekday()]} {s.fecha:%d/%m}"
        lineas.append(f"· {_pila(s)} — {dia} ({_cuando_es(s.fecha, hoy)})")
        lineas.append(f"   {s.motivo}")
        filas.append([(f"👀 {_pila(s)} · {dia}", f"{PREFIJO}ver:{s.id}")])
    filas.append([("‹ Menú", "m:raiz")])
    return "\n".join(lineas), _teclado(filas)


# ── El panorama de UN día ────────────────────────────────────────────────────

def texto_de_contexto(contexto, *, incluir_semana: bool = True) -> list[str]:
    """Las líneas con las que se decide. Puro formato, sin base."""
    lineas: list[str] = []
    if contexto.quien_mas_descansa:
        quienes = ", ".join(contexto.quien_mas_descansa)
        marca = "⚠️" if contexto.quedaria_corta else "·"
        lineas.append(f"{marca} Ese día ya descansa: {quienes}")
    else:
        lineas.append("· Ese día no descansa nadie más")
    if contexto.trabajan_ese_dia:
        lineas.append(f"· Quedarían trabajando: {', '.join(contexto.trabajan_ese_dia)}")
    else:
        lineas.append("⚠️ No quedaría NADIE trabajando ese día")

    if contexto.venta_tipica is not None:
        pico = " — el día más movido de la semana" if contexto.es_el_dia_mas_movido else ""
        lineas.append(
            f"· Los {_en_plural(contexto.nombre_dia)} se vende ${contexto.venta_tipica:,.0f} "
            f"en promedio ({contexto.venta_tipica_de_cuantos} de referencia){pico}"
        )
    if contexto.tiene_pago:
        lineas.append("⚠️ Ese día le toca cobrar")
    if contexto.tiene_conteo:
        lineas.append(f"⚠️ Ese día toca conteo: {', '.join(contexto.tiene_conteo)}")

    if incluir_semana and contexto.semana:
        lineas.append("")
        lineas.append("La semana quedaría así:")
        for d in contexto.semana:
            quien = ", ".join(d.descansan) if d.descansan else "—"
            flecha = " ←" if d.es_el_pedido else ""
            lineas.append(
                f"  {_ABREV[d.fecha.weekday()]} {d.fecha:%d/%m}  "
                f"trabajan {len(d.trabajan)} · descansa {quien}{flecha}"
            )
    return lineas


def detalle(session: Session, solicitud_id: int, *, hoy=None) -> tuple[str, list]:
    """(texto, filas de botones) de UNA solicitud, con todo el panorama."""
    from datetime import date as _date

    from pos_uniformes.database.models import SolicitudDescanso
    from pos_uniformes.services import descansos_service as ds

    hoy = hoy or _date.today()
    s = session.get(SolicitudDescanso, int(solicitud_id))
    if s is None:
        return "Esa solicitud ya no existe.", []

    lineas = encabezado(s, hoy) + [""]
    try:
        lineas.extend(texto_de_contexto(ds.contexto_de(session, s)))
    except Exception:  # noqa: BLE001 — sin panorama se contesta igual
        lineas.append("(no se pudo armar el panorama de ese día)")

    filas = []
    if s.estado == ds.PEDIDO:
        lineas.append("")
        if s.tipo != ds.INTERCAMBIO:
            lineas.append("Si lo apruebas, su descanso fijo de esa semana se mueve a este día.")
        filas.append([
            (f"✅ Dárselo", f"{PREFIJO}ok:{s.id}"),
            ("✖️ Ahora no", f"{PREFIJO}no:{s.id}"),
        ])
    else:
        lineas.append("")
        lineas.append(f"Ya está {s.estado}.")
    return "\n".join(lineas), filas


def contexto_dia(solicitud) -> str:
    _DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    return f"{_DIAS[solicitud.fecha.weekday()]} {solicitud.fecha:%d/%m}"


# ── Botones ──────────────────────────────────────────────────────────────────

def atender(dato: str, *, session_factory, quien: str) -> tuple[str, str, str]:
    """Un botón de descansos: (aviso corto, texto nuevo, botones nuevos)."""
    from pos_uniformes.services import descansos_service as ds

    accion = str(dato or "")[len(PREFIJO):]
    que, _, crudo = accion.partition(":")

    def _con_volver(filas):
        return _teclado(list(filas) + [[("‹ Descansos", f"{PREFIJO}lista")]])

    # «‹ Descansos» no lleva id: hay que atenderlo ANTES de pedir el número.
    # Pedirlo primero lo mandaba a «No conozco ese botón», y el botón de
    # regreso nunca funcionó (mismo tropiezo que cortes el 08/10; 2026-10-10).
    if que == "lista":
        with session_factory() as session:
            texto, botones = texto_y_botones(session)
        return "", texto, botones
    try:
        solicitud_id = int(crudo)
    except ValueError:
        return "No conozco ese botón", "", ""

    if que == "ver":
        with session_factory() as session:
            texto, filas = detalle(session, solicitud_id)
        return "", texto, _con_volver(filas)

    with session_factory() as session:
        try:
            if que == "ok":
                s = ds.aprobar(session, solicitud_id, quien=quien)
                aviso = "Aprobado"
                hecho = (
                    f"✅ {_pila(s)} descansa el {contexto_dia(s)}.\n"
                    "Ya quedó en el calendario y se le avisa en la Libreta."
                )
            elif que == "no":
                s = ds.rechazar(session, solicitud_id, quien=quien)
                aviso = "Rechazado"
                hecho = f"✖️ {_pila(s)} no descansa el {contexto_dia(s)}."
            else:
                return "No conozco ese botón", "", ""
            session.commit()
        except ds.NoSePuede as exc:
            session.rollback()
            texto, botones = texto_y_botones(session)
            return str(exc), texto, botones
        texto, botones = texto_y_botones(session)

    return aviso, hecho + "\n\n" + texto, botones


def botones_de(solicitud) -> str:
    """Los botones de UNA solicitud, para colgarlos de su propio aviso."""
    return _teclado([
        [
            ("✅ Dárselo", f"{PREFIJO}ok:{solicitud.id}"),
            ("✖️ Ahora no", f"{PREFIJO}no:{solicitud.id}"),
        ],
        [("🛌 Ver todos", "m:descansos")],
    ])


def aviso_de_solicitud(solicitud, *, session: Session | None = None, hoy=None) -> str:
    """El mensaje que le llega a Daniel cuando alguien pide un día.

    Con `session` trae el panorama del día; sin ella se queda en lo básico — el
    aviso tiene que salir aunque la consulta falle.
    """
    from datetime import date as _date

    hoy = hoy or _date.today()
    lineas = encabezado(solicitud, hoy)
    if session is not None and getattr(solicitud, "tipo", "cambio") != "intercambio":
        try:
            from pos_uniformes.services import descansos_service as ds

            lineas.append("")
            lineas.extend(texto_de_contexto(ds.contexto_de(session, solicitud)))
        except Exception:  # noqa: BLE001
            pass
    return "\n".join(lineas)


def avisar_a_daniel(session: Session, solicitud) -> None:
    """Le llega al instante con el panorama del día; si no hay internet (o el
    kiosko no tiene el token), no se pierde: queda en la cola de alertas que
    el bot de la PC servidor manda en cuanto puede. Nunca truena: la
    solicitud ya quedó guardada y los recordatorios la vuelven a mostrar."""
    import logging

    texto = aviso_de_solicitud(solicitud, session=session)
    botones = botones_de(solicitud)
    try:
        from pos_uniformes.services.telegram_service import enviar_mensaje

        enviar_mensaje(texto, botones=botones)
        return
    except Exception:  # noqa: BLE001
        pass
    try:
        from pos_uniformes.services.alertas_service import encolar

        encolar(session, texto, botones)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("Descanso: no se pudo avisar")
