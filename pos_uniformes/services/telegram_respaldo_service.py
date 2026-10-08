"""Hacer el respaldo desde el celular, con el botón del propio aviso.

Daniel (2026-10-08): *"el bot solo me avisa que no hay respaldo, en vez de
darme un botón para hacerlo"*. Tenía razón: el aviso terminaba diciendo
«en la tienda: scripts\\respaldo_diario.bat», o sea «ve a la PC». Un aviso que
no se puede atender donde llega es media herramienta, y el respaldo es
justamente lo que no conviene dejar para cuando uno se acuerde.

El respaldo corre en un HILO aparte y no en la vuelta del bot. No es una
preferencia: Telegram da unos segundos para contestar el toque de un botón, y
un `pg_dump` tarda más que eso — el botón se quedaría girando y el bot sordo
mientras tanto. Así se contesta al instante «lo estoy haciendo» y el resultado
llega cuando de verdad terminó.

Y el resultado llega SIEMPRE, salga bien o mal. La tarea de siempre avisa solo
cuando falla, que para una tarea automática está bien; pero aquí alguien
apretó un botón y está esperando. El silencio no es éxito.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Prefijo de los botones de esta pantalla.
PREFIJO = "rs:"

#: Tope para el respaldo. Pasado esto algo está mal y vale más decirlo que
#: dejar el hilo colgado para siempre.
SEGUNDOS_TOPE = 900.0


def es_de_respaldo(dato: str) -> bool:
    return str(dato or "").startswith(PREFIJO)


def botones_del_aviso() -> str:
    """El teclado que acompaña al aviso de respaldo viejo."""
    from pos_uniformes.services import telegram_service

    return telegram_service.teclado(
        [[("💾 Hacer el respaldo ahora", f"{PREFIJO}ahora")]]
    )


def _correr_respaldo() -> tuple[bool, str]:
    """Corre el respaldo y devuelve (salió bien, qué decir)."""
    import subprocess
    import sys
    from pathlib import Path

    from pos_uniformes.services import respaldo_estado_service as est

    raiz = Path(__file__).resolve().parents[2]
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pos_uniformes.scripts.respaldo_diario",
             "--sin-avisar"],
            cwd=str(raiz), capture_output=True, text=True, timeout=SEGUNDOS_TOPE,
        )
    except subprocess.TimeoutExpired:
        return False, (
            f"🛑 El respaldo lleva más de {int(SEGUNDOS_TOPE / 60)} minutos y lo corté.\n"
            "Algo no está bien: revísalo en la tienda."
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"🛑 No se pudo arrancar el respaldo: {exc}"

    # Se cree el ESTADO y no el código de salida: lo que importa es que haya
    # un archivo del tamaño correcto, no que el proceso haya terminado en 0.
    try:
        estado = est.leer_estado()
    except Exception as exc:  # noqa: BLE001
        return False, f"🛑 El respaldo corrió pero no se pudo comprobar: {exc}"

    if estado.al_dia:
        return True, "✅ " + est.texto_resumen(estado).lstrip("✅⚠️ ")
    cola = (proc.stderr or proc.stdout or "").strip().splitlines()
    detalle = cola[-1] if cola else "sin detalle"
    return False, f"🛑 El respaldo no quedó.\n{detalle}"


def atender(dato: str, *, enviar) -> tuple[str, str, str]:
    """Un botón del aviso: (aviso corto, texto nuevo, botones nuevos).

    `enviar(texto)` es por donde sale el resultado cuando el hilo termina.
    """
    import threading

    accion = str(dato or "")[len(PREFIJO):]
    if accion != "ahora":
        return "No conozco ese botón", "", ""

    def _trabajo() -> None:
        try:
            _, texto = _correr_respaldo()
        except Exception as exc:  # noqa: BLE001 — nunca dejar al usuario sin respuesta
            logger.exception("Respaldo desde el celular")
            texto = f"🛑 El respaldo falló: {exc}"
        try:
            enviar(texto)
        except Exception:  # noqa: BLE001
            logger.exception("No se pudo avisar del respaldo")

    threading.Thread(target=_trabajo, name="respaldo-telegram", daemon=True).start()
    return (
        "Haciendo el respaldo…",
        "💾 Haciendo el respaldo de la base.\n\n"
        "Tarda un poco. Te aviso en cuanto termine, salga bien o mal.",
        "",
    )
