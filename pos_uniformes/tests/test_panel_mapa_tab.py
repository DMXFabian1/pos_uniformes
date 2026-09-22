"""La portada del Panel es el mapa de escuelas.

El mapa se genera aparte y ya le pregunta a `escuela_estado_service`; el panel
solo lo enseña. Se cuida que la pestaña exista, que el iframe no se cargue
hasta entrar (trae Leaflet de internet) y que si el mapa no está generado se
diga en vez de enseñar un hueco.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.scripts import generar_panel_uniformes as gen


class PestanaDelMapaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fuente = (
            Path(__file__).resolve().parent.parent / "scripts" / "generar_panel_uniformes.py"
        ).read_text(encoding="utf-8")

    def test_el_mapa_es_la_primera_pestana(self) -> None:
        pos_mapa = self.fuente.index("showTab('mapa')")
        pos_resumen = self.fuente.index("showTab('resumen')")
        self.assertLess(pos_mapa, pos_resumen, "el mapa va primero: es la portada")

    def test_la_pestana_arranca_activa(self) -> None:
        self.assertIn('<div id="mapa" class="tab-panel active">', self.fuente)
        self.assertIn('<div id="resumen" class="tab-panel">', self.fuente)

    def test_el_mapa_entra_en_el_orden_de_las_pestanas(self) -> None:
        # Si se olvida aquí, al cambiar de pestaña se subraya la equivocada.
        self.assertIn("const names = ['mapa','resumen','piezas','tarifarios','variantes','conteo']", self.fuente)

    def test_el_iframe_no_se_carga_hasta_entrar(self) -> None:
        self.assertIn("cargarMapaSiHace", self.fuente)
        self.assertIn('data-src="', self.fuente)


class ComoSeArmaTest(unittest.TestCase):
    def test_apunta_al_mapa_que_genera_el_otro_guion(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            html = gen.build_mapa()
        self.assertIn('data-src="../mapas_escuelas/mapa_escuelas_san_felipe.html"', html)
        self.assertNotIn(' src="', html, "vacío hasta que alguien entre a la pestaña")

    def test_explica_que_dice_cada_color(self) -> None:
        with patch.object(Path, "exists", return_value=True):
            html = gen.build_mapa()
        for palabra in ("rojo", "ámbar", "verde", "internet"):
            self.assertIn(palabra, html)

    def test_si_no_hay_mapa_lo_dice_en_vez_de_dejar_un_hueco(self) -> None:
        with patch.object(Path, "exists", return_value=False):
            html = gen.build_mapa()
        self.assertIn("Todavía no hay mapa", html)
        self.assertIn("generar_datos_escuelas.py", html)
        self.assertNotIn("<iframe", html)


if __name__ == "__main__":
    unittest.main()
