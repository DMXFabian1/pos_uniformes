from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.inventory_alta_texts import mensaje_talla_creada


class MensajeTallaCreadaTests(unittest.TestCase):
    def test_nombra_talla_y_prenda(self) -> None:
        fila = {"talla": "10", "color": "Azul marino", "producto_nombre_base": "Pants 2pz Colegio Muestra"}
        self.assertEqual(
            mensaje_talla_creada(fila, "sku000004"),
            "Talla 10 (Azul marino) de «Pants 2pz Colegio Muestra» lista.",
        )

    def test_sin_fila_cae_al_codigo(self) -> None:
        self.assertEqual(mensaje_talla_creada(None, "sku000004"), "Talla nueva lista (código SKU000004).")


if __name__ == "__main__":
    unittest.main()
