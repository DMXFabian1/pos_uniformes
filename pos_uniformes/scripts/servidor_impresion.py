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
import sys

logger = logging.getLogger("servidor_impresion")


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


def _correr(args, origen: str) -> int:
    """La parte que necesita Qt. El núcleo vive en el helper porque el .exe del
    satélite lo arranca igual con `--servidor-impresion`: en el kiosko no hay
    Python y es justo donde están las impresoras de etiquetas."""
    from PyQt6.QtWidgets import QApplication

    from pos_uniformes.ui.helpers.servidor_impresion_runner import correr

    # QApplication sin una sola ventana: QPrinter/QPainter la necesitan.
    app = QApplication(sys.argv[:1])
    return correr(app, drenar=args.drenar, origen=origen)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Servidor de impresión sin ventana.")
    parser.add_argument("--drenar", action="store_true",
                        help="imprime lo que haya en la cola y termina (para probar).")
    parser.add_argument("--forzar", action="store_true",
                        help="corre aunque esta PC esté marcada como Estación.")
    parser.add_argument("--verboso", action="store_true", help="más detalle en el log.")
    args = parser.parse_args(argv)

    _configurar_log(args.verboso)

    from pos_uniformes.ui.helpers.servidor_impresion_runner import (
        es_servidor_de_impresion,
        tomar_candado,
    )

    es_servidor, origen = es_servidor_de_impresion()
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
