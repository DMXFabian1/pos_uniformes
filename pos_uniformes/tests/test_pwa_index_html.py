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
