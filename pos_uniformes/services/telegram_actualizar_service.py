"""Actualizar la tienda desde el celular: `/actualizar`, `/version`, `/volver`.

Antes había que ir a la PC principal y dar doble clic (Daniel, 2026-11-06).
El bot solo ARRANCA la actualización, en un proceso aparte: la actualización
reinicia al propio bot, así que no puede ser su hijo. Cómo terminó lo dice el
actualizador por Telegram (`scripts/actualizar.py`), salga bien o mal.

Las dos que cambian algo piden «si»: un toque de más en el menú no debe
actualizar la tienda a media venta.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

#: Una actualización tarda minutos (el build). Mientras, no se arranca otra.
MINUTOS_EN_CURSO = 40
_CANDADO = "actualizando.txt"


def _ruta_candado() -> Path:
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir() / "data" / _CANDADO


def en_curso(ahora: float | None = None) -> bool:
    try:
        desde = float(_ruta_candado().read_text(encoding="utf-8").strip())
    except Exception:  # noqa: BLE001 — sin candado o ilegible: no hay nada corriendo
        return False
    return ((ahora or time.time()) - desde) < MINUTOS_EN_CURSO * 60


def poner_candado(ahora: float | None = None) -> None:
    ruta = _ruta_candado()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(str(ahora or time.time()), encoding="utf-8")


def quitar_candado() -> None:
    try:
        _ruta_candado().unlink(missing_ok=True)
    except OSError:
        pass


def _arrancar_aparte() -> None:
    """Corre actualizar_desatendida.bat sin colgarlo de este proceso."""
    bat = Path(__file__).resolve().parents[1] / "scripts" / "actualizar_desatendida.bat"
    banderas = (
        getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )
    subprocess.Popen(  # noqa: S603 — ruta fija del repo
        ["cmd", "/c", str(bat)], cwd=str(bat.parent.parent), close_fds=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=banderas,
    )


def _estado() -> str:
    from pos_uniformes.scripts import actualizar as act

    return act.estado_en_texto(act.mundo_real())


def atender_actualizar(argumento: str, *, es_windows: bool | None = None,
                       arrancar=None, estado=None) -> str:
    """`/actualizar` enseña cómo está; `/actualizar si` la arranca."""
    es_windows = sys.platform.startswith("win") if es_windows is None else es_windows
    estado = estado or _estado
    try:
        como_esta = estado()
    except Exception as exc:  # noqa: BLE001
        como_esta = f"(no pude leer el estado: {exc})"
    pedido = " ".join((argumento or "").lower().split())
    if pedido.startswith("noche"):
        return atender_noche(pedido[len("noche"):].strip(), es_windows=es_windows)
    if pedido not in ("si", "sí"):
        return (
            f"{como_esta}\n\n"
            "Para traer lo nuevo y actualizar la tienda: /actualizar si\n"
            "Hace respaldo antes de tocar la base y, si algo falla, deja todo como estaba. "
            "Tarda unos minutos; te aviso cómo terminó.\n\n"
            "Para que se actualice sola cada noche a las 19:30: /actualizar noche "
            "(y /actualizar noche no para quitarlo)."
        )
    if not es_windows:
        return "Esto solo se puede hacer desde el bot de la PC principal de la tienda."
    if en_curso():
        return "Ya hay una actualización en curso. Te aviso en cuanto termine."
    try:
        poner_candado()
        (arrancar or _arrancar_aparte)()
    except Exception as exc:  # noqa: BLE001
        quitar_candado()
        logger.exception("No se pudo arrancar la actualización")
        return f"🛑 No se pudo arrancar la actualización: {exc}"
    return (
        "🔄 Actualizando la tienda: trae lo nuevo, hace el build, respalda, migra y publica "
        "a los kioskos.\n\nTarda unos minutos. Te aviso cómo terminó, salga bien o mal. "
        "(Yo mismo me reinicio al final.)"
    )


def atender_noche(argumento: str, *, es_windows: bool | None = None,
                  crear=None, borrar=None, existe=None) -> str:
    """`/actualizar noche` enciende la actualización de las 19:30; `noche no` la quita."""
    es_windows = sys.platform.startswith("win") if es_windows is None else es_windows
    if not es_windows:
        return "Esto solo se puede hacer desde el bot de la PC principal de la tienda."
    from pos_uniformes.scripts import postactualizacion as post

    crear = crear or post.crear_tarea
    borrar = borrar or post.borrar_tarea
    existe = existe or post.existe_tarea
    tarea = post.TAREA_ACTUALIZAR
    if (argumento or "").strip().lower() in ("no", "quitar", "apagar", "off"):
        if not existe(tarea.nombre):
            return "La actualización de noche ya estaba apagada."
        if borrar(tarea.nombre):
            return "Listo: la tienda ya no se actualiza sola. Sigue /actualizar si cuando quieras."
        return "🛑 No se pudo quitar la tarea «POS Actualizar». Revísalo en la tienda."
    if crear(tarea):
        return (
            "🌙 Listo: la tienda se actualiza sola todos los días a las 19:30, si hay algo nuevo. "
            "Hace respaldo antes de tocar la base y, si algo falla, deja todo como estaba. "
            "Te aviso cada vez que actualice o que falle; si no había nada nuevo, no molesto.\n\n"
            "La PC principal tiene que estar encendida a esa hora. Para quitarlo: /actualizar noche no"
        )
    return "🛑 No se pudo crear la tarea «POS Actualizar». Revísalo en la tienda."


def atender_version(*, estado=None) -> str:
    try:
        return (estado or _estado)()
    except Exception as exc:  # noqa: BLE001
        return f"No pude leer la versión: {exc}"


def atender_volver(argumento: str, *, volver=None) -> str:
    """`/volver si`: los kioskos regresan a la versión anterior."""
    if (argumento or "").strip().lower() not in ("si", "sí"):
        return (
            "Esto regresa los KIOSKOS a la versión anterior (la toman al abrir). La base no "
            "se regresa y la PC principal se queda como está. Sirve para cuando la versión "
            "nueva salió mala.\n\nPara hacerlo: /volver si"
        )
    if volver is None:
        from pos_uniformes.scripts import actualizar as act

        m = act.mundo_real()

        def volver() -> tuple[bool, str]:
            return act.volver_kioskos(
                carpeta=act.carpeta_updates(), commit_actual=m.commit_actual(),
                escribir_marca=m.escribir_marca, avisar=lambda _t: None, decir=lambda _t: None,
            )
    try:
        _ok, texto = volver()
    except Exception as exc:  # noqa: BLE001
        logger.exception("No se pudo volver a la versión anterior")
        return f"🛑 No se pudo volver a la versión anterior: {exc}"
    return texto
