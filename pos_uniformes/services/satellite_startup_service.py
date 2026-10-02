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


#: Cuánto espera el satélite a que la PC principal aparezca al arrancar.
#: Nace del escenario que más duele: se va la luz y todo se prende junto. El
#: servidor tarda en levantar Postgres y el kiosko, que bootea en segundos,
#: probaba UNA vez, no encontraba nada y se quedaba en modo local toda la
#: mañana (o se negaba a abrir, si tampoco tenía catálogo guardado).
ESPERA_ARRANQUE_SEG = 75.0
INTENTO_CADA_SEG = 3.0


def esperar_base(
    *,
    limite_seg: float = ESPERA_ARRANQUE_SEG,
    cada_seg: float = INTENTO_CADA_SEG,
    probe=None,
    dormir=None,
    reloj=None,
    avisar=None,
) -> bool:
    """Reintenta el probe hasta `limite_seg`. True en cuanto conteste.

    Devuelve en el primer intento si la PC ya está encendida, que es el caso
    de todos los días: esperar solo cuesta cuando de verdad no hay nadie.

    Todo inyectable (probe, sleep, reloj, aviso) para poder probarlo sin
    esperar de verdad.
    """
    import time as _time

    probe = probe or probe_database_host
    dormir = dormir or _time.sleep
    reloj = reloj or _time.monotonic

    inicio = reloj()
    intento = 0
    while True:
        if probe():
            return True
        intento += 1
        if reloj() - inicio >= limite_seg:
            return False
        if avisar is not None:
            restan = max(0, int(limite_seg - (reloj() - inicio)))
            try:
                avisar(intento, restan)
            except Exception:  # noqa: BLE001 — el aviso es adorno
                pass
        dormir(cada_seg)
