"""Botones estándar de Qt en español (Sí / No / Cancelar / Aceptar...).

Sin esto, los QMessageBox con StandardButton salen en inglés ("Yes",
"Cancel") aunque todo el texto de la app esté en español: Qt trae sus
propias traducciones pero hay que instalarlas al arrancar.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def instalar_espanol_qt(app) -> bool:
    """Instala la traducción qtbase_es en la QApplication. Devuelve True si
    cargó; si no (p.ej. bundle sin translations), la app sigue en inglés
    sin romper nada."""
    try:
        from PyQt6.QtCore import QLibraryInfo, QLocale, QTranslator

        translator = QTranslator(app)  # parent=app: no lo recoge el GC
        ruta = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if translator.load(QLocale(QLocale.Language.Spanish), "qtbase", "_", ruta):
            app.installTranslator(translator)
            return True
        logger.warning("No se encontró qtbase_es en %s", ruta)
    except Exception:  # noqa: BLE001 — un fallo aquí jamás debe tirar la app
        logger.exception("No se pudo instalar la traducción de Qt")
    return False
