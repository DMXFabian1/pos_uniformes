"""El Panel dice cómo va cada escuela, sin volver a decidirlo.

En Disponibilidad, que es donde se decide qué pedir, faltaba el contexto: si
esa escuela está contada, si se vendió sin contar. El chip lo trae del mismo
`escuela_estado_service` que usa el mapa, para que las dos ventanas no puedan
contradecirse.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pos_uniformes.scripts import generar_panel_uniformes as gen


class _Estado:
    """Lo mínimo que el chip le pide a un EstadoDeEscuela."""

    def __init__(self, salud, titular, ultimo="hace 3 días (Fanny)"):
        self.salud = salud
        self.titular = titular
        self.ultimo_conteo = type("U", (), {"texto": lambda self_: ultimo})()


class ChipDeSaludTest(unittest.TestCase):
    def test_pinta_el_color_del_semaforo(self):
        for salud, color in (("rojo", "#c0392b"), ("ambar", "#e08b1e"), ("verde", "#3d6b2f")):
            chip = gen.chip_de_salud(_Estado(salud, "lo que sea"))
            self.assertIn(color, chip, f"falta el color de {salud}")

    def test_dice_el_titular_y_cuando_se_conto(self):
        chip = gen.chip_de_salud(_Estado("rojo", "una talla en rojo: se vendió sin contar"))
        self.assertIn("una talla en rojo: se vendió sin contar", chip)
        self.assertIn("se contó hace 3 días (Fanny)", chip)

    def test_sin_estado_no_pinta_nada(self):
        # Una escuela que el servicio no conoce no debe ensuciar el encabezado.
        self.assertEqual(gen.chip_de_salud(None), "")

    def test_escapa_lo_que_viene_de_la_base(self):
        chip = gen.chip_de_salud(_Estado("verde", 'al día <b>"x"</b>'))
        self.assertNotIn("<b>", chip)


class ElPanelPreguntaNoDecideTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fuente = (
            Path(__file__).resolve().parent.parent / "scripts" / "generar_panel_uniformes.py"
        ).read_text(encoding="utf-8")

    def test_le_pide_el_estado_al_servicio(self):
        self.assertIn("escuela_estado_service.estados_de_todas", self.fuente)

    def test_no_arma_su_propio_semaforo(self):
        # El umbral de rojo/ámbar/verde vive en EstadoDeEscuela.salud. Si el
        # panel lo recalculara, podría contradecir al mapa.
        self.assertNotIn("if estado.en_rojo", self.fuente)
        self.assertIn("estado.salud", self.fuente)

    def test_disponibilidad_recibe_los_estados(self):
        self.assertIn("build_variants(catalog_rows, catalog_cols, multi_level_ids, estados)", self.fuente)


if __name__ == "__main__":
    unittest.main()
