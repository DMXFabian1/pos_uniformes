"""El chat del bot se limpia solo: cada mañana amanece con un menú nuevo fijado.

Daniel (2026-10-08): *"me gustaría que quede un menú fijado, y lo demás lo borre
24 horas después"*. Y el 2026-10-15 lo cambió a **una limpieza al día, a la hora
de apertura**: el chat amanece limpio con el tablero del día, en vez de irse
borrando a cuentagotas. Las alertas, cortes y resúmenes se conservan DOS días
(lo de un lunes se ve lunes y martes y se va el miércoles): estando de viaje se
perdían antes de leerlas (2026-10-10).

El chat es un tablero, no un archivo. Lo que vale la pena guardar ya está en la
base —los cortes, los préstamos, los retiros—; lo de Telegram es el aviso, y un
aviso de hace tres semanas solo estorba para encontrar el de hoy.

Dos límites de Telegram que conviene tener presentes, porque mandan sobre el
diseño:

- **En un chat privado el bot SÍ puede borrar lo que le escribe Daniel.** Se
  creía que no (lo decía este mismo comentario) y sus comandos se quedaban
  para siempre. La API de Telegram lo permite para mensajes recibidos en
  chats privados, con el mismo límite de 48 horas.
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

#: Pasado esto, Telegram ya no deja borrar. Se olvida y ya.
HORAS_TOPE_TELEGRAM = 48.0

def ruta_estado() -> Path:
    from pos_uniformes.utils.config import runtime_base_dir

    return runtime_base_dir() / "data" / "bot_mensajes.json"


#: El hilo del respaldo también manda mensajes (y los anota) mientras el
#: principal barre o refresca el menú: sin candado un apunte se perdía y
#: ese mensaje no se barría nunca (2026-10-10).
_CANDADO = __import__("threading").RLock()


def _leer() -> dict:
    ruta = ruta_estado()
    if not ruta.exists():
        return {"menu_id": 0, "mensajes": [], "ultima_limpieza": "", "menu_refrescado": 0.0}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        datos.setdefault("menu_id", 0)
        datos.setdefault("mensajes", [])
        datos.setdefault("ultima_limpieza", "")
        datos.setdefault("menu_refrescado", 0.0)
        datos.setdefault("menu_huella", "")
        return datos
    except Exception:  # noqa: BLE001 — un archivo roto no deja mudo al bot
        return {"menu_id": 0, "mensajes": [], "ultima_limpieza": "", "menu_refrescado": 0.0}


def _guardar(datos: dict) -> None:
    ruta = ruta_estado()
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(datos), encoding="utf-8")
    except OSError:
        logger.warning("No se pudo guardar la lista de mensajes del bot")


def anotar(message_id: int, *, conservar: bool = False, ts: float | None = None) -> None:
    """Apunta un mensaje para la limpieza de la mañana.

    Se llama desde el único lugar que manda mensajes (y desde donde llegan los
    de Daniel), no desde cada sitio que escribe uno: así no hay forma de que
    alguien agregue un aviso nuevo y se le olvide anotarlo.

    `conservar`: alertas, cortes y resúmenes. Se quedan dos días.
    `ts`: cuándo se escribió (los de Daniel traen su propia hora).
    """
    mid = int(message_id or 0)
    if mid <= 0:
        return
    with _CANDADO:
        datos = _leer()
        if mid == int(datos.get("menu_id") or 0):
            return
        if any(int(m.get("id") or 0) == mid for m in datos["mensajes"]):
            return
        apunte = {"id": mid, "ts": float(ts) if ts else time.time()}
        if conservar:
            apunte["conservar"] = True
        datos["mensajes"].append(apunte)
        _guardar(datos)


def menu_fijado() -> int:
    """El id del menú que está fijado arriba, o 0 si no hay."""
    return int(_leer().get("menu_id") or 0)


def recordar_menu(message_id: int) -> None:
    """Guarda cuál es el menú para no barrerlo nunca."""
    datos = _leer()
    datos["menu_id"] = int(message_id or 0)
    # Si ya estaba apuntado como mensaje normal, se saca de la lista: sería la
    # única forma de que el menú se borrara en la limpieza.
    datos["mensajes"] = [m for m in datos["mensajes"] if int(m["id"]) != int(message_id or 0)]
    _guardar(datos)


#: Cada cuánto se reescribe la cabecera del menú fijado. Más seguido sería
#: gastar llamadas para cambiar un par de cifras; más espaciado y el tablero
#: enseña números de hace rato, que es lo que lo volvía mentiroso.
MINUTOS_ENTRE_MENUS = 10.0


def toca_refrescar_menu(ahora: float | None = None) -> bool:
    ahora = ahora if ahora is not None else time.time()
    return (ahora - float(_leer().get("menu_refrescado") or 0.0)) >= MINUTOS_ENTRE_MENUS * 60


def anotar_menu_refrescado(ahora: float | None = None) -> None:
    datos = _leer()
    datos["menu_refrescado"] = ahora if ahora is not None else time.time()
    _guardar(datos)


def huella_del_menu() -> str:
    """Cómo quedó escrito el menú la última vez."""
    return str(_leer().get("menu_huella") or "")


def anotar_huella_del_menu(texto: str) -> None:
    import hashlib

    datos = _leer()
    datos["menu_huella"] = hashlib.sha1(
        str(texto or "").encode("utf-8")
    ).hexdigest()[:16]
    _guardar(datos)


# ── La limpieza de la mañana ─────────────────────────────────────────────────

#: Días que se quedan las alertas, cortes y resúmenes (Daniel, 2026-10-15).
DIAS_QUE_SE_CONSERVA = 2


def _apertura(dia):
    from datetime import datetime

    from pos_uniformes.services.horario_tienda_service import hora_apertura

    return datetime.combine(dia, hora_apertura(dia))


def toca_limpiar(ahora=None) -> bool:
    """Una vez al día, desde la hora de apertura (o en cuanto prenda la PC)."""
    from datetime import datetime

    ahora = ahora or datetime.now()
    if ahora < _apertura(ahora.date()):
        return False
    return str(_leer().get("ultima_limpieza") or "") != ahora.date().isoformat()


def limpiar_del_dia(*, borrar, ahora=None) -> int:
    """Borra lo de antes de abrir y lo conservado de hace dos días o más.

    `borrar(message_id) -> bool` hace la llamada a Telegram (parámetro para
    probarlo sin red). Devuelve cuántos se borraron. El menú no se toca aquí:
    lo renueva quien llama, después de esto.
    """
    from datetime import datetime, timedelta

    ahora = ahora or datetime.now()
    hoy = ahora.date()
    corte_normal = _apertura(hoy).timestamp()
    # Lo conservado se va si es de antier o antes: lo de ayer y hoy se queda.
    corte_conservado = datetime.combine(hoy - timedelta(days=DIAS_QUE_SE_CONSERVA - 1), datetime.min.time()).timestamp()
    tope = HORAS_TOPE_TELEGRAM * 3600
    momento = ahora.timestamp()
    with _CANDADO:
        datos = _leer()
        menu = int(datos.get("menu_id") or 0)
        quedan, borrados = [], 0
        for m in datos.get("mensajes", []):
            mid, ts = int(m.get("id") or 0), float(m.get("ts") or 0.0)
            if mid == menu or mid <= 0:
                continue
            limite = corte_conservado if m.get("conservar") else corte_normal
            if ts >= limite:
                quedan.append(m)
                continue
            if momento - ts >= tope:
                # Telegram ya no deja: se olvida en vez de insistir cada día.
                logger.info("Mensaje %s ya no se puede borrar (%.0f h)", mid, (momento - ts) / 3600)
                continue
            try:
                if borrar(mid):
                    borrados += 1
                else:
                    quedan.append(m)
            except Exception:  # noqa: BLE001 — un borrado fallido se reintenta mañana
                quedan.append(m)
        datos["mensajes"] = quedan
        datos["ultima_limpieza"] = hoy.isoformat()
        _guardar(datos)
    return borrados
