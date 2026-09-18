"""Sanidad del HTML de la PWA: ids únicos (dos `cont-prendas` dejaron la hoja
de captura en blanco el 18/09) y JS que parsea."""

from __future__ import annotations

import re
import unittest
from collections import Counter
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "pwa" / "index.html"


class PwaIndexTests(unittest.TestCase):
    def test_ningun_id_repetido(self) -> None:
        # Solo el HTML estático: los ids dentro de <script> son plantillas que
        # se pintan una a la vez (p.ej. `bod-cajas` en dos pantallas de bodega).
        estatico = re.sub(r"<script>[\s\S]*?</script>", "", HTML.read_text(encoding="utf-8"))
        ids = re.findall(r'\sid="([^"]+)"', estatico)
        repetidos = [i for i, n in Counter(ids).items() if n > 1]
        self.assertEqual(repetidos, [], f"ids repetidos en pwa/index.html: {repetidos}")

    def test_la_hoja_y_el_selector_de_basicos_tienen_su_propio_div(self) -> None:
        s = HTML.read_text(encoding="utf-8")
        self.assertIn('id="cont-prenda-sel"', s)
        self.assertIn('id="cont-prendas"', s)
        self.assertIn('$("cont-prendas").innerHTML = hoja.prendas', s)


class NavegacionTests(unittest.TestCase):
    """La barra superior y la pila de pantallas (2026-09-18)."""

    def _js(self) -> str:
        return "\n".join(re.findall(r"<script>([\s\S]*?)</script>", HTML.read_text(encoding="utf-8")))

    def test_la_barra_tiene_atras_actualizar_y_menu(self) -> None:
        s = HTML.read_text(encoding="utf-8")
        for i in ('id="topbar"', 'id="tb-atras"', 'id="tb-refresh"', 'id="tb-menu"', 'id="tb-titulo"'):
            self.assertIn(i, s)

    def test_todas_las_pantallas_y_acciones_envueltas_existen(self) -> None:
        js = self._js()
        definidas = set(re.findall(r"(?:async )?function (\w+)\(", js))
        for lista in ("NAV_PANTALLAS", "NAV_ACCIONES"):
            m = re.search(lista + r" = \[([\s\S]*?)\];", js)
            nombres = re.findall(r'"(\w+)"', m.group(1))
            faltan = [n for n in nombres if n not in definidas]
            self.assertEqual(faltan, [], f"{lista}: funciones que no existen: {faltan}")

    def test_las_que_guardan_no_se_apilan_ni_se_repiten(self) -> None:
        js = self._js()
        pantallas = set(re.findall(r'"(\w+)"', re.search(r"NAV_PANTALLAS = \[([\s\S]*?)\];", js).group(1)))
        acciones = set(re.findall(r'"(\w+)"', re.search(r"NAV_ACCIONES = \[([\s\S]*?)\];", js).group(1)))
        self.assertEqual(pantallas & acciones, set())
        # todo lo que llama a contPost/fetch POST y pinta después es acción, no pantalla
        for n in ("encConfirmarPago", "bodLlegoGuardar", "duenoGuardarCorte", "encMarcar"):
            self.assertIn(n, acciones)
