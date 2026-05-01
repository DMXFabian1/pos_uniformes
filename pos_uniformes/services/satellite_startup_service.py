"""Logica de arranque del satelite: probe de conexion y modo offline.

Mantiene la decision de arranque fuera de la UI para que sea testeable
y no mezcle logica de negocio con widgets de PyQt.
"""

from __future__ import annotations

import socket

from pos_uniformes.utils.config import settings

_DEFAULT_PROBE_TIMEOUT_SEC = 3.0


def probe_database_host(
    timeout_sec: float = _DEFAULT_PROBE_TIMEOUT_SEC,
    *,
    override_host: str | None = None,
) -> bool:
    """Intenta una conexion TCP al host de la base con un timeout corto.

    Devuelve True si el host responde en el puerto configurado.
    Devuelve False para cualquier fallo de red, sin lanzar excepciones.

    Usar TCP (no SQLAlchemy) es mas rapido porque no necesita autenticacion
    ni negociacion de protocolo: solo verifica que el host este vivo y
    el puerto abierto.
    """
    host = override_host or settings.db_host
    try:
        with socket.create_connection(
            (host, settings.db_port),
            timeout=timeout_sec,
        ):
            return True
    except OSError:
        return False
