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


class NoArrancarEnUnaEstacionTests(unittest.TestCase):
    def test_la_estacion_no_despacha_y_lo_dice(self) -> None:
        with patch.object(srv, "_configurar_log"), \
             patch("pos_uniformes.services.print_routing_cache_service.load_print_routing",
                   return_value=(MODO_SATELITE, "caja 2")), \
             patch.object(srv, "tomar_candado") as candado:
            self.assertEqual(srv.main([]), 2)
        candado.assert_not_called()   # ni siquiera llega a tomar el candado

    def test_con_forzar_arranca_aunque_sea_estacion(self) -> None:
        """Escotilla para una PC a la que se le acaban de poner las impresoras."""
        with patch.object(srv, "_configurar_log"), \
             patch("pos_uniformes.services.print_routing_cache_service.load_print_routing",
                   return_value=(MODO_SATELITE, "caja 2")), \
             patch.object(srv, "tomar_candado", return_value=True), \
             patch.object(srv, "_correr", return_value=0) as correr:
            self.assertEqual(srv.main(["--forzar"]), 0)
        correr.assert_called_once()


class UnoSoloALaVezTests(unittest.TestCase):
    def test_si_ya_hay_uno_el_segundo_se_va_en_paz(self) -> None:
        """La tarea vigía lo relanza cada 5 min: los de más no deben hacer nada."""
        with patch.object(srv, "_configurar_log"), \
             patch("pos_uniformes.services.print_routing_cache_service.load_print_routing",
                   return_value=(MODO_LOCAL, "principal")), \
             patch.object(srv, "tomar_candado", return_value=False), \
             patch.object(srv, "_correr") as correr:
            self.assertEqual(srv.main([]), 0)
        correr.assert_not_called()

    def test_drenar_a_mano_no_pide_el_candado(self) -> None:
        """Sacar la cola a mano tiene que poder hacerse con el servicio arriba."""
        with patch.object(srv, "_configurar_log"), \
             patch("pos_uniformes.services.print_routing_cache_service.load_print_routing",
                   return_value=(MODO_LOCAL, "principal")), \
             patch.object(srv, "tomar_candado") as candado, \
             patch.object(srv, "_correr", return_value=0):
            self.assertEqual(srv.main(["--drenar"]), 0)
        candado.assert_not_called()


if __name__ == "__main__":
    unittest.main()
