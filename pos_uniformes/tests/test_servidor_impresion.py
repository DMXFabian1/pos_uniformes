"""Servidor de impresión sin ventana.

Lo que se cuida: que una Estación NO despache (reclamaría trabajos de las
demás para mandarlos a una impresora que no existe), que no corran dos a la
vez, y que `--drenar` se pueda hacer a mano aunque el servicio esté arriba.

No se levanta Qt aquí: lo que se prueba es la decisión de arrancar, que es
donde está el riesgo. La impresión en sí ya tiene sus tests en los handlers.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from pos_uniformes.scripts import servidor_impresion as srv
from pos_uniformes.services.print_routing_cache_service import MODO_LOCAL, MODO_SATELITE
from pos_uniformes.ui.helpers import servidor_impresion_runner as runner


class NoArrancarEnUnaEstacionTests(unittest.TestCase):
    def test_la_estacion_no_despacha_y_lo_dice(self) -> None:
        with patch.object(srv, "_configurar_log"), \
             patch("pos_uniformes.services.print_routing_cache_service.load_print_routing",
                   return_value=(MODO_SATELITE, "caja 2")), \
             patch.object(runner, "tomar_candado") as candado:
            self.assertEqual(srv.main([]), 2)
        candado.assert_not_called()   # ni siquiera llega a tomar el candado

    def test_con_forzar_arranca_aunque_sea_estacion(self) -> None:
        """Escotilla para una PC a la que se le acaban de poner las impresoras."""
        with patch.object(srv, "_configurar_log"), \
             patch("pos_uniformes.services.print_routing_cache_service.load_print_routing",
                   return_value=(MODO_SATELITE, "caja 2")), \
             patch.object(runner, "tomar_candado", return_value=True), \
             patch.object(srv, "_correr", return_value=0) as correr:
            self.assertEqual(srv.main(["--forzar"]), 0)
        correr.assert_called_once()


class UnoSoloALaVezTests(unittest.TestCase):
    def test_si_ya_hay_uno_el_segundo_se_va_en_paz(self) -> None:
        """La tarea vigía lo relanza cada 5 min: los de más no deben hacer nada."""
        with patch.object(srv, "_configurar_log"), \
             patch("pos_uniformes.services.print_routing_cache_service.load_print_routing",
                   return_value=(MODO_LOCAL, "principal")), \
             patch.object(runner, "tomar_candado", return_value=False), \
             patch.object(srv, "_correr") as correr:
            self.assertEqual(srv.main([]), 0)
        correr.assert_not_called()

    def test_drenar_a_mano_no_pide_el_candado(self) -> None:
        """Sacar la cola a mano tiene que poder hacerse con el servicio arriba."""
        with patch.object(srv, "_configurar_log"), \
             patch("pos_uniformes.services.print_routing_cache_service.load_print_routing",
                   return_value=(MODO_LOCAL, "principal")), \
             patch.object(runner, "tomar_candado") as candado, \
             patch.object(srv, "_correr", return_value=0):
            self.assertEqual(srv.main(["--drenar"]), 0)
        candado.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class DesdeElExeDelSateliteTests(unittest.TestCase):
    """En el kiosko no hay Python —el lanzador solo baja el .exe— y ahí es donde
    están las impresoras de etiquetas. Por eso el mismo ejecutable tiene que
    poder arrancar como servidor de impresión (Daniel, 2026-10-05)."""

    def _main(self, argv, **kw):
        import sys as _sys

        from pos_uniformes import presupuestos_satelite_main as sat

        viejo = _sys.argv
        _sys.argv = argv
        try:
            with patch.object(sat, "install_satellite_excepthook"), \
                 patch.object(sat, "QApplication", return_value=object()), \
                 patch.object(sat, "bootstrap_schema"), \
                 patch("pos_uniformes.ui.helpers.servidor_impresion_runner.correr",
                       return_value=0) as correr, \
                 patch("pos_uniformes.ui.helpers.servidor_impresion_runner.tomar_candado",
                       return_value=kw.get("candado", True)), \
                 patch("pos_uniformes.services.print_routing_cache_service.load_print_routing",
                       return_value=(kw.get("modo", MODO_LOCAL), "kiosko")):
                return sat.main(), correr
        finally:
            _sys.argv = viejo

    def test_la_bandera_despacha_sin_abrir_el_kiosko(self) -> None:
        salida, correr = self._main(["app.exe", "--servidor-impresion"])
        self.assertEqual(salida, 0)
        correr.assert_called_once()

    def test_sin_la_bandera_no_se_mete_en_el_arranque_normal(self) -> None:
        """El kiosko de siempre tiene que seguir abriendo igual."""
        import sys as _sys

        from pos_uniformes import presupuestos_satelite_main as sat

        fuente = __import__("inspect").getsource(sat.main)
        self.assertIn('if "--servidor-impresion" in sys.argv:', fuente)
        del _sys

    def test_una_estacion_tampoco_despacha_desde_el_exe(self) -> None:
        salida, correr = self._main(["app.exe", "--servidor-impresion"], modo=MODO_SATELITE)
        self.assertEqual(salida, 2)
        correr.assert_not_called()

    def test_el_segundo_proceso_se_va_en_paz(self) -> None:
        salida, correr = self._main(["app.exe", "--servidor-impresion"], candado=False)
        self.assertEqual(salida, 0)
        correr.assert_not_called()
