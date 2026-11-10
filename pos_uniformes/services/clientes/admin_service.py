"""Administración de fichas de clientes (E1-C1). Solo ADMIN.

Reglas:

- Editar una ficha toca SOLO su identidad (nombre, teléfono, notas). Nunca
  lee ni escribe el nivel histórico, `descuento_preferente`, el enum
  `tipo_cliente` ni `nivel_asignado_*`, y nunca llama a `LoyaltyService`
  (C1, D5). Los niveles viejos no forman parte del modelo nuevo.
- El tipo se cambia con su propia acción y su propio evento (C2). Un tipo es
  una etiqueta: no da nivel, membresía ni beneficio.
- Activar o desactivar pide un motivo (C1). Archivar es reversible y no borra
  nada: las ventas, la Libreta, los apartados, los presupuestos y el
  Monedero conservan su `cliente_id` (C12).
- Todo cambio deja un evento en `cliente_evento`, con el antes y el después.
  Guardar sin cambios no deja evento.
- Nada se borra físicamente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Cliente, ClienteEvento, ClienteTipo, Monedero, RolUsuario, Usuario
from pos_uniformes.services.clientes import identidad_service as identidad
from pos_uniformes.services.clientes.telefono import normalizar_telefono, solo_digitos

EVENTO_EDICION = "edicion"
EVENTO_CAMBIO_TIPO = "cambio_tipo"
EVENTO_DESACTIVACION = "desactivacion"
EVENTO_REACTIVACION = "reactivacion"
EVENTO_ARCHIVADO = "archivado"
EVENTO_DESARCHIVADO = "desarchivado"

ORIGEN_ADMIN = identidad.ORIGEN_POS_ADMIN
MOTIVO_MINIMO = 5
LIMITE_LISTA = 500

ESTADO_ACTIVOS = "activos"
ESTADO_INACTIVOS = "inactivos"
ESTADO_ARCHIVADOS = "archivados"
ESTADO_TODOS = "todos"
ORIGEN_ANTERIOR = "anterior"  # fichas sin `origen_alta` (anteriores a E1-A)
# E4-D: filtro «Programa» de la lista. Además de estas dos, vale la clave de un programa.
PROGRAMA_NINGUNO = "NINGUNO"
PROGRAMA_PENDIENTE = "PENDIENTE"


# -- permisos -----------------------------------------------------------------


def exigir_admin(session: Session, usuario_id: int | None) -> Usuario:
    """El permiso se valida aquí, no solo en la pantalla (mínimo privilegio)."""
    usuario = session.get(Usuario, int(usuario_id)) if usuario_id is not None else None
    if usuario is None or not usuario.activo:
        raise PermissionError("Se requiere un usuario ADMIN activo.")
    if usuario.rol != RolUsuario.ADMIN:
        raise PermissionError("Solo ADMIN puede administrar fichas de clientes.")
    return usuario


def _cliente(session: Session, cliente_id: int) -> Cliente:
    cliente = session.get(Cliente, int(cliente_id))
    if cliente is None:
        raise ValueError("No se encontró el cliente.")
    return cliente


def _no_archivado(cliente: Cliente) -> None:
    if cliente.archivado_en is not None:
        raise ValueError("La ficha está archivada. Desarchívala antes de modificarla.")


def _motivo(motivo: str | None) -> str:
    limpio = (motivo or "").strip()
    if len(limpio) < MOTIVO_MINIMO:
        raise ValueError(f"Escribe un motivo de al menos {MOTIVO_MINIMO} caracteres.")
    return limpio[:255]


def _evento(session: Session, cliente: Cliente, tipo: str, detalle: dict, usuario: Usuario) -> None:
    identidad.registrar_evento(
        session, cliente, tipo, detalle=detalle, usuario_id=int(usuario.id), origen=ORIGEN_ADMIN
    )


# -- edición de identidad -------------------------------------------------------


def editar_identidad(
    session: Session,
    *,
    cliente_id: int,
    usuario_id: int,
    nombre: str,
    telefono: str | None,
    notas: str | None,
) -> Cliente:
    """Cambia nombre, teléfono y notas. Nada más (C1).

    Si cambia el teléfono, el nuevo debe tener 10 dígitos y no ser de otra
    ficha (Daniel, 2026-11-10). Las fichas viejas con teléfono repetido o
    inválido se pueden seguir editando mientras no se toque el teléfono."""
    usuario = exigir_admin(session, usuario_id)
    cliente = _cliente(session, cliente_id)
    _no_archivado(cliente)

    nuevo_nombre = (nombre or "").strip()
    if not nuevo_nombre:
        raise ValueError("El nombre del cliente no puede estar vacio.")
    nuevo_telefono = (telefono or "").strip() or None
    nuevas_notas = (notas or "").strip() or None

    cambios: dict[str, list] = {}
    if nuevo_nombre != cliente.nombre:
        cambios["nombre"] = [cliente.nombre, nuevo_nombre]
    if nuevo_telefono != cliente.telefono:
        cambios["telefono"] = [cliente.telefono, nuevo_telefono]
    if nuevas_notas != cliente.notas:
        cambios["notas"] = [cliente.notas, nuevas_notas]
    if not cambios:
        return cliente

    coincidencias: list[identidad.ClienteEncontrado] = []
    if "telefono" in cambios:
        if normalizar_telefono(nuevo_telefono) is None:
            raise identidad.TelefonoInvalidoError("El teléfono debe tener 10 dígitos válidos.")
        coincidencias = identidad.coincidencias_por_telefono(session, nuevo_telefono, excluir_id=int(cliente.id))
        if coincidencias:
            raise identidad.CoincidenciasPorConfirmarError(coincidencias)

    cliente.nombre = nuevo_nombre
    cliente.telefono = nuevo_telefono
    cliente.telefono_normalizado = normalizar_telefono(nuevo_telefono)
    cliente.notas = nuevas_notas
    session.add(cliente)

    detalle: dict = {"cambios": cambios}
    if "telefono" in cambios:
        normalizado = cliente.telefono_normalizado
        detalle["telefono"] = "valido" if normalizado else ("vacio" if not solo_digitos(nuevo_telefono) else "invalido")
        detalle["coincidencias"] = [c.id for c in coincidencias]
    _evento(session, cliente, EVENTO_EDICION, detalle, usuario)
    session.flush()
    return cliente


def cambiar_tipo(session: Session, *, cliente_id: int, usuario_id: int, clave: str) -> Cliente:
    """Cambia el tipo del catálogo. No toca nivel, descuento ni el enum viejo."""
    usuario = exigir_admin(session, usuario_id)
    cliente = _cliente(session, cliente_id)
    _no_archivado(cliente)
    tipo = identidad.tipo_por_clave(session, clave)
    if tipo is None or not tipo.activo:
        raise ValueError(f"El tipo {clave} no existe o no está activo.")
    if cliente.tipo_cliente_id == tipo.id:
        return cliente
    anterior = session.get(ClienteTipo, cliente.tipo_cliente_id) if cliente.tipo_cliente_id is not None else None
    cliente.tipo_cliente_id = int(tipo.id)
    session.add(cliente)
    _evento(
        session,
        cliente,
        EVENTO_CAMBIO_TIPO,
        {"antes": anterior.clave if anterior is not None else None, "despues": tipo.clave},
        usuario,
    )
    session.flush()
    return cliente


# -- estado y archivado -----------------------------------------------------------


def tiene_monedero(session: Session, cliente_id: int) -> bool:
    """Solo lectura: ¿existe un monedero de esta ficha? El Monedero no se toca."""
    return session.scalar(select(Monedero.id).where(Monedero.cliente_id == int(cliente_id)).limit(1)) is not None


def cambiar_estado(session: Session, *, cliente_id: int, usuario_id: int, activo: bool, motivo: str) -> Cliente:
    usuario = exigir_admin(session, usuario_id)
    cliente = _cliente(session, cliente_id)
    _no_archivado(cliente)
    texto = _motivo(motivo)
    if bool(cliente.activo) == bool(activo):
        return cliente
    cliente.activo = bool(activo)
    session.add(cliente)
    _evento(
        session,
        cliente,
        EVENTO_REACTIVACION if activo else EVENTO_DESACTIVACION,
        {"motivo": texto, "tiene_monedero": tiene_monedero(session, int(cliente.id))},
        usuario,
    )
    session.flush()
    return cliente


def archivar(session: Session, *, cliente_id: int, usuario_id: int, motivo: str) -> Cliente:
    """Saca la ficha de todo flujo sin borrar nada (C12)."""
    usuario = exigir_admin(session, usuario_id)
    cliente = _cliente(session, cliente_id)
    texto = _motivo(motivo)
    if cliente.archivado_en is not None:
        return cliente
    activo_antes = bool(cliente.activo)
    cliente.archivado_en = datetime.now(timezone.utc)
    cliente.archivado_motivo = texto
    cliente.activo = False
    session.add(cliente)
    _evento(
        session,
        cliente,
        EVENTO_ARCHIVADO,
        {"motivo": texto, "activo_antes": activo_antes, "tiene_monedero": tiene_monedero(session, int(cliente.id))},
        usuario,
    )
    session.flush()
    return cliente


def desarchivar(session: Session, *, cliente_id: int, usuario_id: int, motivo: str) -> Cliente:
    """Deshace el archivado y devuelve el estado activo que tenía antes."""
    usuario = exigir_admin(session, usuario_id)
    cliente = _cliente(session, cliente_id)
    texto = _motivo(motivo)
    if cliente.archivado_en is None:
        return cliente
    ultimo = session.scalar(
        select(ClienteEvento)
        .where(
            ClienteEvento.cliente_id == int(cliente.id),
            ClienteEvento.tipo == EVENTO_ARCHIVADO,
        )
        .order_by(ClienteEvento.id.desc())
        .limit(1)
    )
    activo_antes = True
    if ultimo is not None and isinstance(ultimo.detalle, dict) and "activo_antes" in ultimo.detalle:
        activo_antes = bool(ultimo.detalle["activo_antes"])
    archivado_desde = cliente.archivado_en.isoformat()
    cliente.archivado_en = None
    cliente.archivado_motivo = None
    cliente.activo = activo_antes
    session.add(cliente)
    _evento(
        session,
        cliente,
        EVENTO_DESARCHIVADO,
        {"motivo": texto, "archivado_desde": archivado_desde, "activo": activo_antes},
        usuario,
    )
    session.flush()
    return cliente


# -- lista del ADMIN ------------------------------------------------------------------


@dataclass(frozen=True)
class FilaClienteAdmin:
    id: int
    codigo: str
    nombre: str
    telefono: str  # completo: solo lo ve el ADMIN
    tipo: str  # nombre del catálogo, o "" si la ficha no tiene
    origen: str
    alta: datetime | None
    activo: bool
    archivado: bool
    notas: str
    programa: str = ""  # E4-D: «Maximoda Club», «… (propuesta a Profesional)» o ""


def _programas_de(session: Session, ids: list[int]) -> dict[int, str]:
    """E4-D: texto de la columna «Programa» para estas fichas, en una consulta."""
    from pos_uniformes.database.models import Membresia, Programa

    if not ids:
        return {}
    activas: dict[int, str] = {}
    pendientes: dict[int, str] = {}
    filas = session.execute(
        select(Membresia.cliente_id, Membresia.estado, Programa.nombre)
        .join(Programa, Programa.id == Membresia.programa_id)
        .where(Membresia.cliente_id.in_(ids), Membresia.estado.in_(("activa", "pendiente")))
    ).all()
    for cliente_id, estado, nombre in filas:
        (activas if estado == "activa" else pendientes)[int(cliente_id)] = str(nombre)
    textos = {}
    for cliente_id in set(activas) | set(pendientes):
        partes = [activas[cliente_id]] if cliente_id in activas else []
        if cliente_id in pendientes:
            partes.append(f"(propuesta a {pendientes[cliente_id].replace('Maximoda ', '')})")
        textos[cliente_id] = " ".join(partes)
    return textos


def _filtro_programa(stmt, programa: str):
    from pos_uniformes.database.models import Membresia, Programa

    clave = programa.strip().upper()
    activa = select(Membresia.id).where(Membresia.cliente_id == Cliente.id, Membresia.estado == "activa")
    if clave == PROGRAMA_NINGUNO:
        return stmt.where(~activa.exists())
    if clave == PROGRAMA_PENDIENTE:
        pendiente = select(Membresia.id).where(Membresia.cliente_id == Cliente.id, Membresia.estado == "pendiente")
        return stmt.where(pendiente.exists())
    en_programa = activa.join(Programa, Programa.id == Membresia.programa_id).where(Programa.clave == clave)
    return stmt.where(en_programa.exists())


def listar_para_admin(
    session: Session,
    usuario_id: int,
    *,
    texto: str = "",
    estado: str = ESTADO_ACTIVOS,
    tipo_clave: str | None = None,
    origen: str | None = None,
    limite: int = LIMITE_LISTA,
    programa: str | None = None,
) -> list[FilaClienteAdmin]:
    exigir_admin(session, usuario_id)
    stmt = select(Cliente, ClienteTipo).outerjoin(ClienteTipo, ClienteTipo.id == Cliente.tipo_cliente_id)

    if estado == ESTADO_ACTIVOS:
        stmt = stmt.where(Cliente.activo.is_(True), Cliente.archivado_en.is_(None))
    elif estado == ESTADO_INACTIVOS:
        stmt = stmt.where(Cliente.activo.is_(False), Cliente.archivado_en.is_(None))
    elif estado == ESTADO_ARCHIVADOS:
        stmt = stmt.where(Cliente.archivado_en.is_not(None))
    elif estado != ESTADO_TODOS:
        raise ValueError(f"Estado desconocido: {estado}")

    if tipo_clave:
        stmt = stmt.where(ClienteTipo.clave == tipo_clave.strip().upper())
    if origen == ORIGEN_ANTERIOR:
        stmt = stmt.where(Cliente.origen_alta.is_(None))
    elif origen:
        stmt = stmt.where(Cliente.origen_alta == origen)
    if programa:
        stmt = _filtro_programa(stmt, programa)

    buscado = (texto or "").strip()
    if buscado:
        patron = f"%{buscado}%"
        condiciones = [Cliente.codigo_cliente.ilike(patron), Cliente.nombre.ilike(patron)]
        digitos = solo_digitos(buscado)
        if len(digitos) >= 4:
            condiciones.append(Cliente.telefono_normalizado.like(f"%{digitos}"))
            condiciones.append(Cliente.telefono.like(f"%{digitos}%"))
        stmt = stmt.where(or_(*condiciones))

    stmt = stmt.order_by(Cliente.nombre, Cliente.id).limit(max(1, min(int(limite), LIMITE_LISTA)))
    filas = []
    resultado = session.execute(stmt).all()
    programas = _programas_de(session, [int(c.id) for c, _t in resultado])
    for cliente, tipo in resultado:
        filas.append(
            FilaClienteAdmin(
                id=int(cliente.id),
                codigo=str(cliente.codigo_cliente),
                nombre=str(cliente.nombre),
                telefono=cliente.telefono or "",
                tipo=str(tipo.nombre) if tipo is not None else "",
                origen=cliente.origen_alta or "",
                alta=cliente.cliente_desde,
                activo=bool(cliente.activo),
                archivado=cliente.archivado_en is not None,
                notas=cliente.notas or "",
                programa=programas.get(int(cliente.id), ""),
            )
        )
    return filas
