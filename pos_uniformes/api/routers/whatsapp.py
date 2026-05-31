"""Webhook del chatbot de presupuestos por WhatsApp (Cloud API de Meta).

Expone dos endpoints bajo /api/v1/whatsapp/webhook:

    GET   verificacion del webhook (handshake de Meta al registrarlo).
    POST  recepcion de mensajes entrantes.

El procesamiento del mensaje se delega a un BackgroundTask para responder
200 a Meta de inmediato (Meta reintenta si la respuesta tarda demasiado).

A diferencia del resto de la API, estos endpoints NO usan el JWT de empleada:
la autenticidad se valida con el verify_token (GET) y, opcionalmente, con la
firma X-Hub-Signature-256 (POST) usando el app_secret.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response, status
from fastapi.responses import PlainTextResponse

from pos_uniformes.api.services.whatsapp_client import WhatsAppClient
from pos_uniformes.api.services.whatsapp_flow_service import WhatsAppFlowService
from pos_uniformes.database.connection import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/whatsapp", tags=["whatsapp"])


@router.get("/webhook")
def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> Response:
    """Handshake de verificacion que Meta envia al guardar el webhook."""
    client = WhatsAppClient()
    if client.verify_webhook(hub_mode, hub_verify_token) and hub_challenge is not None:
        return PlainTextResponse(content=hub_challenge, status_code=status.HTTP_200_OK)
    return PlainTextResponse(content="forbidden", status_code=status.HTTP_403_FORBIDDEN)


@router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    """Recibe mensajes de WhatsApp y los procesa en segundo plano."""
    raw_body = await request.body()
    client = WhatsAppClient()

    signature = request.headers.get("X-Hub-Signature-256")
    if not client.is_valid_signature(raw_body, signature):
        logger.warning("Firma de webhook de WhatsApp invalida; mensaje descartado.")
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=status.HTTP_200_OK)

    for message in _extract_messages(payload):
        background_tasks.add_task(_process_message, message)

    # Siempre 200 para que Meta no reintente.
    return Response(status_code=status.HTTP_200_OK)


def _extract_messages(payload: dict) -> list[dict]:
    """
    Aplana el payload de Meta a una lista de mensajes normalizados:
        {"from": wa_id, "reply_id": str|None, "text": str|None}
    Ignora notificaciones que no sean mensajes de usuario (status, etc.).
    """
    normalizados: list[dict] = []
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    normalizado = _normalize_message(msg)
                    if normalizado is not None:
                        normalizados.append(normalizado)
    except Exception:
        logger.exception("Error interpretando payload de WhatsApp")
    return normalizados


def _normalize_message(msg: dict) -> dict | None:
    wa_id = msg.get("from")
    if not wa_id:
        return None
    msg_type = msg.get("type")

    reply_id: str | None = None
    text: str | None = None

    if msg_type == "text":
        text = (msg.get("text") or {}).get("body")
    elif msg_type == "interactive":
        interactive = msg.get("interactive") or {}
        itype = interactive.get("type")
        if itype == "button_reply":
            reply_id = (interactive.get("button_reply") or {}).get("id")
            text = (interactive.get("button_reply") or {}).get("title")
        elif itype == "list_reply":
            reply_id = (interactive.get("list_reply") or {}).get("id")
            text = (interactive.get("list_reply") or {}).get("title")
    elif msg_type == "button":
        # Botones de plantillas (quick reply) llegan con otro formato.
        text = (msg.get("button") or {}).get("text")
    else:
        # Imagenes, audios, ubicaciones, etc.: respondemos con texto guia.
        text = ""

    return {"from": wa_id, "reply_id": reply_id, "text": text}


def _process_message(message: dict) -> None:
    """Procesa un mensaje en background con su propia sesion de BD."""
    db = get_session()
    try:
        service = WhatsAppFlowService(db)
        service.handle(message["from"], {"reply_id": message.get("reply_id"), "text": message.get("text")})
    except Exception:
        logger.exception("Error en el flujo de WhatsApp")
        db.rollback()
    finally:
        db.close()
