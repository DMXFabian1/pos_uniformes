"""Vacaciones desde el celular: ver lo pedido, aprobar o rechazar, primas.

Mismo camino que los descansos y los préstamos: aviso con botones. Lo que se
necesita para decidir va EN el mensaje: fechas, días laborables, saldo del
periodo, fecha límite de ley, quién más falta esos días y conflictos.

Comandos:
- /vacaciones — lo que espera respuesta, con botones.
- /vacaciones no <número> <motivo> — rechazar diciendo por qué.
- /primas — primas vacacionales pendientes de pagar, con botón.
- /ingreso <nombre> <AAAA-MM-DD> — capturar la fecha de ingreso VERIFICADA.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

PREFIJO = "vc:"
_ABREV = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


def _teclado(filas):
    from pos_uniformes.services import telegram_service

    return telegram_service.teclado(filas)


def es_de_vacaciones(dato: str) -> bool:
    return str(dato or "").startswith(PREFIJO)


def _d(f: date) -> str:
    return f"{_ABREV[f.weekday()]} {f:%d/%m}"


def _pila(s) -> str:
    return str(s.employee_name or s.employee_code).split()[0]


def texto_y_botones(session: Session, *, hoy=None) -> tuple[str, str]:
    from pos_uniformes.database.models import SolicitudVacaciones
    from pos_uniformes.services import vacaciones_service as vs

    pendientes = session.query(SolicitudVacaciones).filter(
        SolicitudVacaciones.estado == vs.PEDIDO).order_by(SolicitudVacaciones.desde).all()
    primas = vs.primas_pendientes(session)
    if not pendientes:
        texto = "No hay vacaciones esperando respuesta. ✅"
    else:
        lineas = ["🏖️ Vacaciones por responder:", ""]
        for s in pendientes:
            lineas.append(f"· #{s.id} {_pila(s)} — {_d(s.desde)} a {_d(s.hasta)} ({s.dias} días)")
        texto = "\n".join(lineas)
    if primas:
        total = sum(p.monto for p in primas)
        texto += f"\n\n💵 Primas vacacionales sin pagar: {len(primas)} (${total:,.2f}) → /primas"
    filas = [[(f"👀 {_pila(s)} · {_d(s.desde)}", f"{PREFIJO}ver:{s.id}")] for s in pendientes]
    filas.append([("‹ Menú", "m:raiz")])
    return texto, _teclado(filas)


def detalle(session: Session, sid: int, *, hoy=None) -> tuple[str, list]:
    from pos_uniformes.database.models import PeriodoVacaciones, SolicitudVacaciones
    from pos_uniformes.services import vacaciones_service as vs

    hoy = hoy or date.today()
    s = session.get(SolicitudVacaciones, int(sid))
    if s is None:
        return "Esa solicitud ya no existe.", []
    p = session.get(PeriodoVacaciones, s.periodo_id)
    sal = vs.saldo(session, s.employee_code, periodo_id=s.periodo_id)
    lineas = [
        f"🏖️ #{s.id} {s.employee_name or s.employee_code} pide vacaciones",
        f"Del {_d(s.desde)} al {_d(s.hasta)}: {s.dias} días laborables",
    ]
    if s.motivo:
        lineas.append(f"Nota: {s.motivo}")
    if p is not None:
        lineas.append(
            f"Periodo: año {p.anio_servicio} de servicio · le tocan {p.dias_correspondientes} · "
            f"disponibles {sal.disponible}"
        )
        lineas.append(f"Ley (art. 81): concederlas antes del {p.fecha_limite:%d/%m/%Y}")
        if p.fecha_limite < s.desde:
            lineas.append("⚠️ Las fechas pedidas pasan el plazo de ley de ese periodo")
    if s.dias < vs.DIAS_CONTINUOS_MINIMOS:
        lineas.append(
            f"· Son menos de {vs.DIAS_CONTINUOS_MINIMOS} días seguidos: la ley (art. 78) le "
            "da derecho a 12 continuos si los quiere; partirlas es decisión de ella."
        )
    fuera = {d: q for d, q in vs.cobertura(session, s.desde, s.hasta, excluir=s.employee_code).items() if q}
    if fuera:
        lineas.append("Esos días también faltan:")
        for d, quienes in list(fuera.items())[:7]:
            lineas.append(f"  {_d(d)}: {', '.join(quienes)}")
    else:
        lineas.append("· Esos días no falta nadie más")
    filas = []
    if s.estado == vs.PEDIDO:
        filas.append([("✅ Aprobar", f"{PREFIJO}ok:{s.id}"), ("✖️ Rechazar", f"{PREFIJO}no:{s.id}")])
        lineas.append("")
        lineas.append(f"Para rechazar con motivo: /vacaciones no {s.id} <motivo>")
    else:
        lineas.append(f"\nYa está {s.estado}.")
    return "\n".join(lineas), filas


def atender(dato: str, *, session_factory, quien: str) -> tuple[str, str, str]:
    """Un botón: (aviso corto, texto nuevo, botones nuevos). Uno viejo encuentra
    la solicitud ya resuelta y no hace nada."""
    from pos_uniformes.services import vacaciones_service as vs

    accion = str(dato or "")[len(PREFIJO):]
    que, _, crudo = accion.partition(":")
    if que == "lista":
        with session_factory() as session:
            texto, botones = texto_y_botones(session)
        return "", texto, botones
    try:
        num = int(crudo)
    except ValueError:
        return "No conozco ese botón", "", ""

    def _volver(filas):
        return _teclado(list(filas) + [[("‹ Vacaciones", f"{PREFIJO}lista")]])

    if que == "ver":
        with session_factory() as session:
            texto, filas = detalle(session, num)
        return "", texto, _volver(filas)

    with session_factory() as session:
        try:
            if que == "ok":
                s = vs.aprobar(session, num, quien=quien)
                aviso, hecho = "Aprobado", (
                    f"✅ {_pila(s)} de vacaciones del {_d(s.desde)} al {_d(s.hasta)}. "
                    "Ya está en el calendario; a ella se le avisa en la Libreta."
                    + (f"\nPrima pendiente: ${s.prima_estimada:,.2f} → /primas" if s.prima_estimada else "")
                )
            elif que == "no":
                s = vs.rechazar(session, num, quien=quien)
                aviso, hecho = "Rechazado", f"✖️ No se aprobaron las vacaciones de {_pila(s)}."
            elif que == "pp":
                p = vs.marcar_prima_pagada(session, num, quien=quien)
                aviso, hecho = "Pagada", f"💵 Prima de {p.employee_code} (${p.monto:,.2f}) marcada pagada."
            else:
                return "No conozco ese botón", "", ""
            session.commit()
        except vs.NoSePuede as exc:
            session.rollback()
            texto, botones = texto_y_botones(session)
            return str(exc), texto, botones
        texto, botones = texto_y_botones(session)
    return aviso, hecho + "\n\n" + texto, botones


def comando(session: Session, argumento: str, *, quien: str) -> str:
    """`/vacaciones no 12 temporada alta` rechaza con motivo."""
    from pos_uniformes.services import vacaciones_service as vs

    partes = (argumento or "").split(maxsplit=2)
    if not partes:
        return texto_y_botones(session)[0]
    if partes[0].lower() == "no" and len(partes) >= 2:
        try:
            num = int(partes[1].lstrip("#"))
        except ValueError:
            return "Así: /vacaciones no 12 temporada alta"
        motivo = partes[2] if len(partes) > 2 else ""
        try:
            s = vs.rechazar(session, num, quien=quien, respuesta=motivo)
            session.commit()
        except vs.NoSePuede as exc:
            session.rollback()
            return str(exc)
        return f"✖️ Rechazadas las vacaciones de {_pila(s)}" + (f": «{motivo}»" if motivo else ".")
    return "Así: /vacaciones (lista) o /vacaciones no 12 motivo"


def primas(session: Session) -> tuple[str, str]:
    from pos_uniformes.services import vacaciones_service as vs

    pendientes = vs.primas_pendientes(session)
    if not pendientes:
        return "No hay primas vacacionales pendientes. ✅", _teclado([[("‹ Menú", "m:raiz")]])
    lineas = ["💵 Primas vacacionales sin pagar (se pagan aparte de la nómina semanal):", ""]
    filas = []
    for p in pendientes:
        lineas.append(f"· {p.employee_code}: {p.dias} días × ${p.salario_diario:,.2f} × {p.porcentaje}% = ${p.monto:,.2f}")
        filas.append([(f"✅ Ya pagué {p.employee_code} ${p.monto:,.0f}", f"{PREFIJO}pp:{p.id}")])
    lineas.append("\nBase: sueldo semanal / 7, sin comisiones (REVISAR con el contador).")
    filas.append([("‹ Menú", "m:raiz")])
    return "\n".join(lineas), _teclado(filas)


def ingreso(session: Session, argumento: str, *, quien: str) -> str:
    """`/ingreso Fanny 2024-03-01` — la fecha VERIFICADA (no se adivina)."""
    from datetime import datetime

    from pos_uniformes.services import vacaciones_service as vs
    from pos_uniformes.services.asistencia_service import buscar_code

    partes = (argumento or "").rsplit(maxsplit=1)
    if len(partes) != 2:
        return "Así: /ingreso Fanny 2024-03-01 (la fecha verificada de su contrato o alta)"
    nombre, crudo = partes
    try:
        fecha = datetime.strptime(crudo, "%Y-%m-%d").date()
    except ValueError:
        return f"No entendí «{crudo}» como fecha. Usa AAAA-MM-DD, por ejemplo 2024-03-01."
    code = buscar_code(session, nombre)
    if code is None:
        return f"¿Quién? No encontré a «{nombre}»."
    try:
        vs.capturar_expediente(session, code, fecha_ingreso=fecha, quien=quien, origen="telegram")
        nuevos = vs.generar_periodos(session, code, quien=quien)
        session.commit()
    except vs.NoSePuede as exc:
        session.rollback()
        return str(exc)
    e = vs.expediente(session, code)
    return (f"📁 {code}: ingreso {fecha:%d/%m/%Y}, {e.anios_cumplidos} año(s) cumplidos. "
            f"Periodos generados: {len(nuevos)} · disponibles {e.disponible} días.")


def aviso_de_solicitud(s, *, session: Session | None = None) -> str:
    if session is not None:
        try:
            return detalle(session, s.id)[0]
        except Exception:  # noqa: BLE001 — el aviso sale aunque falte el panorama
            pass
    return (f"🏖️ #{s.id} {s.employee_name or s.employee_code} pide vacaciones del "
            f"{_d(s.desde)} al {_d(s.hasta)} ({s.dias} días). /vacaciones")


def botones_de(s) -> str:
    return _teclado([
        [("✅ Aprobar", f"{PREFIJO}ok:{s.id}"), ("✖️ Rechazar", f"{PREFIJO}no:{s.id}")],
        [("🏖️ Ver todas", f"{PREFIJO}lista")],
    ])


def avisar_a_daniel(session: Session, s) -> None:
    """Directo si se puede; si no, a la cola de alertas (sale cuando vuelva la
    red). Nunca truena: la solicitud ya quedó guardada."""
    import logging

    texto, botones = aviso_de_solicitud(s, session=session), botones_de(s)
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
        logging.getLogger(__name__).exception("Vacaciones: no se pudo avisar")


def con_botones(session: Session, argumento: str = "") -> tuple[str, str]:
    """`/vacaciones` sola trae botones; con argumento es el rechazo con motivo."""
    from pos_uniformes.services.telegram_bot_service import CODIGO_REMOTO

    if (argumento or "").strip():
        return comando(session, argumento, quien=CODIGO_REMOTO), ""
    return texto_y_botones(session)
