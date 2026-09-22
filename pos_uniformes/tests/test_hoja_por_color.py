"""Una hoja por color.

La Licra sale en azul marino, blanca y negra, y la hoja las juntaba todas:
salían `CH CH CH · MD MD MD` sin decir cuál era cuál (Daniel, 2026-09-22, con
la hoja impresa en la mano). Los montones del estante están separados por
color, así que la hoja también.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from pos_uniformes.services.conteo_service import partir_grupos_por_color


@dataclass
class _V:
    talla: str
    color: str = ""


def _grupo(nombre="Licra", tipo="", variantes=()):
    return {"producto_nombre": nombre, "tipo_pieza": tipo, "virtual": False,
            "orden_uniforme": None, "variantes": list(variantes)}


class PartirPorColorTest(unittest.TestCase):
    def test_tres_colores_dan_tres_hojas(self):
        g = _grupo(variantes=[
            _V("CH", "Azul Marino"), _V("MD", "Azul Marino"),
            _V("CH", "Blanca"), _V("MD", "Blanca"),
            _V("CH", "Negro"), _V("MD", "Negro"),
        ])
        partidos = partir_grupos_por_color([g])
        self.assertEqual([p["color"] for p in partidos], ["Azul Marino", "Blanca", "Negro"])
        for p in partidos:
            self.assertEqual([v.talla for v in p["variantes"]], ["CH", "MD"])

    def test_un_solo_color_se_queda_igual(self):
        g = _grupo(variantes=[_V("CH", "Rojo"), _V("MD", "Rojo")])
        self.assertEqual(partir_grupos_por_color([g]), [g], "no hay nada que partir")

    def test_sin_color_se_queda_igual(self):
        g = _grupo(variantes=[_V("CH"), _V("MD", "Sin color"), _V("GD", "Único")])
        self.assertEqual(partir_grupos_por_color([g]), [g])

    def test_las_que_no_dicen_color_no_se_pierden(self):
        # Van en su propia hoja al final, en vez de desaparecer.
        g = _grupo(variantes=[_V("CH", "Rojo"), _V("MD", "Azul"), _V("GD", "")])
        partidos = partir_grupos_por_color([g])
        self.assertEqual([p["color"] for p in partidos], ["Azul", "Rojo", ""])
        self.assertEqual([v.talla for v in partidos[-1]["variantes"]], ["GD"])
        self.assertEqual(
            sum(len(p["variantes"]) for p in partidos), 3, "no se pierde ninguna talla"
        )

    def test_no_saca_hojas_vacias(self):
        g = _grupo(variantes=[])
        self.assertEqual(partir_grupos_por_color([g]), [g])

    def test_cada_hoja_conserva_lo_demas_del_grupo(self):
        g = _grupo(nombre="Licra", tipo="Licra", variantes=[_V("CH", "Rojo"), _V("CH", "Azul")])
        for p in partir_grupos_por_color([g]):
            self.assertEqual(p["producto_nombre"], "Licra")
            self.assertEqual(p["tipo_pieza"], "Licra")
            self.assertFalse(p["virtual"])


class LasDosHojasLaUsanTest(unittest.TestCase):
    """Tira y carta tienen que partir igual: es la misma prenda contada."""

    def _fuente(self, *partes: str) -> str:
        from pathlib import Path

        return Path(__file__).resolve().parent.parent.joinpath(*partes).read_text(encoding="utf-8")

    def test_la_tira_parte_por_color(self):
        fuente = self._fuente("services", "conteo_sheet_service.py")
        self.assertEqual(fuente.count("partir_grupos_por_color(grupos)"), 2, "escuela y básicos")

    def test_la_carta_parte_por_color(self):
        fuente = self._fuente("services", "conteo_hoja_carta_service.py")
        self.assertIn("partir_grupos_por_color(grupos)", fuente)


if __name__ == "__main__":
    unittest.main()
