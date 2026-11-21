"""La llave con la que la API firma y valida las sesiones (JWT) de la PWA.

Hasta 2026-11-20 la llave era un texto fijo en el código público
("dev-secret-key-cambiar-en-produccion"): cualquiera que leyera el repo podía
fabricar un token de VEND-1. Ahora:

1. Si hay `POS_API_SECRET_KEY` (entorno o `pos_uniformes.env`) y no es la
   vieja pública, esa manda.
2. Si no, se usa la guardada en la carpeta de datos del POS
   (`satellite_data_dir()/data/api_secret.key`; en la tienda, que corre desde
   el código fuente, es `<checkout>/pos_uniformes/data/api_secret.key`).
3. Si no existe, se genera una al azar UNA vez, se guarda ahí (600 en Linux y
   macOS; en Windows se intenta con icacls, ver _escribir) y se reutiliza.

Así la tienda queda segura sola al actualizarse. Efecto visible: los tokens
firmados con la llave vieja dejan de servir y cada quien vuelve a entrar con
su PIN una vez.

La llave nunca se escribe en el log ni se muestra.
"""

from __future__ import annotations

import logging
import os
import secrets
import subprocess
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

LLAVE_PUBLICA_VIEJA = "dev-secret-key-cambiar-en-produccion"
NOMBRE_ARCHIVO = "api_secret.key"
# Una llave más corta que esto no se acepta del archivo (truncado o editado a mano).
_LARGO_MINIMO = 32

_ES_WINDOWS = sys.platform == "win32"
_candado = threading.Lock()
_llave_en_memoria: str | None = None


def ruta_llave() -> Path:
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir() / "data" / NOMBRE_ARCHIVO


def _es_utilizable(llave: str | None) -> bool:
    return bool(llave) and llave.strip() != LLAVE_PUBLICA_VIEJA


def _leer(ruta: Path) -> str | None:
    try:
        llave = ruta.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if len(llave) < _LARGO_MINIMO or not _es_utilizable(llave):
        return None
    return llave


def _cuenta_actual_windows() -> str | None:
    """El SID de la cuenta que corre la API (para icacls); None si no se pudo."""
    try:
        r = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=10, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    partes = [p.strip().strip('"') for p in r.stdout.strip().split(",")]
    if r.returncode == 0 and len(partes) >= 2 and partes[-1].startswith("S-1-"):
        return partes[-1]
    return None


def _restringir_en_windows(ruta: Path) -> None:
    """En Windows os.chmod no quita lectores: se quita la herencia del archivo y
    se deja solo a la cuenta que corre la API, a SYSTEM y a Administradores.
    Mejor esfuerzo: si no se puede, la llave sirve igual y se avisa en el log."""
    if not _ES_WINDOWS:
        return
    sid = _cuenta_actual_windows()
    if not sid:
        logger.warning("No pude saber la cuenta de Windows: %s queda con los permisos de su carpeta.", ruta)
        return
    permisos: list[str] = []
    for cuenta in (sid, "S-1-5-18", "S-1-5-32-544"):  # esta cuenta, SYSTEM, Administradores
        permisos += ["/grant:r", f"*{cuenta}:F"]
    try:
        r = subprocess.run(
            ["icacls", str(ruta), *permisos, "/inheritance:r"],
            capture_output=True, text=True, timeout=10, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        ok = r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    if not ok:
        logger.warning("No pude restringir los permisos de %s (icacls).", ruta)


def _escribir(ruta: Path, llave: str) -> str:
    """Guarda la llave y devuelve la que hay que usar: la que quedó en el archivo.

    Permisos: en Linux y macOS, 600. En Windows os.chmod no restringe nada, así
    que se usa icacls (_restringir_en_windows). Ojo: la tienda corre la API
    desde el código fuente, así que la llave queda en
    <checkout>/pos_uniformes/data/api_secret.key, junto a pos_uniformes.env (que
    ya trae la contraseña de Postgres): la carpeta del checkout debe ser solo de
    la cuenta del POS. Solo el bundle congelado la guarda en AppData.

    Varios procesos a la vez (el vigía relanza mientras el anterior sigue vivo,
    uvicorn con --workers): el primero que la crea gana y los demás leen y usan
    la suya; nadie pisa una llave válida. Un archivo que ya existía pero no
    sirve (vacío, truncado, la pública vieja) se reemplaza."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
    fd = os.open(str(temporal), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, (llave + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.chmod(temporal, 0o600)
    except OSError:
        pass
    _restringir_en_windows(temporal)
    try:
        try:
            # Atómico y solo si no existe: el archivo aparece ya completo.
            os.link(temporal, ruta)
            return llave
        except FileExistsError:
            pass
        except OSError:
            pass  # sistema de archivos sin enlaces duros: se sigue abajo
        ganadora = _leer(ruta)
        if ganadora:
            return ganadora  # otro proceso la creó primero (o ya estaba): se usa esa
        os.replace(temporal, ruta)  # la que había no sirve
        return _leer(ruta) or llave
    finally:
        try:
            os.unlink(temporal)
        except OSError:
            pass


def resolver_llave(configurada: str | None, ruta: Path | None = None) -> str:
    """La llave a usar: la configurada si sirve; si no, la del archivo; si no
    hay, una nueva que se guarda en el archivo."""
    if _es_utilizable(configurada):
        return configurada.strip()  # type: ignore[union-attr]
    if configurada and configurada.strip() == LLAVE_PUBLICA_VIEJA:
        logger.warning(
            "POS_API_SECRET_KEY trae la llave pública vieja: se ignora y se usa la guardada."
        )
    ruta = ruta or ruta_llave()
    existente = _leer(ruta)
    if existente:
        return existente
    nueva = secrets.token_urlsafe(48)
    try:
        nueva = _escribir(ruta, nueva)
        logger.info("Llave de sesiones de la API lista en %s.", ruta)
    except OSError as exc:
        # Sin carpeta escribible la API sigue sirviendo, pero las sesiones se
        # pierden en cada reinicio (se vuelve a entrar con PIN).
        logger.warning("No pude guardar la llave de sesiones en %s (%s): vive solo en memoria.", ruta, exc)
    return nueva


def llave_sesiones() -> str:
    """La llave del proceso: se resuelve la primera vez y se reutiliza."""
    global _llave_en_memoria
    if _llave_en_memoria is None:
        with _candado:
            if _llave_en_memoria is None:
                from pos_uniformes.utils.config import settings

                _llave_en_memoria = resolver_llave(settings.api_secret_key)
    return _llave_en_memoria


def olvidar_llave_en_memoria() -> None:
    """Para pruebas: obliga a resolverla de nuevo."""
    global _llave_en_memoria
    _llave_en_memoria = None
