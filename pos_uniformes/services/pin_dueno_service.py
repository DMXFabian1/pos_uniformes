"""El PIN del dueño en el kiosko (Daniel, 2026-11-19).

Antes bastaba escanear o teclear el gafete del dueño para entrar como él a la
Libreta, a Conteos o para autorizar un precio especial. Ahora, además del
gafete, se pide su PIN: el mismo que se define en el POS principal
(Configuración › Empleadas › Definir PIN) y que se guarda en
`Empleada.pin_hash` con `AuthService.hash_password`.

Sin la PC principal se valida contra una copia local del hash, que el kiosko
refresca cada vez que tiene base (`data/pin_dueno.json`, fuera de git).

Aquí no hay Qt: el diálogo vive en `ui/helpers/pin_dueno_dialog.py`.

    verificar_pin(pin_hash, "1234")             # True / False, nunca truena
    verificar_pin_dueno("1234", en_linea=True)  # ResultadoPin(estado, mensaje)
    ControlIntentos().registrar_fallo(ahora)    # 5 fallos seguidos → 60 s
    debe_cerrar_sesion(ultimo, ahora)           # 5 min sin tocar → cerrar
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from pos_uniformes.services.auth_service import PBKDF2_PREFIX, AuthService
from pos_uniformes.services.employee_identity_service import EmployeeIdentityService
from pos_uniformes.services.nomina_service import OWNER_CODE

logger = logging.getLogger(__name__)

_PREFIJO_HASH = f"{PBKDF2_PREFIX}$"

# Estados de verificar_pin_dueno
OK = "ok"
INCORRECTO = "incorrecto"
SIN_PIN = "sin_pin"
SIN_DATOS = "sin_datos"

MENSAJE_OK = "PIN correcto."
MENSAJE_INCORRECTO = "PIN incorrecto."
MENSAJE_SIN_PIN = "Define tu PIN en el POS principal: Configuración › Empleadas › Definir PIN."
MENSAJE_SIN_DATOS = (
    "Sin conexión con la PC principal y sin copia del PIN en este kiosko. "
    "Conecta la PC principal una vez para que el kiosko guarde la copia."
)

# Control de intentos
MAX_FALLOS = 5
BLOQUEO_SEGUNDOS = 60

# Inactividad de la sesión del dueño
MINUTOS_INACTIVIDAD = 5


@dataclass(frozen=True)
class ResultadoPin:
    estado: str  # OK | INCORRECTO | SIN_PIN | SIN_DATOS
    mensaje: str

    @property
    def ok(self) -> bool:
        return self.estado == OK


# ── verificar ────────────────────────────────────────────────────────────


def _hash_valido(pin_hash: object) -> bool:
    return isinstance(pin_hash, str) and pin_hash.strip().startswith(_PREFIJO_HASH)


def verificar_pin(pin_hash: str | None, pin: str) -> bool:
    """¿El PIN coincide con el hash? Nunca compara en texto plano y nunca truena."""
    if not _hash_valido(pin_hash):
        return False
    try:
        limpio = EmployeeIdentityService.normalize_pin(str(pin or ""))
    except ValueError:
        return False
    try:
        return bool(AuthService.verify_password(limpio, str(pin_hash).strip()))
    except Exception:  # noqa: BLE001 — hash dañado (iteraciones, sal) = no coincide
        logger.warning("PIN del dueño: el hash guardado no se pudo leer")
        return False


def hash_del_dueno(session) -> str | None:
    """El pin_hash de la empleada activa con el código del dueño, o None."""
    from sqlalchemy import func, select

    from pos_uniformes.database.models import Empleada

    valor = session.scalar(
        select(Empleada.pin_hash).where(
            func.upper(Empleada.codigo) == OWNER_CODE,
            Empleada.activo.is_(True),
        )
    )
    valor = str(valor or "").strip()
    return valor or None


# ── copia local ──────────────────────────────────────────────────────────


def _ruta_local() -> Path:
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir() / "data" / "pin_dueno.json"


def borrar_copia_local() -> None:
    try:
        _ruta_local().unlink(missing_ok=True)
    except OSError:
        logger.warning("PIN del dueño: no se pudo borrar la copia local", exc_info=True)


def guardar_copia_local(pin_hash: str | None) -> None:
    """Escribe la copia de forma atómica (temporal + os.replace). Sin un hash
    válido —el dueño ya no tiene PIN— la copia se borra."""
    if not _hash_valido(pin_hash):
        borrar_copia_local()
        return
    ruta = _ruta_local()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    datos = {
        "codigo": OWNER_CODE,
        "pin_hash": str(pin_hash).strip(),
        "actualizado": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    fd, temporal = tempfile.mkstemp(prefix=".pin_dueno_", suffix=".tmp", dir=str(ruta.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporal, ruta)
    except Exception:
        try:
            os.unlink(temporal)
        except OSError:
            pass
        raise


def leer_copia_local() -> str | None:
    """El hash de la copia local; None si no hay copia o está dañada."""
    try:
        datos = json.loads(_ruta_local().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — sin archivo o dañado
        return None
    if not isinstance(datos, dict):
        return None
    if str(datos.get("codigo") or "").strip().upper() != OWNER_CODE:
        return None
    pin_hash = datos.get("pin_hash")
    return str(pin_hash).strip() if _hash_valido(pin_hash) else None


def refrescar_copia_local(session) -> None:
    """Lee el hash de la base y lo guarda. Nunca truena hacia afuera."""
    try:
        guardar_copia_local(hash_del_dueno(session))
    except Exception:  # noqa: BLE001 — la copia es un extra: se sigue sin ella
        logger.warning("PIN del dueño: no se pudo refrescar la copia local", exc_info=True)
        try:
            session.rollback()  # que la sesión siga sirviendo a quien la prestó
        except Exception:  # noqa: BLE001
            pass


# ── verificación completa ────────────────────────────────────────────────


def _hash_de_la_base(sesion_factory: Callable[[], object] | None) -> str | None:
    if sesion_factory is None:
        from pos_uniformes.database.connection import get_session as sesion_factory
    with sesion_factory() as session:
        return hash_del_dueno(session)


def verificar_pin_dueno(
    pin: str,
    *,
    sesion_factory: Callable[[], object] | None = None,
    en_linea: bool = True,
) -> ResultadoPin:
    """En línea manda la base (y de paso refresca la copia local); si la base
    truena o no hay conexión, se usa la copia local."""
    pin_hash: str | None = None
    leido_de_base = False
    if en_linea:
        try:
            pin_hash = _hash_de_la_base(sesion_factory)
            leido_de_base = True
        except Exception:  # noqa: BLE001 — base caída: se usa la copia
            logger.warning("PIN del dueño: sin base, se usa la copia local", exc_info=True)
        if leido_de_base:
            try:
                guardar_copia_local(pin_hash)
            except Exception:  # noqa: BLE001
                logger.warning("PIN del dueño: no se pudo guardar la copia local", exc_info=True)
    if not leido_de_base:
        pin_hash = leer_copia_local()
        if pin_hash is None:
            return ResultadoPin(SIN_DATOS, MENSAJE_SIN_DATOS)
    if not _hash_valido(pin_hash):
        return ResultadoPin(SIN_PIN, MENSAJE_SIN_PIN)
    if verificar_pin(pin_hash, pin):
        return ResultadoPin(OK, MENSAJE_OK)
    return ResultadoPin(INCORRECTO, MENSAJE_INCORRECTO)


# ── intentos ─────────────────────────────────────────────────────────────


class ControlIntentos:
    """Tras `max_fallos` PIN incorrectos seguidos, bloquea `bloqueo_seg`
    segundos. Recibe la hora (segundos, p. ej. time.monotonic()): es puro."""

    def __init__(self, max_fallos: int = MAX_FALLOS, bloqueo_seg: float = BLOQUEO_SEGUNDOS) -> None:
        self.max_fallos = int(max_fallos)
        self.bloqueo_seg = float(bloqueo_seg)
        self.fallos = 0
        self._bloqueado_hasta: float | None = None

    def segundos_restantes(self, ahora: float) -> int:
        """Segundos que faltan de bloqueo (redondeado hacia arriba); 0 si se puede intentar."""
        if self._bloqueado_hasta is None:
            return 0
        faltan = self._bloqueado_hasta - float(ahora)
        if faltan <= 0:
            self._bloqueado_hasta = None
            self.fallos = 0
            return 0
        return int(faltan) + (0 if float(faltan).is_integer() else 1)

    def bloqueado(self, ahora: float) -> bool:
        return self.segundos_restantes(ahora) > 0

    def registrar_fallo(self, ahora: float) -> int:
        """Anota un PIN incorrecto. Devuelve los segundos de bloqueo (0 si aún no)."""
        if self.bloqueado(ahora):
            return self.segundos_restantes(ahora)
        self.fallos += 1
        if self.fallos >= self.max_fallos:
            self._bloqueado_hasta = float(ahora) + self.bloqueo_seg
            return self.segundos_restantes(ahora)
        return 0

    def registrar_exito(self) -> None:
        self.fallos = 0
        self._bloqueado_hasta = None


# ── inactividad ──────────────────────────────────────────────────────────


def debe_cerrar_sesion(ultimo_toque, ahora, minutos: float = MINUTOS_INACTIVIDAD) -> bool:
    """¿Pasaron `minutos` sin tocar el kiosko? Acepta segundos (float) o datetimes."""
    if ultimo_toque is None or ahora is None:
        return False
    delta = ahora - ultimo_toque
    segundos = delta.total_seconds() if hasattr(delta, "total_seconds") else float(delta)
    return segundos >= float(minutos) * 60
