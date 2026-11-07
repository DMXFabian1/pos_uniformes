"""El mapa de escuelas, al día (2026-11-07).

Daniel: «hagamos cambios en mapa» → «sí, hazlo completo». Los anillos se
quedaban con el día en que se generó el mapa (22/09): ahora el Panel escribe
`estados_pos.js` cada vez que se regenera y el mapa lo lee."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from pos_uniformes.services import escuela_estado_service as svc

MAPAS = Path(__file__).resolve().parents[2] / "mapas_escuelas"


class _Ultimo:
    def texto(self):
        return "hace 3 días (Fanny)"


class _Est:
    nombre = "Benito Juárez"
    titular = "al día · 4 tallas agotadas"
    en_rojo, faltan_de_contar, tallas, pct_al_dia, agotadas = 0, 0, 40, 100, 4
    piezas_en_tienda, vendido_piezas, pedido, faltas_sentidas = 120, 9, [1, 2], []
    ultimo_conteo = _Ultimo()
    salud = "verde"


class EstadosParaElMapaTests(unittest.TestCase):
    def test_para_mapa_trae_lo_que_pinta_el_mapa(self) -> None:
        d = svc.para_mapa(_Est())
        self.assertEqual(d["salud"], "verde")
        self.assertEqual(d["pedido"], 2)
        self.assertEqual(d["ultimo"], "hace 3 días (Fanny)")
        self.assertEqual(set(d), {"titular", "en_rojo", "faltan", "tallas", "pct_al_dia", "agotadas",
                                  "piezas", "vendido", "pedido", "faltas", "ultimo", "salud"})

    def test_escribe_estados_pos_js_con_su_fecha(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "estados_pos.js"
            n = svc.escribir_estados_para_mapa({7: _Est()}, ruta, ahora=datetime(2026, 11, 7, 10, 0))
            self.assertEqual(n, 1)
            texto = ruta.read_text(encoding="utf-8")
            self.assertTrue(texto.rstrip().endswith(";"))
            datos = json.loads(texto.split("window.ESTADOS_POS = ", 1)[1].rstrip().rstrip(";"))
            self.assertTrue(datos["generado"].startswith("2026-11-07T10:00:00"))
            self.assertEqual(datos["escuelas"]["Benito Juárez"]["salud"], "verde")


class PlantillaDelMapaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plantilla = (MAPAS / "plantilla_mapa.html").read_text(encoding="utf-8")
        self.mapa = (MAPAS / "mapa_escuelas_san_felipe.html").read_text(encoding="utf-8")

    def test_lee_el_estado_fresco_y_dice_de_cuando_es(self) -> None:
        for html in (self.plantilla, self.mapa):
            self.assertIn('<script src="estados_pos.js"></script>', html)
            self.assertIn("window.ESTADOS_POS", html)
            self.assertIn("Conteos actualizados", html)
            self.assertIn("sin actualizar", html)

    def test_burbujas_con_el_color_de_la_peor(self) -> None:
        self.assertIn("getAllChildMarkers", self.plantilla)
        self.assertIn("salud: comparteEstado(e) ? \"\" : saludDe(e)", self.plantilla)

    def test_leyenda_filtro_y_paleta(self) -> None:
        self.assertIn("CÓMO SE LEE", self.plantilla)
        self.assertIn('id="selSalud"', self.plantilla)
        self.assertIn("F.salud && saludDe(e) !== F.salud", self.plantilla)
        self.assertNotIn("#6b543c", self.plantilla)
        self.assertIn('Pre: "#8a6bbf"', self.plantilla)

    def test_el_mapa_generado_es_la_plantilla_con_datos(self) -> None:
        self.assertIn("const ESCUELAS = [", self.mapa)
        self.assertNotIn("/*__DATOS__*/", self.mapa)

    def test_estados_pos_js_no_va_en_git(self) -> None:
        gitignore = (MAPAS.parent / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("mapas_escuelas/estados_pos.js", gitignore)


class ElPanelLoEscribeTests(unittest.TestCase):
    def test_el_generador_del_panel_escribe_el_estado_del_mapa(self) -> None:
        fuente = (Path(__file__).resolve().parents[1] / "scripts" / "generar_panel_uniformes.py").read_text(encoding="utf-8")
        self.assertIn("escribir_estados_para_mapa(estados, carpeta_mapa / \"estados_pos.js\")", fuente)


if __name__ == "__main__":
    unittest.main()
