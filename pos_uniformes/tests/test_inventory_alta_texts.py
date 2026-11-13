from __future__ import annotations

import unittest

from pos_uniformes.ui.helpers.inventory_alta_texts import (
    TITULO_ERROR_LOTE,
    mensaje_talla_creada,
    mensaje_tallas_creadas,
)


class MensajeTallasCreadasTests(unittest.TestCase):
    def test_lote_en_palabras_de_la_tienda(self) -> None:
        texto = mensaje_tallas_creadas("Pants 2pz Colegio Muestra", 6, ["SKU000001", "SKU000006"])
        self.assertTrue(texto.startswith("Se agregaron 6 tallas a «Pants 2pz Colegio Muestra»."))
        self.assertIn("Códigos: SKU000001, SKU000006.", texto)
        for jerga in ("presentaciones", "SKU creados", "Rango", "->", "Incidencias"):
            self.assertNotIn(jerga, texto)

    def test_una_sola(self) -> None:
        self.assertEqual(mensaje_tallas_creadas("Gorra", 1), "Se agregó 1 talla a «Gorra».")

    def test_muchos_codigos_y_errores_se_recortan(self) -> None:
        codigos = [f"SKU{i:06d}" for i in range(10)]
        errores = [f"Talla {i}: ya existe" for i in range(6)]
        texto = mensaje_tallas_creadas("Pants", 4, codigos, errores)
        self.assertIn("SKU000007 y 2 más.", texto)
        self.assertIn("No se pudieron crear:\nTalla 0: ya existe", texto)
        self.assertIn("… y 2 más.", texto)

    def test_titulo_de_error(self) -> None:
        self.assertNotIn("Presentaciones", TITULO_ERROR_LOTE)


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
