"""Credencial de bienvenida por WhatsApp al dar de alta un cliente en el kiosko.

La empleada registra al cliente y el kiosko deja todo listo: la credencial
generada, el chat del cliente abierto en WhatsApp Web con el mensaje escrito
y la imagen copiada. Ella solo pega (Ctrl+V) y envía (Daniel, 2026-11-10:
«sin tantos clics»; «que usemos whatsapp web, no la app de escritorio»).

No manda nada solo: no hay API de WhatsApp Business. Tampoco promete
descuentos ni porcentajes, porque eso lo decide el dueño (E4).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

NEGOCIO_POR_OMISION = "Maximoda"


class SinTelefonoParaWhatsappError(ValueError):
    """La ficha no tiene un teléfono que sirva para WhatsApp."""


def normalizar_telefono(telefono: str | None) -> str:
    """El número como lo pide WhatsApp: con 52 y sin el 1 viejo de celular.

    Si no son 10 dígitos de México (ni 52 + 10), regresa "".
    """
    digitos = "".join(ch for ch in (telefono or "") if ch.isdigit())
    if len(digitos) == 13 and digitos.startswith("521"):
        digitos = "52" + digitos[3:]
    if len(digitos) == 10:
        return "52" + digitos
    if len(digitos) == 12 and digitos.startswith("52"):
        return digitos
    return ""


def mensaje_bienvenida(
    nombre: str, codigo: str, negocio: str = NEGOCIO_POR_OMISION, programa: str | None = None
) -> str:
    pila = (nombre or "").strip().split(" ")[0] or "hola"
    negocio = (negocio or "").strip() or NEGOCIO_POR_OMISION
    miembro = f" Ya eres miembro de {programa}." if programa else ""
    return (
        f"¡Hola {pila}! Gracias por registrarte en {negocio}.{miembro}\n\n"
        f"Te compartimos tu credencial de cliente. Tu código es {codigo}. "
        "Muéstrala en tu próxima compra."
    )


def mensaje_reenvio(
    nombre: str, codigo: str, negocio: str = NEGOCIO_POR_OMISION, programa: str | None = None
) -> str:
    """Para el cliente que perdió su credencial (Daniel, 2026-11-10)."""
    pila = (nombre or "").strip().split(" ")[0] or "hola"
    negocio = (negocio or "").strip() or NEGOCIO_POR_OMISION
    miembro = f" Eres miembro de {programa}." if programa else ""
    return (
        f"¡Hola {pila}! Te reenviamos tu credencial de cliente de {negocio}.{miembro}\n\n"
        f"Tu código es {codigo}. Muéstrala en tu próxima compra."
    )


def enlace_web(telefono_wa: str, mensaje: str) -> str:
    """WhatsApp Web con el chat del cliente y el texto ya escrito."""
    return f"https://web.whatsapp.com/send?phone={telefono_wa}&text={quote(mensaje)}"


@dataclass(frozen=True)
class EnvioCredencial:
    cliente_id: int
    nombre: str
    codigo: str
    telefono_wa: str
    mensaje: str
    imagen: Path
    url_web: str
    #: El programa en que ya quedó (Maximoda Club al registrarse), o None.
    programa: str | None = None


def preparar(
    session, cliente_id: int, *, render=None, negocio: str | None = None, reenvio: bool = False
) -> EnvioCredencial:
    """Genera la credencial del cliente y arma el mensaje y los enlaces.

    `render(cliente) -> Path` es inyectable para las pruebas. Por omisión es
    `CustomerCardService.render_for_client`, que no escribe en la ficha.
    """
    from pos_uniformes.database.models import Cliente

    cliente = session.get(Cliente, int(cliente_id))
    if cliente is None:
        raise ValueError("No se encontró al cliente.")
    telefono_wa = normalizar_telefono(cliente.telefono)
    if not telefono_wa:
        raise SinTelefonoParaWhatsappError("El cliente no tiene un teléfono de 10 dígitos para WhatsApp.")
    if render is None:
        from pos_uniformes.services.customer_card_service import CustomerCardService

        render = CustomerCardService.render_for_client
    imagen = Path(render(cliente))
    if negocio is None:
        negocio = _nombre_del_negocio(session)
    programa = _programa_activo(session, int(cliente.id))
    redactar = mensaje_reenvio if reenvio else mensaje_bienvenida
    mensaje = redactar(cliente.nombre, cliente.codigo_cliente, negocio, programa)
    return EnvioCredencial(
        cliente_id=int(cliente.id),
        nombre=str(cliente.nombre),
        codigo=str(cliente.codigo_cliente),
        telefono_wa=telefono_wa,
        mensaje=mensaje,
        imagen=imagen,
        url_web=enlace_web(telefono_wa, mensaje),
        programa=programa,
    )


def _programa_activo(session, cliente_id: int) -> str | None:
    try:
        from pos_uniformes.services.fidelizacion import membresia_service

        estado = membresia_service.estado_de_cliente(session, cliente_id)
        return str(estado.activa.programa.nombre) if estado.activa is not None else None
    except Exception:  # noqa: BLE001 - es adorno del mensaje; sin él va sin programa
        return None


def _nombre_del_negocio(session) -> str:
    try:
        from pos_uniformes.services.business_settings_service import BusinessSettingsService

        config = BusinessSettingsService.get_or_create(session)
        return str(config.nombre_negocio or NEGOCIO_POR_OMISION)
    except Exception:  # noqa: BLE001 - el nombre es adorno; sin él va el de siempre
        return NEGOCIO_POR_OMISION
