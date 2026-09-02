"""El arranque no debe pagar el import de QtWebEngineWidgets (~1.7s).

WebEngine se carga perezoso al abrir el Panel Uniformes; main.py solo deja
puesto AA_ShareOpenGLContexts antes de crear la QApplication para permitirlo.
"""

from __future__ import annotations

import os
import sys
import unittest

# Evita el probe de red de _detect_db_mode al importar main.
os.environ.setdefault("POS_UNIFORMES_DB_HOST", "localhost")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class LazyWebEngineTests(unittest.TestCase):
    def test_importing_main_does_not_load_webengine(self) -> None:
        import pos_uniformes.main  # noqa: F401

        self.assertNotIn(
            "PyQt6.QtWebEngineWidgets",
            sys.modules,
            "main.py volvio a importar QtWebEngineWidgets al arranque; "
            "debe cargarse perezoso en panel_uniformes_view.",
        )

    def test_main_sets_share_opengl_contexts_before_app(self) -> None:
        # El atributo es el que permite importar WebEngine despues de crear
        # la QApplication; sin el, el panel embebido truena al abrirse.
        import inspect

        import pos_uniformes.main as main_module

        source = inspect.getsource(main_module.main)
        attr_pos = source.find("AA_ShareOpenGLContexts")
        app_pos = source.find("QApplication(sys.argv)")
        self.assertNotEqual(attr_pos, -1, "falta AA_ShareOpenGLContexts en main()")
        self.assertNotEqual(app_pos, -1)
        self.assertLess(attr_pos, app_pos, "el atributo debe ponerse ANTES de crear QApplication")


if __name__ == "__main__":
    unittest.main()
