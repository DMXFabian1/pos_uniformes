"""Cliente minimo para la WhatsApp Cloud API (oficial de Meta).

Encapsula el envio de mensajes de texto y mensajes interactivos
(botones y listas) usados por el chatbot de presupuestos.

Configuracion por variables de entorno (en pos_uniformes.env):

    WHATSAPP_TOKEN              Token de acceso permanente del System User.
    WHATSAPP_PHONE_NUMBER_ID    ID del numero de telefono (no el numero).
    WHATSAPP_VERIFY_TOKEN       Cadena secreta para verificar el webhook.
    WHATSAPP_APP_SECRET         (Opcional) App secret para validar la firma.
    WHATSAPP_API_VERSION        (Opcional) Version del Graph API. Default v21.0.

El cliente NO maneja logica de negocio: solo envia mensajes.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Limites duros que impone WhatsApp en mensajes interactivos.
MAX_BUTTON_TITLE = 20
MAX_ROW_TITLE = 24
MAX_ROW_DESCRIPTION = 72
MAX_SECTION_TITLE = 24
MAX_BODY_TEXT = 1024
MAX_LIST_ROWS = 10  # total de filas permitidas en una lista
MAX_REPLY_BUTTONS = 3


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"  # …


@dataclass(frozen=True)
class WhatsAppConfig:
    token: str
    phone_number_id: str
    verify_token: str
    app_secret: str | None
    api_version: str

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.phone_number_id)

    @property
    def messages_url(self) -> str:
        return (
            f"https://graph.facebook.com/{self.api_version}"
            f"/{self.phone_number_id}/messages"
        )

    @classmethod
    def from_env(cls) -> "WhatsAppConfig":
        return cls(
            token=os.getenv("WHATSAPP_TOKEN", "").strip(),
            phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip(),
            verify_token=os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip(),
            app_secret=(os.getenv("WHATSAPP_APP_SECRET", "").strip() or None),
            api_version=os.getenv("WHATSAPP_API_VERSION", "v21.0").strip() or "v21.0",
        )


class WhatsAppClient:
    """Envia mensajes a traves de la WhatsApp Cloud API."""

    def __init__(self, config: WhatsAppConfig | None = None) -> None:
        self.config = config or WhatsAppConfig.from_env()

    # ── Verificacion del webhook ───────────────────────────────────────────

    def verify_webhook(self, mode: str | None, token: str | None) -> bool:
        """Valida el handshake GET que envia Meta al registrar el webhook."""
        return mode == "subscribe" and bool(token) and token == self.config.verify_token

    def is_valid_signature(self, payload: bytes, signature_header: str | None) -> bool:
        """
        Valida la firma X-Hub-Signature-256 del cuerpo recibido.
        Si no hay app_secret configurado, no se valida (devuelve True).
        """
        if not self.config.app_secret:
            return True
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        expected = hmac.new(
            self.config.app_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        received = signature_header.split("=", 1)[1]
        return hmac.compare_digest(expected, received)

    # ── Envio de mensajes ──────────────────────────────────────────────────

    def _post(self, body: dict) -> bool:
        if not self.config.is_configured:
            logger.warning("WhatsApp no configurado: mensaje no enviado. body=%s", body)
            return False
        headers = {
            "Authorization": f"Bearer {self.config.token}",
            "Content-Type": "application/json",
        }
        try:
            resp = httpx.post(self.config.messages_url, json=body, headers=headers, timeout=15.0)
            if resp.status_code >= 400:
                logger.error("WhatsApp API %s: %s", resp.status_code, resp.text)
                return False
            return True
        except httpx.HTTPError as exc:
            logger.error("Error enviando mensaje a WhatsApp: %s", exc)
            return False

    def send_text(self, to: str, body: str) -> bool:
        return self._post(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"preview_url": False, "body": _truncate(body, MAX_BODY_TEXT)},
            }
        )

    def send_buttons(
        self,
        to: str,
        body: str,
        buttons: list[tuple[str, str]],
        header: str | None = None,
    ) -> bool:
        """buttons: lista de (id, titulo). Maximo 3."""
        reply_buttons = [
            {
                "type": "reply",
                "reply": {"id": btn_id, "title": _truncate(title, MAX_BUTTON_TITLE)},
            }
            for btn_id, title in buttons[:MAX_REPLY_BUTTONS]
        ]
        interactive: dict = {
            "type": "button",
            "body": {"text": _truncate(body, MAX_BODY_TEXT)},
            "action": {"buttons": reply_buttons},
        }
        if header:
            interactive["header"] = {"type": "text", "text": _truncate(header, 60)}
        return self._post(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "interactive",
                "interactive": interactive,
            }
        )

    def send_list(
        self,
        to: str,
        body: str,
        button_label: str,
        rows: list[tuple[str, str, str | None]],
        header: str | None = None,
        section_title: str = "Opciones",
    ) -> bool:
        """
        Mensaje de lista desplegable.
        rows: lista de (id, titulo, descripcion|None). Maximo 10 filas.
        """
        list_rows = []
        for row_id, title, description in rows[:MAX_LIST_ROWS]:
            row: dict = {"id": row_id, "title": _truncate(title, MAX_ROW_TITLE)}
            if description:
                row["description"] = _truncate(description, MAX_ROW_DESCRIPTION)
            list_rows.append(row)

        interactive: dict = {
            "type": "list",
            "body": {"text": _truncate(body, MAX_BODY_TEXT)},
            "action": {
                "button": _truncate(button_label, MAX_BUTTON_TITLE),
                "sections": [
                    {
                        "title": _truncate(section_title, MAX_SECTION_TITLE),
                        "rows": list_rows,
                    }
                ],
            },
        }
        if header:
            interactive["header"] = {"type": "text", "text": _truncate(header, 60)}
        return self._post(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "interactive",
                "interactive": interactive,
            }
        )
