"""Las notas de los diálogos tienen que LEERSE.

El 2026-10-07 el resumen de impresoras salió en crema sobre crema en la PC de
la tienda: se veía el emoji y nada más. La causa es que reusé `satStatus`, que
está pintado para la barra OSCURA del kiosko (`color: #f9f4ea`), en un diálogo
de fondo claro. Mis capturas no lo detectaron porque las hice sin aplicar la
hoja de estilos de la app.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _color_de(regla: str, hoja: str) -> str | None:
    bloque = re.search(re.escape(regla) + r"\s*\{(.*?)\}", hoja, re.S)
    if bloque is None:
        return None
    color = re.search(r"(?<!-)\bcolor:\s*([^;]+);", bloque.group(1))
    return color.group(1).strip() if color else None


class LaHojaDeEstilosTests(unittest.TestCase):
    def setUp(self) -> None:
        from pos_uniformes.ui.styles.satellite_styles import build_satellite_stylesheet

        self.hoja = build_satellite_stylesheet()

    def test_satStatus_sigue_siendo_para_fondo_oscuro(self) -> None:
        """Si esto cambia, la nota de abajo deja de tener sentido."""
        self.assertEqual(_color_de("QLabel#satStatus", self.hoja), "#f9f4ea")

    def test_hay_una_nota_para_fondo_claro(self) -> None:
        self.assertEqual(_color_de("QLabel#satNota", self.hoja), "#2c2a27")


class ElDialogoNoUsaElEstiloOscuroTests(unittest.TestCase):
    def test_el_menu_admin_no_pinta_notas_en_crema(self) -> None:
        """El diálogo es de fondo claro: ahí `satStatus` es texto invisible."""
        fuente = (RAIZ / "ui" / "dialogs" / "satellite_admin_dialog.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('setObjectName("satStatus")', fuente)
        self.assertIn('setObjectName("satNota")', fuente)

    def test_la_caja_de_impresoras_trae_su_color_escrito(self) -> None:
        """La usan DOS apps con hojas distintas (kiosko y POS principal), así
        que no puede depender de que el tema de turno defina el objectName."""
        fuente = (RAIZ / "ui" / "helpers" / "impresoras_de_la_pc_widget.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("color: #2c2a27", fuente)
        self.assertNotIn("satStatus", fuente)


# NO hay prueba de pixeles aquí, y es a propósito. Lo intenté dos veces:
# fotografiar la etiqueta sola (falla: se graba sobre vacío y ahí el crema sí
# contrasta) y fotografiar la caja midiendo el rango de claridad en la zona del
# resumen (falla también: el emoji y el borde de la caja aportan pixeles
# oscuros, así que el rango sale amplio aunque el texto sea invisible).
#
# Las dos versiones PASABAN con el bug puesto. Un test que no distingue el
# error del acierto es peor que no tenerlo, porque da confianza falsa. Lo que
# sí distingue es lo de arriba: que el diálogo no use el estilo pintado para
# fondo oscuro. Lo que de verdad cierra esto es mirar la captura con la hoja de
# estilos aplicada, que es como se encontró.


if __name__ == "__main__":
    unittest.main()
