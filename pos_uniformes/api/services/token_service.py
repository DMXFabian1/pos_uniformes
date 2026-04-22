"""Generacion y validacion de tokens JWT para la API movil."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from pos_uniformes.utils.config import settings

ALGORITHM = "HS256"


class TokenPayload:
    def __init__(self, employee_id: int, device_id: str, employee_name: str) -> None:
        self.employee_id = employee_id
        self.device_id = device_id
        self.employee_name = employee_name


class TokenService:
    """Manejo de JWT para sesiones de empleada en dispositivos moviles."""

    @classmethod
    def _secret(cls) -> str:
        return settings.api_secret_key

    @classmethod
    def create_token(cls, employee_id: int, employee_name: str, device_id: str | None = None) -> tuple[str, str]:
        """
        Genera un JWT para la sesion de una empleada.
        Devuelve (token, device_id). Si device_id no se provee, genera uno nuevo.
        """
        resolved_device_id = device_id or str(uuid.uuid4())
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.api_token_expire_hours)
        payload: dict[str, Any] = {
            "sub": str(employee_id),
            "name": employee_name,
            "device_id": resolved_device_id,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(payload, cls._secret(), algorithm=ALGORITHM)
        return token, resolved_device_id

    @classmethod
    def decode_token(cls, token: str) -> TokenPayload:
        """
        Decodifica y valida un JWT. Lanza jwt.InvalidTokenError si no es valido.
        """
        payload = jwt.decode(token, cls._secret(), algorithms=[ALGORITHM])
        return TokenPayload(
            employee_id=int(payload["sub"]),
            device_id=str(payload["device_id"]),
            employee_name=str(payload["name"]),
        )
