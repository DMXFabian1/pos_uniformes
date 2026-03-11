"""Autenticacion local y hashing de contrasenas."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Usuario

PBKDF2_PREFIX: Final[str] = "pbkdf2_sha256"
PBKDF2_ITERATIONS: Final[int] = 120_000
SALT_BYTES: Final[int] = 16


class AuthService:
    """Gestiona hashing, verificacion y autenticacion local."""

    @staticmethod
    def hash_password(password: str) -> str:
        if not password:
            raise ValueError("La contrasena no puede estar vacia.")

        salt = os.urandom(SALT_BYTES).hex()
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            PBKDF2_ITERATIONS,
        ).hex()
        return f"{PBKDF2_PREFIX}${PBKDF2_ITERATIONS}${salt}${digest}"

    @staticmethod
    def _verify_pbkdf2(password: str, stored_hash: str) -> bool:
        try:
            prefix, iteration_text, salt, digest = stored_hash.split("$", 3)
        except ValueError:
            return False

        if prefix != PBKDF2_PREFIX:
            return False

        iterations = int(iteration_text)
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            iterations,
        ).hex()
        return hmac.compare_digest(candidate, digest)

    @classmethod
    def verify_password(cls, password: str, stored_hash: str) -> bool:
        if stored_hash.startswith(f"{PBKDF2_PREFIX}$"):
            return cls._verify_pbkdf2(password, stored_hash)

        # Compatibilidad temporal con seeds anteriores en texto plano.
        return hmac.compare_digest(password, stored_hash)

    @classmethod
    def authenticate(cls, session: Session, username: str, password: str) -> Usuario | None:
        user = session.scalar(
            select(Usuario).where(
                Usuario.username == username,
                Usuario.activo.is_(True),
            )
        )
        if user is None:
            return None

        if not cls.verify_password(password, user.password_hash):
            return None

        if not user.password_hash.startswith(f"{PBKDF2_PREFIX}$"):
            user.password_hash = cls.hash_password(password)
            session.add(user)

        return user
