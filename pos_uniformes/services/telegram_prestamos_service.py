"""Aprobar o rechazar préstamos desde el celular.

Ella lo pide en la Libreta y a Daniel le llega el aviso; aquí vive lo que ve y
lo que pasa cuando toca un botón. Aprobar mueve dinero (sale del cajón), así
que no está a un solo toque desde el tablero: hay que entrar a /prestamos.
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


def aviso_de_solicitud(prestamo) -> str:
    """El mensaje que le llega a Daniel cuando alguien pide."""
    nombre = str(prestamo.employee_name or prestamo.employee_code)
    monto = Decimal(str(prestamo.monto))
    return (
        f"💵 {nombre} pide un préstamo de ${monto:,.2f}\n"
        f"Para: {prestamo.motivo}\n\n"
        "Responde con /prestamos"
    )
