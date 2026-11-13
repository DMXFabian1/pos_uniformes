"""Membresías a programas (E4-A). Las reglas viven aquí, no en las pantallas.

Aquí solo se lleva la membresía: nunca toca ventas, Libreta, Monedero, promo
3pz ni el 5 % de empleada. Lo que gana cada programa (el % de Monedero de
`programa.tasa_monedero`, el descuento de Mayorista) lo aplica E5 en
`monedero_service` (2026-11-12, «solucionemos estos»: Club ya gana Monedero).

Reglas (D1 ajustada, P7, P-E4-1..7):

- Un cliente tiene como máximo UNA membresía activa y UNA propuesta
  pendiente. Lo garantizan índices únicos parciales en la base; aquí se
  revisa antes para dar un mensaje claro, y si dos empleadas chocan al mismo
  tiempo, el choque de la base se traduce al mismo mensaje.
- La empleada inscribe directo solo a programas `directo_empleada` (Club).
  Los `aprobacion_dueno` (Profesional, Mayorista) los propone con motivo y
  quedan pendientes hasta que el dueño los aprueba o rechaza (bot) o un ADMIN
  lo hace en el POS.
- Al aprobar, la membresía activa anterior queda `reemplazada` en la misma
  transacción, y el tipo del cliente pasa al sugerido por el programa
  (P-E4-2), salvo Institución para Mayorista.
- Cambiar de programa o sacar a alguien es solo del ADMIN en el POS, con
  motivo (P-E4-7).
- Una propuesta sin respuesta expira a los 7 días (P-E4-4).
- Cada cambio deja un `membresia_evento` inmutable.
- Las fichas inactivas o archivadas no se inscriben ni se proponen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    Cliente,
    ClienteTipo,
    Empleada,
    Membresia,
    MembresiaEvento,
    Programa,
    RolUsuario,
    Usuario,
)
from pos_uniformes.services.clientes import identidad_service as identidad

# estados de la membresía
PENDIENTE = "pendiente"
ACTIVA = "activa"
RECHAZADA = "rechazada"
EXPIRADA = "expirada"
CANCELADA = "cancelada"
VENCIDA = "vencida"
REEMPLAZADA = "reemplazada"

DIRECTO_EMPLEADA = "directo_empleada"
APROBACION_DUENO = "aprobacion_dueno"
PROGRAMA_ACTIVO = "activo"

# eventos
EV_ALTA = "alta"
EV_PROPUESTA = "propuesta"
EV_APROBACION = "aprobacion"
EV_RECHAZO = "rechazo"
EV_EXPIRACION = "expiracion"
EV_REEMPLAZO = "reemplazo"
EV_CAMBIO_PROGRAMA = "cambio_programa"
EV_CANCELACION = "cancelacion"

DIAS_PARA_EXPIRAR = 7
MOTIVO_PROPUESTA_MINIMO = 10
MOTIVO_ADMIN_MINIMO = 5
QUIEN_DUENO_TELEGRAM = "dueño (Telegram)"
ORIGEN_TELEGRAM = "telegram"


_logger = logging.getLogger(__name__)


class NoSePuede(ValueError):
    """La acción no procede; el mensaje se le puede mostrar tal cual a quien la pidió."""


@dataclass(frozen=True)
class EstadoCliente:
    """Lo que ven la barra del cliente y la ficha."""

    activa: Membresia | None
    pendiente: Membresia | None


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


# -- consultas ------------------------------------------------------------------


def programa_por_clave(session: Session, clave: str) -> Programa | None:
    return session.scalar(select(Programa).where(Programa.clave == (clave or "").strip().upper()))


def programas_activos(session: Session) -> list[Programa]:
    return list(
        session.scalars(select(Programa).where(Programa.estado == PROGRAMA_ACTIVO).order_by(Programa.orden, Programa.id))
    )


def estado_de_cliente(session: Session, cliente_id: int) -> EstadoCliente:
    filas = list(
        session.scalars(
            select(Membresia).where(Membresia.cliente_id == int(cliente_id), Membresia.estado.in_((ACTIVA, PENDIENTE)))
        )
    )
    return EstadoCliente(
        activa=next((m for m in filas if m.estado == ACTIVA), None),
        pendiente=next((m for m in filas if m.estado == PENDIENTE), None),
    )


def historial(session: Session, cliente_id: int) -> list[tuple[Membresia, MembresiaEvento]]:
    return list(
        session.execute(
            select(Membresia, MembresiaEvento)
            .join(MembresiaEvento, MembresiaEvento.membresia_id == Membresia.id)
            .where(Membresia.cliente_id == int(cliente_id))
            .order_by(MembresiaEvento.id.desc())
        ).all()
    )


def pendientes(session: Session) -> list[Membresia]:
    return list(session.scalars(select(Membresia).where(Membresia.estado == PENDIENTE).order_by(Membresia.created_at)))


# -- validaciones -----------------------------------------------------------------


def _cliente_vigente(session: Session, cliente_id: int) -> Cliente:
    cliente = session.get(Cliente, int(cliente_id))
    if cliente is None:
        raise NoSePuede("No se encontró el cliente.")
    if cliente.archivado_en is not None or not cliente.activo:
        raise NoSePuede("La ficha de este cliente no está activa.")
    return cliente


def _programa_vigente(session: Session, clave: str) -> Programa:
    programa = programa_por_clave(session, clave)
    if programa is None or programa.estado != PROGRAMA_ACTIVO:
        raise NoSePuede(f"El programa {clave} no está disponible.")
    return programa


def _empleada_activa(session: Session, employee_code: str | None) -> Empleada:
    codigo = (employee_code or "").strip()
    empleada = session.scalar(
        select(Empleada).where(func.upper(Empleada.codigo) == codigo.upper(), Empleada.activo.is_(True))
    ) if codigo else None
    if empleada is None:
        raise PermissionError("Se requiere una empleada activa.")
    return empleada


def _admin(session: Session, usuario_id: int | None) -> Usuario:
    usuario = session.get(Usuario, int(usuario_id)) if usuario_id is not None else None
    if usuario is None or not usuario.activo or usuario.rol != RolUsuario.ADMIN:
        raise PermissionError("Solo un ADMIN activo puede hacer esto.")
    return usuario


def _motivo(texto: str | None, minimo: int) -> str:
    limpio = (texto or "").strip()
    if len(limpio) < minimo:
        raise NoSePuede(f"Escribe un motivo de al menos {minimo} caracteres.")
    return limpio[:255]


def _evento(
    session: Session,
    membresia: Membresia,
    tipo: str,
    *,
    antes: str | None,
    motivo: str | None = None,
    detalle: dict | None = None,
    usuario_id: int | None = None,
    employee_code: str | None = None,
    quien: str | None = None,
) -> None:
    session.add(
        MembresiaEvento(
            membresia_id=int(membresia.id),
            tipo=tipo,
            antes=antes,
            despues=membresia.estado,
            motivo=motivo,
            detalle=detalle or {},
            usuario_id=usuario_id,
            employee_code=employee_code,
            quien=quien,
        )
    )


def _guardar(session: Session, membresia: Membresia) -> None:
    """Inserta respetando los candados; un choque se vuelve un mensaje claro."""
    punto = session.begin_nested()
    try:
        session.add(membresia)
        session.flush()
    except IntegrityError as exc:
        punto.rollback()
        raise NoSePuede("Este cliente ya tiene un programa o una propuesta en curso.") from exc
    punto.commit()


def _hasta(programa: Programa, desde: datetime) -> datetime | None:
    return desde + timedelta(days=int(programa.vigencia_dias)) if programa.vigencia_dias else None


# -- empleada (kiosko) ------------------------------------------------------------


def inscribir_por_empleada(session: Session, *, cliente_id: int, programa_clave: str, employee_code: str) -> Membresia:
    """Club: queda activa al instante."""
    empleada = _empleada_activa(session, employee_code)
    cliente = _cliente_vigente(session, cliente_id)
    programa = _programa_vigente(session, programa_clave)
    if programa.ingreso_modo != DIRECTO_EMPLEADA:
        raise NoSePuede(f"{programa.nombre} se propone; lo aprueba el dueño.")
    estado = estado_de_cliente(session, int(cliente.id))
    if estado.activa is not None:
        raise NoSePuede(f"Ya está en {estado.activa.programa.nombre}.")
    ahora = _ahora()
    membresia = Membresia(
        cliente_id=int(cliente.id),
        programa_id=int(programa.id),
        estado=ACTIVA,
        desde=ahora,
        hasta=_hasta(programa, ahora),
        propuesta_por_employee_code=empleada.codigo,
        avisada_at=ahora,  # lo inscribió ella: no hay respuesta que avisarle
    )
    _guardar(session, membresia)
    _evento(session, membresia, EV_ALTA, antes=None, employee_code=empleada.codigo, quien=empleada.nombre_completo)
    session.flush()
    return membresia


CLUB = "CLUB"


def tasa_monedero_de_programa(session: Session, clave: str) -> Decimal | None:
    """El % de Monedero que gana quien entra hoy al programa `clave` (Club 5
    en la caja), leído de la base. None si el Monedero está apagado, si el
    programa no existe o si da 0 %: entonces no se promete nada.

    2026-11-12 (Daniel, «solucionemos estos»): el aviso de inscribir a Club
    decía «por ahora no cambia ningún precio», pero Club ya gana Monedero."""
    from pos_uniformes.services import monedero_service as mon

    if mon.tasa_vigente(session) is None:
        return None
    programa = programa_por_clave(session, clave)
    if programa is None or programa.estado != PROGRAMA_ACTIVO:
        return None
    tasa = Decimal(str(programa.tasa_monedero or 0))
    return tasa if tasa > 0 else None


def texto_inscribir_club(nombre: str, tasa: Decimal | None) -> str:
    """La pregunta antes de inscribir a Club en el kiosko. Sin tasa (no se
    pudo leer o el Monedero no da nada) no se menciona ningún %.

    Desde esta misma compra es cierto: antes de cobrar el kiosko vuelve a leer
    al cliente (T3) y la Libreta abona con el programa que tenga al momento de
    la venta. Lo de Oferta o Liquidación no suma (E7)."""
    pregunta = f"¿Inscribir a {nombre} a Maximoda Club?\n\n"
    if tasa is None or Decimal(str(tasa)) <= 0:
        return pregunta + "Queda como miembro desde hoy."
    pct = format(Decimal(str(tasa)).normalize(), "f")
    return (
        pregunta
        + f"Queda como miembro desde hoy y gana {pct} % de cada compra en su Monedero, "
        "desde esta misma compra. Lo de Oferta o Liquidación no suma."
    )


def inscribir_al_club_al_registrar(session: Session, *, cliente_id: int, employee_code: str | None) -> Membresia | None:
    """El cliente que se registra en el kiosko entra directo a Maximoda Club,
    sin que la empleada apriete nada (Daniel, 2026-11-10).

    Va en la misma transacción que el alta, dentro de un punto de guardado: si
    no se puede (no hay empleada, el Club no está disponible), regresa None y
    el alta sigue igual, sin programa. La empleada lo puede inscribir después
    desde la franja."""
    if not (employee_code or "").strip():
        return None
    punto = None
    try:
        punto = session.begin_nested()
        membresia = inscribir_por_empleada(
            session, cliente_id=int(cliente_id), programa_clave=CLUB, employee_code=str(employee_code)
        )
        punto.commit()
    except (NoSePuede, PermissionError) as exc:
        if punto is not None:
            punto.rollback()
        _logger.info("Alta sin Club para el cliente %s: %s", cliente_id, exc)
        return None
    except Exception:  # noqa: BLE001 - el Club nunca tumba el alta
        if punto is not None and punto.is_active:
            punto.rollback()
        _logger.exception("Alta sin Club para el cliente %s: falló la inscripción", cliente_id)
        return None
    return membresia


def proponer(
    session: Session, *, cliente_id: int, programa_clave: str, employee_code: str, motivo: str
) -> Membresia:
    """Profesional o Mayorista: queda pendiente hasta que el dueño decida."""
    empleada = _empleada_activa(session, employee_code)
    cliente = _cliente_vigente(session, cliente_id)
    programa = _programa_vigente(session, programa_clave)
    if programa.ingreso_modo != APROBACION_DUENO:
        raise NoSePuede(f"{programa.nombre} no necesita aprobación: inscríbelo directo.")
    texto = _motivo(motivo, MOTIVO_PROPUESTA_MINIMO)
    estado = estado_de_cliente(session, int(cliente.id))
    if estado.pendiente is not None:
        raise NoSePuede(f"Ya hay una propuesta a {estado.pendiente.programa.nombre} esperando respuesta.")
    if estado.activa is not None and estado.activa.programa_id == programa.id:
        raise NoSePuede(f"Ya está en {programa.nombre}.")
    membresia = Membresia(
        cliente_id=int(cliente.id),
        programa_id=int(programa.id),
        estado=PENDIENTE,
        propuesta_por_employee_code=empleada.codigo,
        motivo_propuesta=texto,
    )
    _guardar(session, membresia)
    _evento(
        session,
        membresia,
        EV_PROPUESTA,
        antes=None,
        motivo=texto,
        employee_code=empleada.codigo,
        quien=empleada.nombre_completo,
    )
    session.flush()
    return membresia


# -- dueño (bot) o ADMIN (POS) --------------------------------------------------------


def _pendiente(session: Session, membresia_id: int) -> Membresia:
    membresia = session.get(Membresia, int(membresia_id), with_for_update=True)
    if membresia is None:
        raise NoSePuede("No encontré esa propuesta.")
    if membresia.estado != PENDIENTE:
        raise NoSePuede(f"Esa propuesta ya no está pendiente: quedó {membresia.estado}.")
    return membresia


def _aplicar_tipo_sugerido(session: Session, cliente: Cliente, programa: Programa, *, quien: str, usuario_id, origen):
    """P-E4-2: al aprobar, el tipo pasa al del programa (Mayorista respeta Institución)."""
    clave = programa.tipo_sugerido_clave
    if not clave:
        return
    actual = session.get(ClienteTipo, cliente.tipo_cliente_id) if cliente.tipo_cliente_id is not None else None
    if actual is not None and (actual.clave == clave or (clave == "MAYORISTA" and actual.clave == "INSTITUCION")):
        return
    nuevo = identidad.tipo_por_clave(session, clave)
    if nuevo is None or not nuevo.activo:
        return
    cliente.tipo_cliente_id = int(nuevo.id)
    session.add(cliente)
    identidad.registrar_evento(
        session,
        cliente,
        "cambio_tipo",
        detalle={"antes": actual.clave if actual is not None else None, "despues": clave, "por": f"programa {programa.clave}"},
        usuario_id=usuario_id,
        origen=origen,
    )


def _resolver_aprobacion(session: Session, membresia: Membresia, *, quien: str, usuario_id: int | None, origen: str):
    ahora = _ahora()
    cliente = session.get(Cliente, membresia.cliente_id)
    if cliente is None or cliente.archivado_en is not None or not cliente.activo:
        raise NoSePuede("La ficha de este cliente ya no está activa; no se puede aprobar.")
    programa = membresia.programa
    if programa.estado != PROGRAMA_ACTIVO:
        raise NoSePuede(f"El programa {programa.nombre} ya no está disponible.")
    anterior = estado_de_cliente(session, int(cliente.id)).activa
    if anterior is not None:
        anterior.estado = REEMPLAZADA
        anterior.hasta = ahora
        anterior.resuelta_por = quien
        anterior.resuelta_en = ahora
        session.add(anterior)
        session.flush()  # libera el candado de «una activa» antes de activar la nueva
        _evento(
            session,
            anterior,
            EV_REEMPLAZO,
            antes=ACTIVA,
            detalle={"por_programa": programa.clave},
            usuario_id=usuario_id,
            quien=quien,
        )
    membresia.estado = ACTIVA
    membresia.desde = ahora
    membresia.hasta = _hasta(programa, ahora)
    membresia.resuelta_por = quien
    membresia.resuelta_en = ahora
    session.add(membresia)
    session.flush()
    _evento(session, membresia, EV_APROBACION, antes=PENDIENTE, usuario_id=usuario_id, quien=quien)
    _aplicar_tipo_sugerido(session, cliente, programa, quien=quien, usuario_id=usuario_id, origen=origen)
    session.flush()
    return membresia


def aprobar_por_dueno(session: Session, membresia_id: int) -> Membresia:
    """Botón ✅ del bot. El bot ya valida que el chat sea el del dueño."""
    membresia = _pendiente(session, membresia_id)
    return _resolver_aprobacion(session, membresia, quien=QUIEN_DUENO_TELEGRAM, usuario_id=None, origen=ORIGEN_TELEGRAM)


def rechazar_por_dueno(session: Session, membresia_id: int, *, motivo: str | None = None) -> Membresia:
    membresia = _pendiente(session, membresia_id)
    return _rechazar(session, membresia, quien=QUIEN_DUENO_TELEGRAM, usuario_id=None, motivo=motivo)


def aprobar_por_admin(session: Session, membresia_id: int, *, usuario_id: int) -> Membresia:
    usuario = _admin(session, usuario_id)
    membresia = _pendiente(session, membresia_id)
    return _resolver_aprobacion(
        session, membresia, quien=usuario.username, usuario_id=int(usuario.id), origen=identidad.ORIGEN_POS_ADMIN
    )


def rechazar_por_admin(session: Session, membresia_id: int, *, usuario_id: int, motivo: str) -> Membresia:
    usuario = _admin(session, usuario_id)
    membresia = _pendiente(session, membresia_id)
    texto = _motivo(motivo, MOTIVO_ADMIN_MINIMO)
    return _rechazar(session, membresia, quien=usuario.username, usuario_id=int(usuario.id), motivo=texto)


def _rechazar(session: Session, membresia: Membresia, *, quien: str, usuario_id: int | None, motivo: str | None):
    membresia.estado = RECHAZADA
    membresia.resuelta_por = quien
    membresia.resuelta_en = _ahora()
    membresia.motivo_resolucion = (motivo or "").strip()[:255] or None
    session.add(membresia)
    _evento(session, membresia, EV_RECHAZO, antes=PENDIENTE, motivo=membresia.motivo_resolucion, usuario_id=usuario_id, quien=quien)
    session.flush()
    return membresia


# -- solo ADMIN en el POS (P-E4-7) -------------------------------------------------------


def inscribir_por_admin(session: Session, *, cliente_id: int, programa_clave: str, usuario_id: int, motivo: str) -> Membresia:
    """El ADMIN inscribe directo a cualquier programa, o cambia el actual (con motivo)."""
    usuario = _admin(session, usuario_id)
    cliente = _cliente_vigente(session, cliente_id)
    programa = _programa_vigente(session, programa_clave)
    texto = _motivo(motivo, MOTIVO_ADMIN_MINIMO)
    estado = estado_de_cliente(session, int(cliente.id))
    if estado.activa is not None and estado.activa.programa_id == programa.id:
        raise NoSePuede(f"Ya está en {programa.nombre}.")
    if estado.pendiente is not None:
        raise NoSePuede("Primero aprueba o rechaza la propuesta pendiente de este cliente.")
    membresia = Membresia(
        cliente_id=int(cliente.id),
        programa_id=int(programa.id),
        estado=PENDIENTE,
        alta_por_usuario_id=int(usuario.id),
        motivo_propuesta=texto,
    )
    _guardar(session, membresia)
    tipo_evento = EV_CAMBIO_PROGRAMA if estado.activa is not None else EV_ALTA
    _evento(session, membresia, tipo_evento, antes=None, motivo=texto, usuario_id=int(usuario.id), quien=usuario.username)
    return _resolver_aprobacion(
        session, membresia, quien=usuario.username, usuario_id=int(usuario.id), origen=identidad.ORIGEN_POS_ADMIN
    )


def sacar_del_programa(session: Session, *, cliente_id: int, usuario_id: int, motivo: str) -> Membresia:
    usuario = _admin(session, usuario_id)
    texto = _motivo(motivo, MOTIVO_ADMIN_MINIMO)
    activa = estado_de_cliente(session, int(cliente_id)).activa
    if activa is None:
        raise NoSePuede("Este cliente no está en ningún programa.")
    activa.estado = CANCELADA
    activa.hasta = _ahora()
    activa.resuelta_por = usuario.username
    activa.resuelta_en = activa.hasta
    activa.motivo_resolucion = texto
    session.add(activa)
    _evento(session, activa, EV_CANCELACION, antes=ACTIVA, motivo=texto, usuario_id=int(usuario.id), quien=usuario.username)
    session.flush()
    return activa


# -- tarea periódica (la corre el bot) ------------------------------------------------------


def expirar_pendientes(session: Session, *, ahora: datetime | None = None, dias: int = DIAS_PARA_EXPIRAR) -> list[Membresia]:
    """P-E4-4: propuestas sin respuesta en `dias` días pasan a `expirada`. Sin commit."""
    limite = (ahora or _ahora()) - timedelta(days=dias)
    vencidas = list(
        session.scalars(select(Membresia).where(Membresia.estado == PENDIENTE, Membresia.created_at <= limite))
    )
    for membresia in vencidas:
        membresia.estado = EXPIRADA
        membresia.resuelta_en = ahora or _ahora()
        membresia.resuelta_por = "sistema"
        session.add(membresia)
        _evento(session, membresia, EV_EXPIRACION, antes=PENDIENTE, detalle={"dias": dias}, quien="sistema")
    session.flush()
    return vencidas


#: El primer recordatorio sale a las 24 h de la propuesta y luego uno al día (P-E4-4).
HORAS_ENTRE_RECORDATORIOS = 24


def tarea_periodica(session: Session, *, ahora: datetime | None = None) -> list[tuple[str, str]]:
    """Caduca las propuestas de más de 7 días y arma el recordatorio diario de
    las que siguen esperando. Sin commit: lo confirma quien encola el aviso,
    así un aviso que no entró se vuelve a intentar en la siguiente vuelta."""
    from pos_uniformes.services import telegram_membresias_service as tm

    ahora = ahora or _ahora()
    avisos: list[tuple[str, str]] = []
    vencidas = expirar_pendientes(session, ahora=ahora)
    if vencidas:
        avisos.append((tm.aviso_de_caducadas(session, vencidas), ""))
    for membresia in pendientes(session):
        ultimo = membresia.ultimo_recordatorio_at or membresia.created_at
        if ultimo is None:
            continue
        if ultimo.tzinfo is None:
            ultimo = ultimo.replace(tzinfo=timezone.utc)
        if ahora - ultimo < timedelta(hours=HORAS_ENTRE_RECORDATORIOS):
            continue
        membresia.ultimo_recordatorio_at = ahora
        membresia.recordatorios = int(membresia.recordatorios or 0) + 1
        session.add(membresia)
        session.flush()
        avisos.append(("⏰ Sigue sin respuesta:\n" + tm.aviso_de_propuesta(session, membresia, ahora=ahora),
                       tm.botones_de(membresia)))
    return avisos


# -- lo que ve la empleada de vuelta (P-E4-5) -------------------------------------------------------

_RESUELTAS_PARA_ELLA = (ACTIVA, RECHAZADA, EXPIRADA, REEMPLAZADA, CANCELADA)


def respuestas_sin_ver(session: Session, employee_code: str) -> list[Membresia]:
    """Propuestas suyas que ya se resolvieron y ella no ha visto. Solo las que
    pasaron por propuesta: un Club que inscribió ella misma nace visto."""
    code = str(employee_code or "").strip().upper()
    if not code:
        return []
    return list(
        session.scalars(
            select(Membresia)
            .where(
                func.upper(Membresia.propuesta_por_employee_code) == code,
                Membresia.resuelta_en.is_not(None),
                Membresia.estado.in_(_RESUELTAS_PARA_ELLA),
                Membresia.avisada_at.is_(None),
            )
            .order_by(Membresia.id)
        )
    )


def marcar_vista(session: Session, membresia_id: int, employee_code: str) -> None:
    membresia = session.get(Membresia, int(membresia_id))
    code = str(employee_code or "").strip().upper()
    if membresia is None or membresia.avisada_at is not None:
        return
    if str(membresia.propuesta_por_employee_code or "").strip().upper() != code:
        return
    membresia.avisada_at = _ahora()
    session.add(membresia)
    session.flush()


def texto_de_respuesta(session: Session, membresia: Membresia) -> str:
    """Lo que se le enseña a ella en la Libreta."""
    cliente = session.get(Cliente, membresia.cliente_id)
    quien = cliente.nombre if cliente is not None else f"el cliente #{membresia.cliente_id}"
    programa = membresia.programa.nombre
    if membresia.estado in (ACTIVA, REEMPLAZADA, CANCELADA) and membresia.desde is not None:
        texto = f"✅ Daniel aprobó a {quien} en {programa}."
    elif membresia.estado == RECHAZADA:
        texto = f"✖️ Daniel no aprobó a {quien} en {programa}."
        if membresia.motivo_resolucion:
            texto += f"\n«{membresia.motivo_resolucion}»"
    elif membresia.estado == EXPIRADA:
        texto = (f"⌛ Tu propuesta de {quien} para {programa} se quedó sin respuesta "
                 f"{DIAS_PARA_EXPIRAR} días y caducó. Si sigue valiendo la pena, vuelve a proponerlo.")
    else:
        texto = f"La propuesta de {quien} para {programa} quedó {membresia.estado}."
    return texto
