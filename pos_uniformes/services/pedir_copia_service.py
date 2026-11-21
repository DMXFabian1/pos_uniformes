"""Pedirle al servidor de casa una copia nueva de la tienda (solo modo casa).

La Libreta de casa lee la copia viva, que se recarga con cada copia de la
tienda (cada 15 min). Al abrirla o recargarla, la PWA llama a
POST /api/v1/movil/actualizar y aquí se le pide al disparador de nucleo
(nucleo-pedir-copia, en servidor-nucleo) que saque una copia ya. Nunca se
espera a la copia: el disparador contesta al momento y la PWA vuelve a mirar
/movil/inicio hasta que «datos_de» cambie.

Configuración (solo en el contenedor de casa):
  POS_PWA_PEDIR_COPIA_URL         p. ej. http://192.168.68.115:8926/copia
  POS_PWA_PEDIR_COPIA_TOKEN_FILE  archivo con el token compartido (montado de
                                  solo lectura; se lee en cada petición)
Sin las dos (o con el archivo vacío) → "sin_configurar". No escribe en la base.

El token no viaja: es HTTP plano en la LAN de la casa. Cada petición va firmada
(cabecera X-Firma = "<segundos>.<nonce>.<HMAC-SHA256(token, "POST <ruta>
<segundos> <nonce>")>"); nucleo revisa la hora (±2 min) y no acepta un nonce dos
veces, así que una firma copiada de la red no sirve para pedir otra copia.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

# Lo que puede contestar el disparador (ver nucleo-pedir-copia)
ESTADOS_DEL_DISPARADOR = {
    "pidiendo", "en_curso", "reciente", "espera", "tienda_apagada", "sin_configurar",
    "fuera_de_horario", "tope",
}
LIMITE_S = 3.0

# Sin proxies del entorno: el disparador está en la red de la casa
_abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open


def _token(archivo: str) -> str:
    try:
        with open(archivo, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def firma(token: str, metodo: str, ruta: str, segundos: int | None = None, nonce: str | None = None) -> str:
    """Valor de la cabecera X-Firma (el mismo formato que revisa nucleo-pedir-copia)."""
    s = str(int(time.time()) if segundos is None else segundos)
    n = nonce or secrets.token_hex(12)
    texto = f"{metodo} {ruta} {s} {n}".encode()
    return f"{s}.{n}.{hmac.new(token.encode(), texto, hashlib.sha256).hexdigest()}"


def pedir_copia(limite_s: float | None = None) -> str:
    """Estado que contestó el disparador, "sin_configurar", "sin_respuesta"
    (no contestó a tiempo o no se alcanzó) o "error" (contestó con error)."""
    url = (os.getenv("POS_PWA_PEDIR_COPIA_URL") or "").strip()
    archivo = (os.getenv("POS_PWA_PEDIR_COPIA_TOKEN_FILE") or "").strip()
    token = _token(archivo) if archivo else ""
    if not url or not token:
        return "sin_configurar"
    peticion = urllib.request.Request(
        url, data=b"", method="POST",
        headers={"X-Firma": firma(token, "POST", urllib.parse.urlsplit(url).path or "/")},
    )
    try:
        with _abrir(peticion, timeout=limite_s or LIMITE_S) as r:
            datos = json.loads(r.read(4096) or b"{}")
    except urllib.error.HTTPError:
        return "error"
    except (urllib.error.URLError, OSError, ValueError):  # incluye el timeout
        return "sin_respuesta"
    estado = datos.get("estado") if isinstance(datos, dict) else None
    return estado if estado in ESTADOS_DEL_DISPARADOR else "error"
