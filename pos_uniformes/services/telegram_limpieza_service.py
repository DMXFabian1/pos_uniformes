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

**Desde el 2026-11-20 se barre en cada vuelta del bot**, no una sola vez en la
mañana (Daniel: «todavía no se limpia solo y se siguen acumulando mensajes
antiguos»). Lo que se encontró:

- Lo conservado vivía «dos días» contados por medianoche y se barría en la
  limpieza de la mañana: lo que salía antes de abrir ya tenía más de 48 h al
  llegar su turno y se olvidaba sin borrarse. Ahora vive 36 h contadas desde
  que salió (se ve hoy y mañana) y se borra en la vuelta en que se cumplen,
  siempre lejos del tope.
- Un barrido sin red daba el día por limpio. Ahora un error de red no borra
  nada de la lista: se reintenta en unos minutos.
- Varios procesos (bot, tareas de la tarde, actualizar.py) escriben este
  archivo: ahora hay un candado entre procesos, y un archivo que no se pudo
  leer (antivirus) ya no se pisa con una lista vacía.
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


class NoSeLeyo(OSError):
    """El archivo existe pero no se pudo leer (antivirus, otro proceso).
    Quien iba a escribir no escribe: pisarlo con una lista vacía olvidaba
    todo lo apuntado, y esos mensajes ya no se barrían nunca."""


def _vacio() -> dict:
    return {"menu_id": 0, "mensajes": [], "ultima_limpieza": "", "menu_refrescado": 0.0,
            "menu_huella": ""}


def _leer() -> dict:
    ruta = ruta_estado()
    if not ruta.exists():
        return _vacio()
    texto = None
    for intento in range(3):
        try:
            texto = ruta.read_text(encoding="utf-8")
            break
        except OSError:
            if intento == 2:
                raise NoSeLeyo(f"No se pudo leer {ruta.name}")
            time.sleep(0.2)
    try:
        datos = json.loads(texto or "")
        if not isinstance(datos, dict):
            raise ValueError("no es un objeto")
    except Exception:  # noqa: BLE001 — un archivo roto no deja mudo al bot
        # Se guarda aparte para poder ver qué pasó, y se empieza de nuevo.
        try:
            ruta.replace(ruta.with_suffix(".roto.json"))
        except OSError:
            pass
        return _vacio()
    for llave, valor in _vacio().items():
        datos.setdefault(llave, valor)
    return datos


def _leer_o_vacio() -> dict:
    """Para solo consultar: si no se pudo leer, como si no hubiera nada."""
    try:
        return _leer()
    except NoSeLeyo:
        return _vacio()


#: Cuánto se espera el candado de otro proceso, y a partir de cuándo un
#: candado se da por abandonado (un proceso que murió con él puesto).
_ESPERA_CANDADO_S = 5.0
_CANDADO_ABANDONADO_S = 30.0


class _CandadoEntreProcesos:
    """Un archivo `.lock` creado con O_EXCL: funciona igual en Windows y Mac.

    El RLock cuida los hilos de este proceso; esto cuida a los demás procesos
    (el bot, las tareas de la tarde, actualizar.py) que escriben la misma
    lista. Si no se consigue a tiempo se sigue sin él: es peor quedarse mudo."""

    def __init__(self) -> None:
        self._ruta = None
        self._propio = False

    def __enter__(self):
        import os

        _CANDADO.acquire()
        self._ruta = ruta_estado().with_suffix(".lock")
        try:
            self._ruta.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return self
        limite = time.monotonic() + _ESPERA_CANDADO_S
        while True:
            try:
                fd = os.open(str(self._ruta), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                self._propio = True
                return self
            except FileExistsError:
                try:
                    if time.time() - self._ruta.stat().st_mtime > _CANDADO_ABANDONADO_S:
                        self._ruta.unlink()
                        continue
                except OSError:
                    pass
                if time.monotonic() >= limite:
                    logger.warning("Lista de mensajes del bot: se sigue sin candado")
                    return self
                time.sleep(0.05)
            except OSError:
                return self

    def __exit__(self, *exc) -> None:
        try:
            if self._propio and self._ruta is not None:
                self._ruta.unlink()
        except OSError:
            pass
        finally:
            self._propio = False
            _CANDADO.release()


def _modificar(cambio) -> bool:
    """Leer, cambiar y guardar bajo los dos candados. False si no se pudo leer."""
    with _CandadoEntreProcesos():
        try:
            datos = _leer()
        except NoSeLeyo:
            logger.warning("Lista de mensajes del bot: no se pudo leer; no se toca")
            return False
        cambio(datos)
        _guardar(datos)
        return True


def _guardar(datos: dict) -> None:
    ruta = ruta_estado()
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        from pos_uniformes.utils.archivo_atomico import escribir_json

        escribir_json(ruta, datos)
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

    def _cambio(datos: dict) -> None:
        if mid == int(datos.get("menu_id") or 0):
            return
        if any(int(m.get("id") or 0) == mid for m in datos["mensajes"]):
            return
        apunte = {"id": mid, "ts": float(ts) if ts else time.time()}
        if conservar:
            apunte["conservar"] = True
        datos["mensajes"].append(apunte)

    _modificar(_cambio)


def menu_fijado() -> int:
    """El id del menú que está fijado arriba, o 0 si no hay."""
    return int(_leer_o_vacio().get("menu_id") or 0)


def recordar_menu(message_id: int) -> None:
    """Guarda cuál es el menú para no barrerlo nunca."""
    nuevo = int(message_id or 0)

    def _cambio(datos: dict) -> None:
        datos["menu_id"] = nuevo
        # Si ya estaba apuntado como mensaje normal, se saca de la lista: sería
        # la única forma de que el menú se borrara en la limpieza.
        datos["mensajes"] = [m for m in datos["mensajes"] if int(m.get("id") or 0) != nuevo]

    _modificar(_cambio)


#: Cada cuánto se reescribe la cabecera del menú fijado. Más seguido sería
#: gastar llamadas para cambiar un par de cifras; más espaciado y el tablero
#: enseña números de hace rato, que es lo que lo volvía mentiroso.
MINUTOS_ENTRE_MENUS = 10.0


def toca_refrescar_menu(ahora: float | None = None) -> bool:
    ahora = ahora if ahora is not None else time.time()
    return (ahora - float(_leer_o_vacio().get("menu_refrescado") or 0.0)) >= MINUTOS_ENTRE_MENUS * 60


def anotar_menu_refrescado(ahora: float | None = None) -> None:
    momento = ahora if ahora is not None else time.time()
    _modificar(lambda datos: datos.__setitem__("menu_refrescado", momento))


def huella_del_menu() -> str:
    """Cómo quedó escrito el menú la última vez."""
    return str(_leer_o_vacio().get("menu_huella") or "")


def anotar_huella_del_menu(texto: str) -> None:
    import hashlib

    huella = hashlib.sha1(str(texto or "").encode("utf-8")).hexdigest()[:16]
    _modificar(lambda datos: datos.__setitem__("menu_huella", huella))


# ── El barrido ───────────────────────────────────────────────────────────────

#: Lo conservado (alertas, cortes, resúmenes) vive esto, contado desde que
#: salió: se ve hoy y mañana, y se borra siempre antes del tope de Telegram
#: (Daniel, 2026-11-20: «hasta el día siguiente»).
HORAS_CONSERVADO = 36.0

#: Una respuesta normal se va en la mañana siguiente; si por algo no se fue
#: (la PC prendió tarde), a esta edad se borra igual, antes del tope.
HORAS_MAXIMO_NORMAL = 40.0

#: Si Telegram contestó que no (ya no existe, no se puede), se reintenta hasta
#: esta pausa después, no en cada vuelta del bot.
MINUTOS_ENTRE_REINTENTOS = 60.0

#: Sin red no se insiste en cada vuelta.
MINUTOS_SIN_RED = 5.0

#: Resultados de `borrar`. También vale True (= BORRADO) y False (= NO_SE_PUDO).
BORRADO = "ok"
NO_SE_PUDO = "no"      # Telegram contestó: ya no existe, o ya no se puede
SIN_RED = "red"        # no se supo: se reintenta sin perder nada


def _apertura(dia):
    from datetime import datetime

    from pos_uniformes.services.horario_tienda_service import hora_apertura

    return datetime.combine(dia, hora_apertura(dia))


def toca_limpiar(ahora=None) -> bool:
    """¿Toca renovar el menú de la mañana? Una vez al día, desde la apertura
    (o en cuanto prenda la PC). El barrido de mensajes ya no espera a esto."""
    from datetime import datetime

    ahora = ahora or datetime.now()
    if ahora < _apertura(ahora.date()):
        return False
    return str(_leer_o_vacio().get("ultima_limpieza") or "") != ahora.date().isoformat()


def marcar_limpieza_de_hoy(ahora=None) -> None:
    """El menú de hoy ya quedó: no se renueva otra vez hoy."""
    from datetime import datetime

    hoy = (ahora or datetime.now()).date().isoformat()
    _modificar(lambda datos: datos.__setitem__("ultima_limpieza", hoy))


def _ya_toca(apunte: dict, ahora) -> bool:
    ts = float(apunte.get("ts") or 0.0)
    edad_h = (ahora.timestamp() - ts) / 3600
    if apunte.get("conservar"):
        return edad_h >= HORAS_CONSERVADO
    if edad_h >= HORAS_MAXIMO_NORMAL:
        return True
    apertura = _apertura(ahora.date())
    return ahora >= apertura and ts < apertura.timestamp()


def _resultado(valor) -> str:
    if valor is True:
        return BORRADO
    if valor is False or valor is None:
        return NO_SE_PUDO
    return str(valor)


def barrer(*, borrar, ahora=None) -> int:
    """Borra lo que ya cumplió su tiempo. Se llama en cada vuelta del bot.

    `borrar(message_id)` hace la llamada a Telegram y devuelve BORRADO,
    NO_SE_PUDO o SIN_RED (o True/False). Una excepción cuenta como SIN_RED.
    Devuelve cuántos se borraron. El menú fijado nunca se toca.

    - BORRADO: se quita de la lista.
    - NO_SE_PUDO: se reintenta en una hora; pasadas las 48 h se olvida.
    - SIN_RED: se deja todo como está y se para la vuelta (sin red, cada
      intento tarda y falla igual); se vuelve a probar en unos minutos.
    """
    from datetime import datetime

    ahora = ahora or datetime.now()
    momento = ahora.timestamp()
    tope = HORAS_TOPE_TELEGRAM * 3600
    datos = _leer_o_vacio()
    if float(datos.get("sin_red_hasta") or 0.0) > momento:
        return 0
    menu = int(datos.get("menu_id") or 0)
    pendientes = [
        m for m in datos.get("mensajes", [])
        if int(m.get("id") or 0) not in (0, menu)
        and float(m.get("reintentar") or 0.0) <= momento
        and _ya_toca(m, ahora)
    ]
    if not pendientes:
        return 0
    quitar: set[int] = set()
    borrados = 0
    reintentar: dict[int, float] = {}
    sin_red = False
    for m in pendientes:
        mid = int(m["id"])
        try:
            res = _resultado(borrar(mid))
        except Exception:  # noqa: BLE001 — sin red o algo raro: no se pierde
            res = SIN_RED
        if res == BORRADO:
            quitar.add(mid)
            borrados += 1
        elif res == SIN_RED:
            sin_red = True
            break
        elif momento - float(m.get("ts") or 0.0) >= tope:
            # Telegram ya no deja borrarlo: se olvida en vez de insistir.
            logger.info("Mensaje %s ya no se puede borrar; se olvida", mid)
            quitar.add(mid)
        else:
            reintentar[mid] = momento + MINUTOS_ENTRE_REINTENTOS * 60

    def _cambio(d: dict) -> None:
        # Se relee bajo el candado y solo se quita lo que se borró: lo que
        # otro proceso anotó mientras tanto no se pierde.
        quedan = []
        for m in d.get("mensajes", []):
            mid = int(m.get("id") or 0)
            if mid in quitar:
                continue
            if mid in reintentar:
                m["reintentar"] = reintentar[mid]
            quedan.append(m)
        d["mensajes"] = quedan
        if sin_red:
            d["sin_red_hasta"] = momento + MINUTOS_SIN_RED * 60

    _modificar(_cambio)
    return borrados


def limpiar_del_dia(*, borrar, ahora=None) -> int:
    """Lo de siempre con otro nombre: hoy es un barrido como cualquier otro."""
    return barrer(borrar=borrar, ahora=ahora)
