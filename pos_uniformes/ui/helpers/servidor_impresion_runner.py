"""El servidor de impresión sin ventana: el despachador corriendo solo.

Vive aquí y no en el script porque hay DOS formas de arrancarlo y tienen que
ser el mismo programa:

- `scripts/servidor_impresion.py` — en una PC con el repo y su venv
  (la principal). Se instala como tarea de Windows.
- `PresupuestosSatelite.exe --servidor-impresion` — en un kiosko, donde NO hay
  Python: el lanzador solo baja el .exe empacado. Y en la tienda las
  impresoras de etiquetas cuelgan justo del kiosko (Daniel, 2026-10-05), así
  que sin esto el modo sin ventana no servía para nada ahí.

Qt hace falta aunque no haya ventana: los tickets se imprimen con QPrinter y
QPainter, que necesitan una QApplication. Lo que no hace falta es mostrar nada.
"""

from __future__ import annotations

import logging
import signal
import sys

logger = logging.getLogger(__name__)

#: Candado: el vigía lo relanza cada pocos minutos para que vuelva si se murió,
#: y esto hace que los lanzamientos de más no hagan nada. Dos despachadores no
#: imprimirían doble (el reclamo es atómico), pero serían dos procesos
#: peleando por la misma impresora y dos logs mezclados.
NOMBRE_MUTEX = "Global\\POSUniformesServidorImpresion"
_MUTEX = None


def tomar_candado() -> bool:
    """True si somos el único. Fuera de Windows no hay candado (solo dev)."""
    if not sys.platform.startswith("win"):
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.CreateMutexW(None, True, NOMBRE_MUTEX)
    if not handle:
        return True
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return False
    global _MUTEX
    _MUTEX = handle
    return True


def es_servidor_de_impresion() -> tuple[bool, str]:
    """(es_servidor, cómo se llama esta PC) según el menú admin del kiosko."""
    from pos_uniformes.services.print_routing_cache_service import MODO_LOCAL, load_print_routing

    modo, origen = load_print_routing()
    return modo == MODO_LOCAL, origen


def correr(app, *, drenar: bool = False, origen: str = "") -> int:
    """Despacha la cola con la QApplication que se le dé. Devuelve el código de salida.

    `app` se recibe hecha a propósito: dentro del .exe del satélite ya existe
    una, y crear otra tiraría Qt.
    """
    from PyQt6.QtCore import QTimer

    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.print_routing_cache_service import tipos_que_atiende
    from pos_uniformes.services.trabajo_dispatcher import TrabajoDispatcher
    from pos_uniformes.ui.helpers.trabajo_print_handlers import build_handlers

    app.setQuitOnLastWindowClosed(False)   # no hay ventanas: no se debe salir solo

    tipos = tipos_que_atiende()
    if tipos is not None:
        logger.info("Atiendo solo: %s", ", ".join(t.value for t in tipos))

    despachador = TrabajoDispatcher(
        get_session,
        build_handlers(),
        tipos=tipos,
        schedule=QTimer.singleShot,
        on_event=lambda tid, estado, err: logger.info(
            "Trabajo %s → %s%s", tid, getattr(estado, "value", estado), f" ({err})" if err else ""
        ),
    )

    if drenar:
        cuantos = despachador.drain()
        logger.info("Saqué %s trabajo(s) de la cola.", cuantos)
        return 0

    logger.info("Servidor de impresión en pie como «%s». Esperando trabajos.", origen or "esta PC")

    def _parar(*_args) -> None:
        logger.info("Me piden parar: termino lo que estoy imprimiendo y cierro.")
        despachador.stop()
        app.quit()

    for señal in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(señal, _parar)
        except (ValueError, OSError):   # en Windows no todas existen
            pass
    # Sin esto, un Ctrl+C no se atiende hasta que Qt vuelva de su event loop.
    despertador = QTimer()
    despertador.start(500)
    despertador.timeout.connect(lambda: None)

    despachador.start()
    return int(app.exec())
