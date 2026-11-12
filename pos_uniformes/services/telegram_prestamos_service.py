"""Aprobar o rechazar préstamos y compras a cuenta desde el celular.

Ella lo pide en la Libreta (o compra a cuenta en la caja) y a Daniel le llega
el aviso; aquí vive lo que ve y lo que pasa cuando toca un botón.

El aviso **trae los botones** (Daniel, 02/10: "me gustaría al momento que me
llegue el mensaje del bot decidir aprobarlo o no, no que solo me informe"). Y
trae con qué decidir: cuánto lleva ganado, cuál es su tope, qué le quedaría de
su pago.

Claridad (Daniel, 2026-11-12: «con las compras de las empleadas queda medio
confuso de entre y sale»). Son dos cosas distintas y cada mensaje lo dice
desde la primera línea:

- 💵 PRÉSTAMO: si lo apruebas, **sale** dinero del cajón.
- 🛍️ COMPRA A CUENTA: ya se llevó la mercancía y **no entró** dinero. El
  cajón ya está cuadrado (la venta y su retiro se cancelan); si no la
  autorizas, ella la paga en caja y entonces sí entra.

Cada mensaje dice qué pasa con el cajón y de qué pago se descuenta, sin
palabras de sistema («retiro», «ticket 9e9ad282») donde no hacen falta.
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


def _nombre(prestamo) -> str:
    return str(prestamo.employee_name or prestamo.employee_code)


def _pila(prestamo) -> str:
    return _nombre(prestamo).split()[0]


def _monto(prestamo) -> Decimal:
    return Decimal(str(prestamo.monto))


# ─── La lista (/prestamos) ───────────────────────────────────────────────


def texto_y_botones(session: Session) -> tuple[str, str]:
    """Lo que está esperando respuesta, separado en préstamos y compras."""
    from pos_uniformes.services import prestamos_service as pr

    pendientes = pr.pendientes(session)
    if not pendientes:
        return "No hay préstamos esperando respuesta. ✅", _teclado([[("‹ Menú", "m:raiz")]])

    prestamos = [p for p in pendientes if not _es_compra(p)]
    compras = [p for p in pendientes if _es_compra(p)]
    lineas: list[str] = []
    filas = []
    if prestamos:
        lineas.append("💵 PRÉSTAMOS · si los apruebas, sale dinero del cajón")
        for p in prestamos:
            cuando = _cuando(p)
            lineas.append(f"· {_nombre(p)} — ${_monto(p):,.2f}")
            lineas.append(f"   Para: {p.motivo}" + (f" · {cuando}" if cuando else ""))
            filas.append([
                (f"✅ {_nombre(p)} ${_monto(p):,.0f}", f"{PREFIJO}ok:{p.id}"),
                ("✖️ No", f"{PREFIJO}no:{p.id}"),
            ])
    if compras:
        if lineas:
            lineas.append("")
        lineas.append("🛍️ COMPRAS A CUENTA · ya se llevaron la mercancía, no entró dinero")
        for p in compras:
            lineas.append(f"· {_nombre(p)} — ${_monto(p):,.2f}")
            lineas.append(f"   {_cuando_se_descuenta(p)}")
            filas.append([
                (f"✅ {_nombre(p)} ${_monto(p):,.0f} a cuenta", f"{PREFIJO}ok:{p.id}"),
                ("✖️ Que lo pague", f"{PREFIJO}no:{p.id}"),
            ])
    filas.append([("‹ Menú", "m:raiz")])
    return "\n".join(lineas), _teclado(filas)


# ─── Lo que pasa al tocar un botón ───────────────────────────────────────


def texto_al_decidir(prestamo, aprobado: bool) -> str:
    """Lo que el bot contesta al decidir: qué pasó y qué pasa con el cajón."""
    nombre, monto = _nombre(prestamo), _monto(prestamo)
    if _es_compra(prestamo):
        if aprobado:
            return (
                f"✅ Compra a cuenta autorizada: {nombre}, ${monto:,.2f}.\n"
                f"• {_cuando_se_descuenta(prestamo)}\n"
                "• El cajón no cambia: ese dinero nunca entró."
            )
        return (
            f"✖️ Compra a cuenta NO autorizada: {nombre} paga ${monto:,.2f} en caja.\n"
            f"• Ahora el corte sí espera esos ${monto:,.2f} en el cajón: cóbraselos.\n"
            "• En su Libreta le sale el aviso."
        )
    if aprobado:
        return (
            f"✅ Préstamo aprobado: ${monto:,.2f} para {nombre}.\n"
            f"• Sale ${monto:,.2f} del cajón (ya quedó anotado como retiro del cajón).\n"
            "• Se le descuenta completo en su siguiente pago."
        )
    return f"✖️ Préstamo no aprobado: {nombre} no recibe los ${monto:,.2f}. Del cajón no sale nada."


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
                hecho = texto_al_decidir(p, True)
            elif que == "no":
                p = pr.rechazar(session, prestamo_id, quien=quien)
                aviso = "Rechazado"
                hecho = texto_al_decidir(p, False)
            else:
                return "No conozco ese botón", "", ""
            session.commit()
        except pr.NoSePuede as exc:
            session.rollback()
            texto, botones = texto_y_botones(session)
            return str(exc), texto, botones
        texto, botones = texto_y_botones(session)

    return aviso, hecho + "\n\n" + texto, botones


def _es_compra(prestamo) -> bool:
    from pos_uniformes.services.compra_a_cuenta_service import es_compra

    return es_compra(prestamo)


def _fecha_del_pago(prestamo) -> str | None:
    """«dom 22 nov» si el motivo de la compra lo dice."""
    motivo = str(prestamo.motivo or "")
    if "pago del " in motivo:
        return motivo.split("pago del ", 1)[1].split(" · ", 1)[0]
    return None


def _cuando_se_descuenta(prestamo) -> str:
    """«Se le descuenta completo en su pago del sáb 14 nov.»"""
    fecha = _fecha_del_pago(prestamo)
    if fecha:
        return f"Se le descuenta completo en su pago del {fecha}."
    return "Se le descuenta completo en su siguiente pago."


def botones_de(prestamo) -> str:
    """Los dos botones de UNA solicitud, para colgarlos de su propio aviso."""
    nombre = _pila(prestamo)
    if _es_compra(prestamo):
        return _teclado([
            [
                (f"✅ Autorizar a {nombre}", f"{PREFIJO}ok:{prestamo.id}"),
                ("✖️ Que lo pague", f"{PREFIJO}no:{prestamo.id}"),
            ],
            [("💵 Ver todos", "m:prestamos")],
        ])
    return _teclado([
        [
            (f"✅ Prestarle a {nombre}", f"{PREFIJO}ok:{prestamo.id}"),
            ("✖️ Ahora no", f"{PREFIJO}no:{prestamo.id}"),
        ],
        [("💵 Ver todos", "m:prestamos")],
    ])


# ─── El aviso que le llega a Daniel ──────────────────────────────────────


def aviso_de_solicitud(prestamo, *, session: Session | None = None) -> str:
    """El mensaje que le llega a Daniel cuando alguien pide o compra a cuenta.

    Con `session` trae además con qué decidir sin abrir nada (lo que lleva
    ganado, su tope, qué le quedaría del pago) y, en una compra, qué se
    llevó. Sin ella se queda en lo básico: el aviso tiene que salir aunque la
    consulta falle.
    """
    nombre, monto = _nombre(prestamo), _monto(prestamo)
    if _es_compra(prestamo):
        lineas = [f"🛍️ COMPRA A CUENTA · {nombre} compró a cuenta de su pago: ${monto:,.2f}"]
        llevo = _lo_que_se_llevo(prestamo, session)
        if llevo:
            lineas.append(f"Se llevó: {llevo}")
        lineas.append(_cuando_se_descuenta(prestamo))
        lineas.append("")
        lineas.append("💰 El cajón ya está cuadrado: no entró dinero y no falta nada.")
        lineas.append(f"• Si la autorizas: se le descuentan ${monto:,.2f} de ese pago.")
        lineas.append(f"• Si no: ella la paga en caja y esos ${monto:,.2f} sí entran al cajón.")
        detalle = _contexto(prestamo, session)
        if detalle:
            lineas.append("")
            lineas.extend(detalle)
        return "\n".join(lineas)
    lineas = [
        f"💵 PRÉSTAMO · {nombre} pide ${monto:,.2f} prestados",
        f"Para: {prestamo.motivo}",
        "",
        f"💰 Si lo apruebas: sale del cajón hoy (${monto:,.2f}) y se le descuenta",
        "completo en su siguiente pago.",
    ]
    detalle = _contexto(prestamo, session)
    if detalle:
        lineas.append("")
        lineas.extend(detalle)
    return "\n".join(lineas)


def _lo_que_se_llevo(prestamo, session: Session | None) -> str:
    """«Pantalón x1», de la venta que va con la compra. Vacío si no se halla."""
    if session is None:
        return ""
    try:
        import re

        from sqlalchemy import select

        from pos_uniformes.database.models import LibretaVenta
        from pos_uniformes.services.libreta_service import describir_detalle

        m = re.search(r"ticket\s+([0-9a-fA-F]{8})", str(prestamo.motivo or ""))
        if not m:
            return ""
        venta = session.scalars(
            select(LibretaVenta).where(LibretaVenta.operacion_uuid.like(f"{m.group(1).lower()}%")).limit(1)
        ).first()
        return describir_detalle(list(venta.detalle or [])) if venta is not None else ""
    except Exception:  # noqa: BLE001 — el aviso vale más que su adorno
        return ""


def _contexto(prestamo, session: Session | None) -> list[str]:
    """Las cifras con las que se decide. Vacío si no se pudieron sacar."""
    if session is None:
        return []
    try:
        from pos_uniformes.services import prestamos_service as pr

        code = str(prestamo.employee_code)
        monto = _monto(prestamo)
        ganado = pr.ganado_hasta_hoy(session, code)
        tope = pr.tope_para(session, code)
        # Lo demás que ya tiene encima (otro pedido sin responder o uno
        # aprobado por descontar), sin contar este mismo.
        encima = (pr.comprometido(session, code) - monto).quantize(Decimal("0.01"))
        debe = pr.total_por_cobrar(session, code)
    except Exception:  # noqa: BLE001 — el aviso vale más que su adorno
        return []

    lineas = [
        f"📊 Sus números ({_pila(prestamo)}):",
        f"• Lleva ganado: ${ganado:,.2f}",
        f"• Puede pedir hasta: ${tope:,.2f} (70 % de lo ganado)",
    ]
    if encima > 0:
        lineas.append(f"• Ya debe o tiene pedido: ${encima:,.2f} (aparte de este)")
    # «Del pago siguiente» se descuenta de un pago que aún no gana: no se adivina.
    if not getattr(prestamo, "cobrar_desde", None):
        lineas.append(f"• Le quedarían: ${ganado - monto - debe:,.2f} de su próximo pago")
    return lineas
