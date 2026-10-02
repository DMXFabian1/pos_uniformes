"""Aprobar o rechazar préstamos desde el celular.

Ella lo pide en la Libreta y a Daniel le llega el aviso; aquí vive lo que ve y
lo que pasa cuando toca un botón.

El aviso **trae los botones** (Daniel, 02/10: "me gustaría al momento que me
llegue el mensaje del bot decidir aprobarlo o no, no que solo me informe"). Y
trae con qué decidir: cuánto lleva ganado, cuál es su tope, qué le quedaría de
su próximo pago. Antes decía el monto y el motivo y mandaba a `/prestamos`, de
modo que para contestar había que acordarse de un comando y volver a buscar a
quién era — con el teléfono en la mano, en medio de otra cosa.

Aprobar sigue sin estar a un toque desde el **tablero**: ahí no hay contexto.
En el aviso sí lo hay, porque el aviso es de esa persona y de ese monto.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

#: Prefijo de los botones de esta pantalla.
PREFIJO = "pr:"


def _teclado(filas):
    from pos_uniformes.services import telegram_service

    return telegram_service.teclado(filas)


def es_de_prestamos(dato: str) -> bool:
    return str(dato or "").startswith(PREFIJO)


def _cuando(prestamo) -> str:
    from pos_uniformes.utils.date_format import format_display_datetime

    try:
        return format_display_datetime(prestamo.created_at)
    except Exception:  # noqa: BLE001
        return ""


def texto_y_botones(session: Session) -> tuple[str, str]:
    """Lo que está esperando respuesta, con un botón por solicitud."""
    from pos_uniformes.services import prestamos_service as pr

    pendientes = pr.pendientes(session)
    if not pendientes:
        return "No hay préstamos esperando respuesta. ✅", _teclado([[("‹ Menú", "m:raiz")]])

    lineas = ["💵 Préstamos por responder:", ""]
    filas = []
    for p in pendientes:
        nombre = str(p.employee_name or p.employee_code)
        monto = Decimal(str(p.monto))
        cuando = _cuando(p)
        lineas.append(f"· {nombre} — ${monto:,.2f}")
        lineas.append(f"   {p.motivo}" + (f" · {cuando}" if cuando else ""))
        filas.append([
            (f"✅ {nombre} ${monto:,.0f}", f"{PREFIJO}ok:{p.id}"),
            ("✖️", f"{PREFIJO}no:{p.id}"),
        ])
    filas.append([("‹ Menú", "m:raiz")])
    return "\n".join(lineas), _teclado(filas)


def atender(dato: str, *, session_factory, quien: str) -> tuple[str, str, str]:
    """Un botón de préstamos: (aviso corto, texto nuevo, botones nuevos)."""
    from pos_uniformes.services import prestamos_service as pr

    accion = str(dato or "")[len(PREFIJO):]
    if ":" not in accion:
        return "No conozco ese botón", "", ""
    que, _, crudo = accion.partition(":")
    try:
        prestamo_id = int(crudo)
    except ValueError:
        return "No conozco ese botón", "", ""

    with session_factory() as session:
        try:
            if que == "ok":
                p = pr.aprobar(session, prestamo_id, quien=quien)
                aviso = "Aprobado"
                hecho = (
                    f"✅ Aprobado: ${Decimal(str(p.monto)):,.2f} para "
                    f"{p.employee_name or p.employee_code}.\n"
                    "Ya quedó anotado como retiro del cajón, y se le descuenta "
                    "completo en su siguiente pago."
                )
            elif que == "no":
                p = pr.rechazar(session, prestamo_id, quien=quien)
                aviso = "Rechazado"
                hecho = f"✖️ Rechazado el préstamo de {p.employee_name or p.employee_code}."
            else:
                return "No conozco ese botón", "", ""
            session.commit()
        except pr.NoSePuede as exc:
            session.rollback()
            texto, botones = texto_y_botones(session)
            return str(exc), texto, botones
        texto, botones = texto_y_botones(session)

    return aviso, hecho + "\n\n" + texto, botones


def botones_de(prestamo) -> str:
    """Los dos botones de UNA solicitud, para colgarlos de su propio aviso."""
    nombre = str(prestamo.employee_name or prestamo.employee_code).split()[0]
    return _teclado([
        [
            (f"✅ Prestarle a {nombre}", f"{PREFIJO}ok:{prestamo.id}"),
            ("✖️ Ahora no", f"{PREFIJO}no:{prestamo.id}"),
        ],
        [("💵 Ver todos", "m:prestamos")],
    ])


def aviso_de_solicitud(prestamo, *, session: Session | None = None) -> str:
    """El mensaje que le llega a Daniel cuando alguien pide.

    Con `session` trae además con qué decidir sin abrir nada: lo que lleva
    ganado, su tope, y qué le quedaría del próximo pago. Sin ella se queda en
    lo básico — el aviso tiene que salir aunque la consulta falle.
    """
    nombre = str(prestamo.employee_name or prestamo.employee_code)
    monto = Decimal(str(prestamo.monto))
    lineas = [
        f"💵 {nombre} pide ${monto:,.2f} prestados",
        f"Para: {prestamo.motivo}",
    ]
    detalle = _contexto(prestamo, session)
    if detalle:
        lineas.append("")
        lineas.extend(detalle)
    lineas.append("")
    lineas.append("Si lo apruebas sale del cajón hoy y se le descuenta completo")
    lineas.append("en su siguiente pago.")
    return "\n".join(lineas)


def _contexto(prestamo, session: Session | None) -> list[str]:
    """Las tres cifras con las que se decide. Vacío si no se pudieron sacar."""
    if session is None:
        return []
    try:
        from pos_uniformes.services import prestamos_service as pr

        code = str(prestamo.employee_code)
        monto = Decimal(str(prestamo.monto))
        ganado = pr.ganado_hasta_hoy(session, code)
        tope = pr.tope_para(session, code)
    except Exception:  # noqa: BLE001 — el aviso vale más que su adorno
        return []

    # No se consulta lo que ya debe: `pedir` no la deja pedir si tiene algo por
    # cobrar, así que aquí siempre sería cero.
    return [
        f"Lleva ganado: ${ganado:,.2f}",
        f"Puede pedir hasta: ${tope:,.2f}",
        f"Le quedarían: ${ganado - monto:,.2f} de su próximo pago",
    ]
