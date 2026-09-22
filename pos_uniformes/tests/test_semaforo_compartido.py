"""Un solo semáforo para todas las ventanas.

Hasta el 2026-09-22 el kiosko tenía su propia regla de colores: rojo = nunca
contada, ámbar = empezada, gris = el resto. El mapa, el panel y el celular
usaban otra: rojo = se vendió sin contar. Resultado: el renglón más urgente
—una escuela con tallas en rojo— salía **gris** en el kiosko y **rojo** en el
mapa. Estos tests cuidan que no vuelvan a separarse.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pos_uniformes.services import conteo_mapa_service as cm


class SemaforoTest(unittest.TestCase):
    def test_lo_rojo_le_gana_a_todo(self):
        # Aunque esté contada al día: que el sistema crea que hay menos que
        # nada es peor que cualquier vigencia vencida.
        self.assertEqual(cm.semaforo(en_rojo=1, faltan=0), "rojo")
        self.assertEqual(cm.semaforo(en_rojo=1, faltan=99), "rojo")

    def test_si_le_falta_contarse_va_en_ambar(self):
        self.assertEqual(cm.semaforo(en_rojo=0, faltan=7), "ambar")

    def test_contada_y_al_dia_va_en_verde(self):
        self.assertEqual(cm.semaforo(en_rojo=0, faltan=0), "verde")


class NadieLoDecidePorSuCuentaTest(unittest.TestCase):
    """Las cuatro ventanas traducen el semáforo a su paleta, pero ninguna
    decide el umbral. Si alguna vuelve a decidirlo, esto truena."""

    def _fuente(self, *partes: str) -> str:
        return (Path(__file__).resolve().parent.parent.joinpath(*partes)).read_text(encoding="utf-8")

    def test_el_kiosko_pinta_por_salud_no_por_su_cuenta(self):
        fuente = self._fuente("ui", "quote_satellite_window.py")
        self.assertIn("_COLOR_SEMAFORO.get(fila.salud", fuente)
        self.assertNotIn(
            'detalle, color = "nunca se ha contado"',
            fuente,
            "el kiosko volvió a decidir su propio rojo",
        )

    def test_el_panel_pinta_por_salud(self):
        fuente = self._fuente("scripts", "generar_panel_uniformes.py")
        self.assertIn("estado.salud", fuente)

    def test_el_celular_pinta_por_salud(self):
        fuente = self._fuente("pwa", "index.html")
        self.assertIn("ESC_COLOR[e.salud]", fuente)

    def test_el_estado_de_escuela_no_repite_la_regla(self):
        fuente = self._fuente("services", "escuela_estado_service.py")
        self.assertIn("conteo_mapa_service.semaforo", fuente)
        self.assertNotIn('return "ambar"', fuente, "la regla se volvió a copiar")


if __name__ == "__main__":
    unittest.main()
