"""Servidor de impresión SIN ventana: la cola sale aunque el kiosko esté cerrado.

Hasta hoy el despachador vivía dentro de la ventana del kiosko: si esa PC tenía
el programa cerrado (o nada más la pantalla apagada y a alguien se le ocurría
cerrarlo), los tickets y las etiquetas se quedaban en la cola callados. Esto es
el mismo despachador, con los mismos handlers, corriendo solo.

Qt SÍ hace falta aunque no haya ventana: los tickets se imprimen con QPrinter y
QPainter, que necesitan una QApplication. Lo que no hace falta es MOSTRAR nada,
así que no se crea ninguna ventana y el proceso vive en la sesión del usuario
(por eso la tarea va con ONLOGON y correr_oculto.vbs, como el supervisor).

Uso:
    servidor_impresion.bat                 # se queda corriendo
    servidor_impresion.bat --drenar        # saca lo que haya y termina
    servidor_impresion.bat --forzar        # aunque esta PC sea "Estación"
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys

logger = logging.getLogger("servidor_impresion")

#: Candado: la tarea vigía lo lanza cada 5 min para que vuelva si se murió, y
#: esto hace que los lanzamientos de más no hagan nada. Dos despachadores no
#: imprimirían doble (el reclamo es atómico), pero sí serían dos procesos
#: compitiendo por la misma impresora y dos logs mezclados.
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


def _configurar_log(verboso: bool) -> None:
    from pos_uniformes.utils.config import satellite_data_dir

    nivel = logging.DEBUG if verboso else logging.INFO
    destino = satellite_data_dir() / "logs" / "servidor_impresion.log"
    destino.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(destino, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )


def _es_servidor_de_impresion() -> tuple[bool, str]:
    """(es_servidor, cómo se llama esta PC) según el menú admin del kiosko."""
    from pos_uniformes.services.print_routing_cache_service import MODO_LOCAL, load_print_routing

    modo, origen = load_print_routing()
    return modo == MODO_LOCAL, origen


def _correr(args, origen: str) -> int:
    """La parte que necesita Qt: event loop, handlers y despachador.

    Separada de `main` a propósito: la decisión de arrancar (soy servidor, soy
    el único) es donde está el riesgo y se prueba sin levantar Qt.
    """
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication

    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.trabajo_dispatcher import TrabajoDispatcher
    from pos_uniformes.ui.helpers.trabajo_print_handlers import build_handlers

    # QApplication sin una sola ventana: QPrinter/QPainter la necesitan.
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)   # no hay ventanas: no se debe salir solo

    despachador = TrabajoDispatcher(
        get_session,
        build_handlers(),
        schedule=QTimer.singleShot,
        on_event=lambda tid, estado, err: logger.info(
            "Trabajo %s → %s%s", tid, getattr(estado, "value", estado), f" ({err})" if err else ""
        ),
    )

    if args.drenar:
        cuantos = despachador.drain()
        logger.info("Saqué %s trabajo(s) de la cola.", cuantos)
        return 0

    logger.info("Servidor de impresión en pie como «%s». Esperando trabajos.", origen)

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Servidor de impresión sin ventana.")
    parser.add_argument("--drenar", action="store_true",
                        help="imprime lo que haya en la cola y termina (para probar).")
    parser.add_argument("--forzar", action="store_true",
                        help="corre aunque esta PC esté marcada como Estación.")
    parser.add_argument("--verboso", action="store_true", help="más detalle en el log.")
    args = parser.parse_args(argv)

    _configurar_log(args.verboso)

    es_servidor, origen = _es_servidor_de_impresion()
    if not es_servidor and not args.forzar:
        # Una Estación no tiene impresoras: si despachara, reclamaría trabajos
        # de los demás para mandarlos a una impresora que no existe y los
        # dejaría en ERROR. Mejor no arrancar y decir por qué.
        logger.warning(
            "Esta PC (%s) está marcada como «Estación», no como «Servidor de impresión». "
            "No arranco. Cámbialo en el menú admin del kiosko → «Rol de impresión de "
            "esta PC», o corre con --forzar si sabes lo que haces.", origen,
        )
        return 2

    # El candado va DESPUÉS de --drenar: drenar a mano es de una sola vez y
    # tiene que poder hacerse aunque el servicio esté corriendo.
    if not args.drenar and not tomar_candado():
        logger.info("Ya hay un servidor de impresión corriendo en esta PC. No arranco otro.")
        return 0

    return _correr(args, origen)


if __name__ == "__main__":
    raise SystemExit(main())
