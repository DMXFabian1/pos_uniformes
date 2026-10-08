"""El chat del bot se limpia solo: un menú fijado arriba y lo demás se va.

Daniel (2026-10-08): *"me gustaría que quede un menú fijado, y lo demás lo borre
24 horas después"*.

El chat es un tablero, no un archivo. Lo que vale la pena guardar ya está en la
base —los cortes, los préstamos, los retiros—; lo de Telegram es el aviso, y un
aviso de hace tres semanas solo estorba para encontrar el de hoy.

Dos límites de Telegram que conviene tener presentes, porque mandan sobre el
diseño:

- **El bot solo borra lo suyo.** En un chat privado no puede borrar los
  mensajes que escribe Daniel. Sus comandos se quedan; eso no se puede
  arreglar desde aquí.
- **Después de 48 horas ya no se puede borrar nada.** Por eso el barrido no
  reintenta para siempre: lo que se pasó de ese plazo se olvida, porque
  pedirlo otra vez sería gastar una llamada para que Telegram diga que no.

El menú fijado no se barre nunca: es lo único que debe seguir ahí mañana.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

#: Cuánto vive un mensaje del bot.
HORAS_DE_VIDA = 24.0
#: Pasado esto, Telegram ya no deja borrar. Se olvida y ya.
HORAS_TOPE_TELEGRAM = 48.0
#: Cada cuánto se barre. No en cada vuelta del bot (son ~25 s): borrar es una
#: llamada por mensaje y no hay prisa ninguna.
MINUTOS_ENTRE_BARRIDOS = 15.0


def ruta_estado() -> Path:
    from pos_uniformes.utils.config import runtime_base_dir

    return runtime_base_dir() / "data" / "bot_mensajes.json"


def _leer() -> dict:
    ruta = ruta_estado()
    if not ruta.exists():
        return {"menu_id": 0, "mensajes": [], "ultimo_barrido": 0.0}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        datos.setdefault("menu_id", 0)
        datos.setdefault("mensajes", [])
        datos.setdefault("ultimo_barrido", 0.0)
        return datos
    except Exception:  # noqa: BLE001 — un archivo roto no deja mudo al bot
        return {"menu_id": 0, "mensajes": [], "ultimo_barrido": 0.0}


def _guardar(datos: dict) -> None:
    ruta = ruta_estado()
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(datos), encoding="utf-8")
    except OSError:
        logger.warning("No se pudo guardar la lista de mensajes del bot")


def anotar(message_id: int) -> None:
    """Apunta un mensaje recién mandado para borrarlo mañana.

    Se llama desde el único lugar que manda mensajes, y no desde cada sitio
    que escribe uno: así no hay forma de que alguien agregue un aviso nuevo y
    se le olvide anotarlo.
    """
    mid = int(message_id or 0)
    if mid <= 0:
        return
    datos = _leer()
    if mid == int(datos.get("menu_id") or 0):
        return
    datos["mensajes"].append({"id": mid, "ts": time.time()})
    _guardar(datos)


def menu_fijado() -> int:
    """El id del menú que está fijado arriba, o 0 si no hay."""
    return int(_leer().get("menu_id") or 0)


def recordar_menu(message_id: int) -> None:
    """Guarda cuál es el menú para no barrerlo nunca."""
    datos = _leer()
    datos["menu_id"] = int(message_id or 0)
    # Si ya estaba apuntado como mensaje normal, se saca de la lista: sería la
    # única forma de que el menú se borrara solo a las 24 horas.
    datos["mensajes"] = [m for m in datos["mensajes"] if int(m["id"]) != int(message_id or 0)]
    _guardar(datos)


def toca_barrer(ahora: float | None = None) -> bool:
    ahora = ahora if ahora is not None else time.time()
    return (ahora - float(_leer().get("ultimo_barrido") or 0.0)) >= MINUTOS_ENTRE_BARRIDOS * 60


def barrer(*, borrar, ahora: float | None = None) -> int:
    """Borra lo que ya cumplió su tiempo. Devuelve cuántos se fueron.

    `borrar(message_id) -> bool` hace la llamada a Telegram. Entra como
    parámetro para poder probar esto sin red.
    """
    ahora = ahora if ahora is not None else time.time()
    datos = _leer()
    menu = int(datos.get("menu_id") or 0)
    quedan, borrados = [], 0
    for m in datos.get("mensajes", []):
        mid, ts = int(m.get("id") or 0), float(m.get("ts") or 0.0)
        edad = (ahora - ts) / 3600.0
        if mid == menu or mid <= 0:
            continue
        if edad < HORAS_DE_VIDA:
            quedan.append(m)
            continue
        if edad >= HORAS_TOPE_TELEGRAM:
            # Telegram ya no deja. Se olvida en vez de reintentar cada 15
            # minutos hasta el fin de los tiempos.
            logger.info("Mensaje %s ya no se puede borrar (%.0f h)", mid, edad)
            continue
        try:
            if borrar(mid):
                borrados += 1
            else:
                quedan.append(m)
        except Exception:  # noqa: BLE001 — un borrado fallido se reintenta
            quedan.append(m)
    datos["mensajes"] = quedan
    datos["ultimo_barrido"] = ahora
    _guardar(datos)
    return borrados
