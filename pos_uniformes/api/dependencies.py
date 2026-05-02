"""Dependencias compartidas de FastAPI: sesion DB y autenticacion."""

from __future__ import annotations

from collections.abc import Generator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Empleada
from pos_uniformes.api.services.token_service import TokenPayload, TokenService
from sqlalchemy import select

bearer_scheme = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    """Provee una sesion de base de datos por request."""
    db = get_session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_current_employee(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> tuple[Empleada, TokenPayload]:
    """
    Valida el Bearer token y devuelve (empleada, payload).
    Lanza 401 si el token es invalido o la empleada esta inactiva.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "token_invalido", "message": "Token invalido o expirado."}},
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = TokenService.decode_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise credentials_exception

    empleada = db.scalar(
        select(Empleada).where(Empleada.id == payload.employee_id, Empleada.activo.is_(True))
    )
    if empleada is None:
        raise credentials_exception

    return empleada, payload
