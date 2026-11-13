"""Identidad de clientes (E1-B): búsqueda, alta sin nivel y duplicados.

Reglas (K1, R1):

- Toda alta nace SIN nivel (`nivel_lealtad = NULL`), con
  `descuento_preferente = 0`, sin `nivel_asignado_*`, con `origen_alta` y con
  un evento en `cliente_evento`. Aquí nunca se llama a `LoyaltyService`.
- Antes de crear se buscan coincidencias por `telefono_normalizado`. Con
  `revisar_duplicados=True` (Venta Rápida) una coincidencia sin confirmar
  detiene el alta; nunca se crea en silencio. En las altas que conservan su
  diálogo de hoy (Presupuesto del kiosko y Configuración) las coincidencias
  no detienen el alta, pero quedan registradas en el evento.
- Un teléfono compartido es válido: se crea con confirmación explícita y el
  evento `alta_telefono_compartido` guarda los ids de las coincidencias.
  Ninguna pantalla lo ofrece ya: en el kiosko y en el POS el teléfono es
  obligatorio y único (Daniel, 2026-11-10). Las altas de la tienda pasan
  `exigir_telefono_valido=True, revisar_duplicados=True` y nunca confirman.
- A la empleada solo le viaja el teléfono enmascarado (P2).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Cliente, ClienteEvento, ClienteTipo, TipoCliente
from pos_uniformes.services.clientes.telefono import (
    enmascarar_telefono,
    normalizar_telefono,
    solo_digitos,
)

_logger = logging.getLogger(__name__)

# E1-C0: tipo del catálogo que corresponde al enum viejo (P23: PROFESOR = DOCENTE).
TIPO_GENERAL = "GENERAL"
_CLAVE_DESDE_ENUM = {
    TipoCliente.GENERAL: "GENERAL",
    TipoCliente.PROFESOR: "DOCENTE",
    TipoCliente.MAYORISTA: "MAYORISTA",
}


def tipo_por_clave(session: Session, clave: str) -> ClienteTipo | None:
    return session.scalar(select(ClienteTipo).where(ClienteTipo.clave == (clave or "").strip().upper()))


def tipos_activos(session: Session) -> list[ClienteTipo]:
    return list(
        session.scalars(select(ClienteTipo).where(ClienteTipo.activo.is_(True)).order_by(ClienteTipo.orden, ClienteTipo.id))
    )


def clave_desde_enum(tipo_cliente: TipoCliente | None) -> str:
    """La clave del catálogo que corresponde al enum viejo (PROFESOR = DOCENTE)."""
    return _CLAVE_DESDE_ENUM.get(tipo_cliente, TIPO_GENERAL)


def enum_desde_clave(clave: str | None) -> TipoCliente:
    """El enum viejo más cercano a una clave del catálogo, solo para dejar
    `Cliente.tipo_cliente` coherente (2026-11-12: nadie vivo lo lee ya).
    DOCENTE → PROFESOR; MAYORISTA e INSTITUCION → MAYORISTA; lo demás GENERAL."""
    clave = (clave or "").strip().upper()
    if clave == "DOCENTE":
        return TipoCliente.PROFESOR
    if clave in {"MAYORISTA", "INSTITUCION"}:
        return TipoCliente.MAYORISTA
    return TipoCliente.GENERAL


EVENTO_CAMBIO_TIPO = "cambio_tipo"


def aplicar_tipo(
    session: Session,
    cliente: Cliente,
    clave: str,
    *,
    usuario_id: int | None = None,
    respetar_institucion: bool = False,
    origen: str | None = None,
) -> bool:
    """Pone a `cliente` el tipo del catálogo `clave` (`tipo_cliente_id`, el
    que manda) y deja el evento `cambio_tipo`, como `admin_service.cambiar_tipo`.

    El tipo no da nivel, descuento ni programa: no toca nada de eso (los
    beneficios vienen de las membresías). Con `respetar_institucion`, pedir
    MAYORISTA a una Institución la deja Institución (la misma regla que al
    aprobar Maximoda Mayorista). Devuelve si cambió. 2026-11-12."""
    clave = (clave or "").strip().upper()
    tipo = tipo_por_clave(session, clave)
    if tipo is None or not tipo.activo:
        raise ValueError(f"El tipo de cliente {clave} no existe o no está activo.")
    if cliente.tipo_cliente_id == tipo.id:
        return False
    anterior = session.get(ClienteTipo, cliente.tipo_cliente_id) if cliente.tipo_cliente_id is not None else None
    if respetar_institucion and clave == "MAYORISTA" and anterior is not None and anterior.clave == "INSTITUCION":
        return False
    cliente.tipo_cliente_id = int(tipo.id)
    session.add(cliente)
    registrar_evento(
        session,
        cliente,
        EVENTO_CAMBIO_TIPO,
        detalle={"antes": anterior.clave if anterior is not None else None, "despues": str(tipo.clave)},
        usuario_id=usuario_id,
        origen=origen,
    )
    return True

ORIGEN_VENTA_RAPIDA = "venta_rapida"
ORIGEN_PRESUPUESTO_KIOSKO = "presupuesto_kiosko"
ORIGEN_POS_ADMIN = "pos_admin"

EVENTO_ALTA = "alta"
EVENTO_ALTA_TELEFONO_COMPARTIDO = "alta_telefono_compartido"

LIMITE_BUSQUEDA = 30
_INTENTOS_CODIGO = 5
_MIN_DIGITOS_SUFIJO = 4


class TelefonoInvalidoError(ValueError):
    """El teléfono no tiene 10 dígitos válidos."""


@dataclass(frozen=True)
class ClienteEncontrado:
    """Lo que ve la empleada: sin teléfono completo ni datos comerciales."""

    id: int
    codigo: str
    nombre: str
    telefono_enmascarado: str


class CoincidenciasPorConfirmarError(ValueError):
    """Ya hay fichas con ese teléfono: hay que elegir una o confirmar otra persona."""

    def __init__(self, coincidencias: list[ClienteEncontrado]) -> None:
        super().__init__(f"Ya hay {len(coincidencias)} cliente(s) con ese teléfono.")
        self.coincidencias = coincidencias


def mensaje_telefono_ya_registrado(coincidencias: list[ClienteEncontrado]) -> str:
    """El error que ve la empleada cuando el teléfono ya es de otro cliente."""
    lineas = "\n".join(
        f"• {c.nombre} · {c.codigo}" + (f" · Tel {c.telefono_enmascarado}" if c.telefono_enmascarado else "")
        for c in coincidencias
    )
    return (
        f"Ya hay un cliente con ese teléfono:\n{lineas}\n\n"
        "No se guardó. Si es la misma persona, usa su ficha."
    )


def _a_encontrado(cliente: Cliente) -> ClienteEncontrado:
    return ClienteEncontrado(
        id=int(cliente.id),
        codigo=str(cliente.codigo_cliente),
        nombre=str(cliente.nombre),
        telefono_enmascarado=enmascarar_telefono(cliente.telefono),
    )


def buscar_clientes(session: Session, texto: str, limite: int = LIMITE_BUSQUEDA) -> list[ClienteEncontrado]:
    """Clientes ACTIVOS por código, nombre o los últimos dígitos del teléfono."""
    texto = (texto or "").strip()
    if not texto:
        return []
    patron = f"%{texto}%"
    condiciones = [Cliente.codigo_cliente.ilike(patron), Cliente.nombre.ilike(patron)]
    digitos = solo_digitos(texto)
    if len(digitos) >= _MIN_DIGITOS_SUFIJO and len(digitos) == len(re.sub(r"[\s\-().+]", "", texto)):
        condiciones.append(Cliente.telefono_normalizado.like(f"%{digitos}"))
    stmt = (
        select(Cliente)
        .where(Cliente.activo.is_(True), Cliente.archivado_en.is_(None), or_(*condiciones))
        .order_by(Cliente.nombre)
        .limit(max(1, min(int(limite), LIMITE_BUSQUEDA)))
    )
    return [_a_encontrado(c) for c in session.scalars(stmt).all()]


def coincidencias_por_telefono(
    session: Session, telefono: str | None, *, excluir_id: int | None = None
) -> list[ClienteEncontrado]:
    """Fichas ACTIVAS y no archivadas con el mismo teléfono normalizado (vacío si es inválido)."""
    normalizado = normalizar_telefono(telefono)
    if normalizado is None:
        return []
    stmt = (
        select(Cliente)
        .where(
            Cliente.activo.is_(True),
            Cliente.archivado_en.is_(None),
            Cliente.telefono_normalizado == normalizado,
        )
        .order_by(Cliente.id)
    )
    if excluir_id is not None:
        stmt = stmt.where(Cliente.id != int(excluir_id))
    return [_a_encontrado(c) for c in session.scalars(stmt).all()]


def _siguiente_codigo(session: Session, intento: int) -> str:
    siguiente = (session.scalar(select(func.coalesce(func.max(Cliente.id), 0))) or 0) + 1 + intento
    return f"CLI-{int(siguiente):06d}"


def registrar_evento(
    session: Session,
    cliente: Cliente,
    tipo: str,
    *,
    detalle: dict | None = None,
    usuario_id: int | None = None,
    employee_code: str | None = None,
    origen: str | None = None,
) -> ClienteEvento:
    evento = ClienteEvento(
        cliente_id=int(cliente.id),
        tipo=tipo,
        detalle=detalle or {},
        usuario_id=usuario_id,
        employee_code=employee_code,
        origen=origen,
    )
    session.add(evento)
    return evento


def dar_de_alta(
    session: Session,
    *,
    nombre: str,
    telefono: str | None,
    origen: str,
    tipo_cliente: TipoCliente = TipoCliente.GENERAL,
    notas: str | None = None,
    usuario_id: int | None = None,
    employee_code: str | None = None,
    exigir_telefono_valido: bool = False,
    revisar_duplicados: bool = False,
    confirmar_telefono_compartido: bool = False,
    tipo_clave: str | None = None,
) -> Cliente:
    """Crea una ficha SIN nivel ni descuento (K1) y deja su evento de alta.

    E1-C0: la ficha nace con un tipo del catálogo. Por omisión, el que
    corresponde al enum (GENERAL, salvo que el llamador diga otro); el tipo
    no da nivel ni beneficio."""
    nombre_limpio = (nombre or "").strip()
    if not nombre_limpio:
        raise ValueError("El nombre del cliente no puede estar vacio.")
    clave = (tipo_clave or _CLAVE_DESDE_ENUM.get(tipo_cliente, TIPO_GENERAL)).strip().upper()
    tipo = tipo_por_clave(session, clave)
    if tipo is None or not tipo.activo:
        raise ValueError(f"El tipo de cliente {clave} no existe o no está activo.")
    telefono_limpio = (telefono or "").strip() or None
    normalizado = normalizar_telefono(telefono_limpio)
    if exigir_telefono_valido and normalizado is None:
        raise TelefonoInvalidoError("El teléfono debe tener 10 dígitos válidos.")

    coincidencias = coincidencias_por_telefono(session, telefono_limpio)
    if coincidencias and revisar_duplicados and not confirmar_telefono_compartido:
        raise CoincidenciasPorConfirmarError(coincidencias)

    cliente: Cliente | None = None
    for intento in range(_INTENTOS_CODIGO):
        candidato = Cliente(
            codigo_cliente=_siguiente_codigo(session, intento),
            nombre=nombre_limpio,
            tipo_cliente=tipo_cliente,
            descuento_preferente=Decimal("0.00"),
            nivel_lealtad=None,
            tipo_cliente_id=int(tipo.id),
            telefono=telefono_limpio,
            telefono_normalizado=normalizado,
            notas=(notas or "").strip() or None,
            origen_alta=origen,
            activo=True,
        )
        punto = session.begin_nested()
        try:
            session.add(candidato)
            session.flush()
        except IntegrityError:
            punto.rollback()
            _logger.info("Código de cliente %s ocupado; reintento %s", candidato.codigo_cliente, intento + 1)
            continue
        punto.commit()
        cliente = candidato
        break
    if cliente is None:
        raise RuntimeError("No se pudo generar un código de cliente libre; intenta de nuevo.")

    compartido = bool(coincidencias) and revisar_duplicados and confirmar_telefono_compartido
    registrar_evento(
        session,
        cliente,
        EVENTO_ALTA_TELEFONO_COMPARTIDO if compartido else EVENTO_ALTA,
        detalle={
            "origen": origen,
            "tipo": str(tipo.clave),
            "telefono": "valido" if normalizado else ("vacio" if not solo_digitos(telefono_limpio) else "invalido"),
            "coincidencias": [c.id for c in coincidencias],
        },
        usuario_id=usuario_id,
        employee_code=employee_code,
        origen=origen,
    )
    session.flush()
    return cliente
