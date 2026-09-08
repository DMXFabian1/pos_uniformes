"""Configuración local del DVR de cámaras (ajuste por máquina).

El DVR Dahua de la tienda entrega video por RTSP dentro de la red local. Cada
kiosko guarda aquí cómo llegar a él (host, usuario, contraseña) y la lista de
canales con su nombre y si es una cámara de *entrada*.

Reglas de acceso (decisión de Daniel, 2026-09-08):
  - Empleadas: solo ven las cámaras marcadas como entrada.
  - Administrador (PIN): ve todas.

Vive en `satellite_data_dir()/data/dvr_settings.json`. Si el archivo no existe,
se toman defaults del entorno (`POS_UNIFORMES_DVR_HOST`, `_USER`, `_PASSWORD`)
para que la Mac de Daniel funcione sin pasar por la pantalla de configuración.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from pos_uniformes.utils.config import load_runtime_env_overrides, satellite_data_dir

_CACHE_FILENAME = "dvr_settings.json"
_ENV_HOST = "POS_UNIFORMES_DVR_HOST"
_ENV_USER = "POS_UNIFORMES_DVR_USER"
_ENV_PASSWORD = "POS_UNIFORMES_DVR_PASSWORD"

RTSP_PORT_DEFAULT = 554
HTTP_PORT_DEFAULT = 80


@dataclass
class CanalDVR:
    canal: int
    nombre: str
    entrada: bool = False


@dataclass
class DVRSettings:
    host: str = ""
    user: str = ""
    password: str = ""
    rtsp_port: int = RTSP_PORT_DEFAULT
    http_port: int = HTTP_PORT_DEFAULT
    canales: list[CanalDVR] = field(default_factory=list)

    def configurado(self) -> bool:
        return bool(self.host.strip() and self.user.strip())

    def canales_visibles(self, admin: bool) -> list[CanalDVR]:
        """Admin ve todo; empleada solo las cámaras de entrada."""
        if admin:
            return list(self.canales)
        return [c for c in self.canales if c.entrada]

    def _rtsp_base(self) -> str:
        auth = f"{quote(self.user, safe='')}:{quote(self.password, safe='')}@" if self.user else ""
        return f"rtsp://{auth}{self.host}:{self.rtsp_port}"

    def rtsp_url(self, canal: int, substream: bool = True) -> str:
        """URL RTSP Dahua. `substream` = resolución baja (mosaico); False = principal."""
        subtype = 1 if substream else 0
        return f"{self._rtsp_base()}/cam/realmonitor?channel={int(canal)}&subtype={subtype}"

    def playback_url(self, canal: int, inicio: datetime, fin: datetime) -> str:
        """Grabación del DVR entre `inicio` y `fin` (hora local del DVR, stream principal).

        Dahua acepta `cam/playback` con `starttime`/`endtime` en formato
        `AAAA_MM_DD_HH_MM_SS`. El DVR reporta la duración del clip y permite
        buscar posición, así que QMediaPlayer lo trata como un archivo.
        """
        if fin <= inicio:
            raise ValueError("fin debe ser posterior a inicio")
        fmt = "%Y_%m_%d_%H_%M_%S"
        return (
            f"{self._rtsp_base()}/cam/playback?channel={int(canal)}&subtype=0"
            f"&starttime={inicio.strftime(fmt)}&endtime={fin.strftime(fmt)}"
        )

    def canal_por_nombre(self, nombre: str, admin: bool) -> CanalDVR | None:
        """Primer canal visible cuyo nombre contiene `nombre` (sin distinguir mayúsculas)."""
        clave = (nombre or "").strip().upper()
        if not clave:
            return None
        for c in self.canales_visibles(admin):
            if clave in c.nombre.upper():
                return c
        return None


def _cache_path() -> Path:
    return satellite_data_dir() / "data" / _CACHE_FILENAME


def es_entrada_por_nombre(nombre: str) -> bool:
    return "ENTRADA" in (nombre or "").upper()


def _env_default(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        value = load_runtime_env_overrides().get(name, "")
    return (value or "").strip()


def _from_env() -> DVRSettings:
    return DVRSettings(
        host=_env_default(_ENV_HOST),
        user=_env_default(_ENV_USER),
        password=_env_default(_ENV_PASSWORD),
    )


def save_dvr_settings(settings: DVRSettings) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(settings)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_dvr_settings() -> DVRSettings:
    """Archivo local si existe; si no, defaults del entorno; nunca lanza."""
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return _from_env()
    try:
        canales = []
        for raw in data.get("canales", []) or []:
            canales.append(
                CanalDVR(
                    canal=int(raw.get("canal")),
                    nombre=str(raw.get("nombre", "")).strip() or f"Canal {int(raw.get('canal'))}",
                    entrada=bool(raw.get("entrada", False)),
                )
            )
        env = _from_env()
        return DVRSettings(
            host=str(data.get("host", "")).strip() or env.host,
            user=str(data.get("user", "")).strip() or env.user,
            password=str(data.get("password", "")) or env.password,
            rtsp_port=int(data.get("rtsp_port", RTSP_PORT_DEFAULT) or RTSP_PORT_DEFAULT),
            http_port=int(data.get("http_port", HTTP_PORT_DEFAULT) or HTTP_PORT_DEFAULT),
            canales=canales,
        )
    except Exception:  # noqa: BLE001
        return _from_env()


# --- Detección de canales vía la API HTTP del DVR (Dahua CGI) ----------------

_TITLE_RE = re.compile(r"ChannelTitle\[(\d+)\]\.Name=(.*)")


def parse_channel_titles(texto: str) -> list[CanalDVR]:
    """Convierte la respuesta de `configManager.cgi?name=ChannelTitle` en canales.

    Dahua numera los canales desde 0 en la API y desde 1 en RTSP.
    """
    canales: list[CanalDVR] = []
    for linea in (texto or "").splitlines():
        m = _TITLE_RE.search(linea.strip())
        if not m:
            continue
        nombre = m.group(2).strip()
        canal = int(m.group(1)) + 1
        canales.append(CanalDVR(canal=canal, nombre=nombre or f"Canal {canal}", entrada=es_entrada_por_nombre(nombre)))
    canales.sort(key=lambda c: c.canal)
    return canales


def detectar_canales(settings: DVRSettings, timeout: float = 6.0) -> list[CanalDVR]:
    """Pregunta al DVR los nombres de sus canales. Lanza `RuntimeError` si falla."""
    import urllib.error
    import urllib.request

    if not settings.configurado():
        raise RuntimeError("Falta el host o el usuario del DVR.")
    url = (
        f"http://{settings.host}:{settings.http_port}"
        "/cgi-bin/configManager.cgi?action=getConfig&name=ChannelTitle"
    )
    passwd = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    passwd.add_password(None, url, settings.user, settings.password)
    opener = urllib.request.build_opener(
        urllib.request.HTTPDigestAuthHandler(passwd),
        urllib.request.HTTPBasicAuthHandler(passwd),
    )
    try:
        with opener.open(url, timeout=timeout) as resp:
            texto = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError("El DVR rechazó el usuario o la contraseña.") from exc
        raise RuntimeError(f"El DVR respondió HTTP {exc.code}.") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"No se pudo conectar al DVR en {settings.host}: {exc}") from exc
    canales = parse_channel_titles(texto)
    if not canales:
        raise RuntimeError("El DVR no devolvió nombres de canal.")
    return canales

