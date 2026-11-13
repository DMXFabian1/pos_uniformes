"""E4-B: aprobar o rechazar desde el celular a quién entra a Maximoda
Profesional o Mayorista.

La empleada lo propone en el kiosko (E4-C) y al dueño le llega el aviso con
los botones, igual que los días de descanso. Lo que se necesita para decidir
viene en el mismo aviso: quién es el cliente, cómo está hoy y cuánto ha
comprado, para no tener que ir a buscarlo a otro lado.

El bot solo aprueba o rechaza (P-E4-7): cambiar de programa o sacar a alguien
se hace en el POS con usuario ADMIN.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

#: Prefijo de los botones de esta pantalla.
PREFIJO = "mb:"


def _teclado(filas):
    from pos_uniformes.services import telegram_service

    return telegram_service.teclado(filas)


def es_de_membresias(dato: str) -> bool:
    return str(dato or "").startswith(PREFIJO)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _pila(texto: str | None) -> str:
    texto = str(texto or "").strip()
    return texto.split()[0] if texto else "?"


def _empleada(session: Session, code: str | None) -> str:
    from pos_uniformes.database.models import Empleada

    code = str(code or "").strip()
    if not code:
        return "alguien"
    empleada = session.scalar(select(Empleada).where(func.upper(Empleada.codigo) == code.upper()))
    return _pila(empleada.nombre_completo) if empleada is not None else code


def _cliente(session: Session, cliente_id: int):
    from pos_uniformes.database.models import Cliente

    return session.get(Cliente, int(cliente_id))


def _hace(fecha: datetime | None, ahora: datetime) -> str:
    """«hoy», «ayer» o «hace N días» por día de calendario en hora local
    (2026-11-12: antes eran bloques de 24 horas y una compra de anoche a
    las 20:00 salía «hoy» en el aviso de la mañana siguiente)."""
    if fecha is None:
        return ""
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)
    dias = (ahora.astimezone().date() - fecha.astimezone().date()).days
    if dias <= 0:
        return "hoy"
    if dias == 1:
        return "ayer"
    return f"hace {dias} días"


def _compras(session: Session, cliente_id: int) -> tuple[int, Decimal, datetime | None]:
    """Solo lectura: lo que este cliente ha comprado, de la Libreta (número
    de ventas, total y la última).

    2026-11-12 (Daniel: «la caja antigua ya no es de utilidad, todo lo demás
    corre en libreta y kioskos»): antes contaba en `Venta`, la tabla de la
    Caja antigua que ya no crece, y a un cliente que compra seguido en el
    kiosko le salía «Sin compras». Ahora cuenta en `LibretaVenta.cliente_id`:
    solo ventas (ni abonos ni apartados, ni la compra de una empleada con
    precio especial), incluidas las privadas (este aviso solo lo ve el
    dueño). Una operación anulada se borra de la Libreta, así que no cuenta.

    El total es el importe de las ventas (`monto_total`: lo que el cliente
    compró, incluido lo pagado con Monedero), no el dinero recibido del
    corte (`monto_neto`), y no descuenta los cambios de talla posteriores:
    es una referencia para decidir, no una cifra para cuadrar."""
    return _sumar(session, cliente_id, "venta")


def _apartados(session: Session, cliente_id: int) -> tuple[int, Decimal, datetime | None]:
    """Solo lectura: los apartados del cliente en la Libreta (número e
    importe apartado). Va en una línea aparte de las ventas y no se suma con
    los abonos, que contarían el mismo dinero dos veces. 2026-11-12."""
    return _sumar(session, cliente_id, "apartado")


def _sumar(session: Session, cliente_id: int, tipo: str) -> tuple[int, Decimal, datetime | None]:
    from pos_uniformes.database.models import LibretaVenta
    from pos_uniformes.services.libreta_service import contar_operaciones_sql, predicado_operacion

    fila = session.execute(
        select(
            # Ventas unidas en una operación son 1 compra (2026-11-13).
            contar_operaciones_sql(),
            func.coalesce(func.sum(LibretaVenta.monto_total), 0),
            func.max(LibretaVenta.created_at),
        ).where(LibretaVenta.cliente_id == int(cliente_id), predicado_operacion((tipo,)))
    ).one()
    return int(fila[0] or 0), Decimal(str(fila[1] or 0)), fila[2]


def _tipo(session: Session, cliente) -> str:
    from pos_uniformes.database.models import ClienteTipo

    tipo_id = getattr(cliente, "tipo_cliente_id", None)
    tipo = session.get(ClienteTipo, tipo_id) if tipo_id is not None else None
    return tipo.nombre if tipo is not None else "sin tipo"


def _resumen_cliente(session: Session, membresia, ahora: datetime) -> list[str]:
    from pos_uniformes.services.fidelizacion import membresia_service as ms

    cliente = _cliente(session, membresia.cliente_id)
    if cliente is None:
        return ["(la ficha de este cliente ya no existe)"]
    lineas = [f"👤 {cliente.nombre} · {cliente.codigo_cliente}", f"· Tipo hoy: {_tipo(session, cliente)}"]
    activa = ms.estado_de_cliente(session, int(cliente.id)).activa
    lineas.append(f"· Programa hoy: {activa.programa.nombre if activa is not None else 'ninguno'}")
    try:
        cuantas, total, ultima = _compras(session, int(cliente.id))
        n_apartados, total_apartados, ultimo_apartado = _apartados(session, int(cliente.id))
    except Exception:  # noqa: BLE001 — sin el historial se contesta igual
        cuantas = None
    if cuantas is None:
        lineas.append("· (no se pudo leer su historial de compras)")
        return lineas
    if cuantas:
        compras = "1 compra" if cuantas == 1 else f"{cuantas} compras"
        lineas.append(f"· {compras} por ${total:,.0f} (la última {_hace(ultima, ahora)})")
    if n_apartados:
        # 2026-11-12: quien compra por apartado y liquida con abonos no
        # sale «Sin compras»; va aparte para no sumar el dinero dos veces.
        apartados = "1 apartado" if n_apartados == 1 else f"{n_apartados} apartados"
        lineas.append(f"· {apartados} por ${total_apartados:,.0f} (el último {_hace(ultimo_apartado, ahora)})")
    if not cuantas and not n_apartados:
        lineas.append("· Sin compras registradas a su nombre")
    return lineas


def _que_pasa_al_aprobar(membresia) -> str:
    programa = membresia.programa
    nombres = {"DOCENTE": "Docente", "MAYORISTA": "Mayorista"}
    tipo = nombres.get(programa.tipo_sugerido_clave or "", programa.tipo_sugerido_clave)
    texto = f"Si lo apruebas entra a {programa.nombre}"
    if tipo:
        texto += f" y su tipo pasa a {tipo}"
        if programa.tipo_sugerido_clave == "MAYORISTA":
            texto += " (si es Institución, se queda Institución)"
    return texto + "."


def aviso_de_propuesta(session: Session, membresia, *, ahora: datetime | None = None) -> str:
    """El mensaje que le llega al dueño cuando una empleada propone a alguien."""
    ahora = ahora or _ahora()
    quien = _empleada(session, membresia.propuesta_por_employee_code)
    lineas = [
        f"⭐ {quien} propone a un cliente para {membresia.programa.nombre} ({_hace(membresia.created_at, ahora)})",
        f"Por qué: {membresia.motivo_propuesta or '—'}",
        "",
    ]
    lineas.extend(_resumen_cliente(session, membresia, ahora))
    lineas.append("")
    lineas.append(_que_pasa_al_aprobar(membresia))
    return "\n".join(lineas)


def botones_de(membresia) -> str:
    """Los botones de UNA propuesta, para colgarlos de su propio aviso."""
    return _teclado([
        [("✅ Aprobar", f"{PREFIJO}ok:{membresia.id}"), ("✖️ Rechazar", f"{PREFIJO}no:{membresia.id}")],
        [("⭐ Ver pendientes", f"{PREFIJO}lista")],
    ])


def aviso_de_caducadas(session: Session, vencidas) -> str:
    quienes = []
    for m in vencidas:
        cliente = _cliente(session, m.cliente_id)
        quienes.append(f"{cliente.nombre if cliente is not None else '?'} → {m.programa.nombre}")
    return (
        f"⌛ Caducaron {len(vencidas)} propuestas de programa sin respuesta en 7 días:\n· "
        + "\n· ".join(quienes)
        + "\nNo cambió nada; a quien las propuso se le avisa en la Libreta."
    )


# ── La lista: «⭐ Programas» ───────────────────────────────────────────────


def texto_y_botones(session: Session, *, ahora: datetime | None = None) -> tuple[str, str]:
    from pos_uniformes.services.fidelizacion import membresia_service as ms

    ahora = ahora or _ahora()
    pendientes = ms.pendientes(session)
    if not pendientes:
        return "No hay propuestas de programa esperando respuesta. ✅", _teclado([[("‹ Menú", "m:raiz")]])
    lineas = ["⭐ Propuestas por responder:", ""]
    filas = []
    for m in pendientes:
        cliente = _cliente(session, m.cliente_id)
        nombre = cliente.nombre if cliente is not None else f"#{m.cliente_id}"
        lineas.append(f"· {nombre} → {m.programa.nombre} ({_hace(m.created_at, ahora)}, "
                      f"la propuso {_empleada(session, m.propuesta_por_employee_code)})")
        filas.append([(f"👀 {_pila(nombre)} · {m.programa.nombre.replace('Maximoda ', '')}", f"{PREFIJO}ver:{m.id}")])
    lineas.append("")
    lineas.append("Las que nadie conteste en 7 días caducan solas.")
    filas.append([("‹ Menú", "m:raiz")])
    return "\n".join(lineas), _teclado(filas)


def detalle(session: Session, membresia_id: int, *, ahora: datetime | None = None) -> tuple[str, list]:
    from pos_uniformes.database.models import Membresia
    from pos_uniformes.services.fidelizacion import membresia_service as ms

    m = session.get(Membresia, int(membresia_id))
    if m is None:
        return "Esa propuesta ya no existe.", []
    texto = aviso_de_propuesta(session, m, ahora=ahora)
    if m.estado != ms.PENDIENTE:
        return texto + f"\n\nYa quedó {m.estado}.", []
    return texto, [[("✅ Aprobar", f"{PREFIJO}ok:{m.id}"), ("✖️ Rechazar", f"{PREFIJO}no:{m.id}")]]


# ── Botones ────────────────────────────────────────────────────────────────


def atender(dato: str, *, session_factory, quien: str = "") -> tuple[str, str, str]:
    """Un botón de programas: (aviso corto, texto nuevo, botones nuevos).

    `quien` se acepta por simetría con los demás botones, pero lo resuelto
    queda siempre a nombre de «dueño (Telegram)»: el bot solo atiende el chat
    del dueño."""
    from pos_uniformes.services.fidelizacion import membresia_service as ms

    accion = str(dato or "")[len(PREFIJO):]
    que, _, crudo = accion.partition(":")

    def _con_volver(filas):
        return _teclado(list(filas) + [[("‹ Programas", f"{PREFIJO}lista")]])

    if que == "lista":
        with session_factory() as session:
            texto, botones = texto_y_botones(session)
        return "", texto, botones
    try:
        membresia_id = int(crudo)
    except ValueError:
        return "No conozco ese botón", "", ""

    if que == "ver":
        with session_factory() as session:
            texto, filas = detalle(session, membresia_id)
        return "", texto, _con_volver(filas)
    if que not in ("ok", "no"):
        return "No conozco ese botón", "", ""

    with session_factory() as session:
        try:
            if que == "ok":
                m = ms.aprobar_por_dueno(session, membresia_id)
                aviso = "Aprobado"
            else:
                m = ms.rechazar_por_dueno(session, membresia_id)
                aviso = "Rechazado"
            cliente = _cliente(session, m.cliente_id)
            nombre = cliente.nombre if cliente is not None else f"#{m.cliente_id}"
            programa = m.programa.nombre
            session.commit()
        except ms.NoSePuede as exc:
            session.rollback()
            texto, botones = texto_y_botones(session)
            return str(exc), texto, botones
        if que == "ok":
            hecho = f"✅ {nombre} ya está en {programa}.\nA quien lo propuso se le avisa en la Libreta."
        else:
            hecho = f"✖️ {nombre} no entra a {programa}.\nA quien lo propuso se le avisa en la Libreta."
        texto, botones = texto_y_botones(session)
    return aviso, hecho + "\n\n" + texto, botones


def avisar_a_daniel(session: Session, membresia) -> None:
    """Le llega al instante; sin internet (o sin token en el kiosko) queda en
    la cola de alertas que el bot de la PC servidor manda en cuanto puede.
    Nunca truena: la propuesta ya quedó guardada y el recordatorio diario la
    vuelve a mostrar."""
    import logging

    texto = aviso_de_propuesta(session, membresia)
    botones = botones_de(membresia)
    try:
        from pos_uniformes.services.telegram_service import enviar_mensaje

        enviar_mensaje(texto, botones=botones, conservar=True)
        return
    except Exception:  # noqa: BLE001
        pass
    try:
        from pos_uniformes.services.alertas_service import encolar

        encolar(session, texto, botones)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("Programas: no se pudo avisar de la propuesta")
