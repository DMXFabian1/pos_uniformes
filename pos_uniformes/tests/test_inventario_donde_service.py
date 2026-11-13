from __future__ import annotations

import unittest

from pos_uniformes.services.inventario_donde_service import (
    repartir,
    texto_donde,
    texto_donde_completo,
)


class TextoDondeTests(unittest.TestCase):
    def test_bodega_y_piso(self) -> None:
        self.assertEqual(texto_donde(10, bodega=6, piso=2), "Bodega 6 · Piso 2")

    def test_solo_bodega_o_solo_piso(self) -> None:
        self.assertEqual(texto_donde(10, bodega=6), "Bodega 6")
        self.assertEqual(texto_donde(3, piso=3), "Piso 3")

    def test_todo_en_tienda(self) -> None:
        self.assertEqual(texto_donde(5), "Tienda")

    def test_sin_existencia_es_raya(self) -> None:
        self.assertEqual(texto_donde(0), "—")
        self.assertEqual(texto_donde(-2), "—")

    def test_negativo_pero_con_cajas_dice_las_cajas_con_marca_de_descuadre(self) -> None:
        self.assertEqual(texto_donde(-1, bodega=2), "Bodega 2 ⚠")

    def test_mas_en_cajas_que_el_total_lleva_marca(self) -> None:
        self.assertEqual(texto_donde(2, bodega=6), "Bodega 6 ⚠")
        self.assertEqual(texto_donde(8, bodega=6, piso=2), "Bodega 6 · Piso 2")

    def test_conjunto_es_raya(self) -> None:
        self.assertEqual(texto_donde(4, bodega=1, conjunto=True), "—")

    def test_nulos_cuentan_como_cero(self) -> None:
        self.assertEqual(texto_donde(None, None, None), "—")  # type: ignore[arg-type]


class TextoDondeCompletoTests(unittest.TestCase):
    def test_reparto_completo(self) -> None:
        self.assertEqual(texto_donde_completo(12, bodega=6, piso=2), "Tienda 4 · Bodega 6 · Piso 2")

    def test_todo_en_tienda(self) -> None:
        self.assertEqual(texto_donde_completo(5), "Tienda 5")

    def test_nada(self) -> None:
        self.assertEqual(texto_donde_completo(0), "No hay")

    def test_avisa_descuadre(self) -> None:
        self.assertEqual(
            texto_donde_completo(3, bodega=5),
            "Bodega 5. Ojo: en cajas hay 5 y el total dice 3",
        )

    def test_conjunto(self) -> None:
        self.assertIn("piezas", texto_donde_completo(2, conjunto=True))


class RepartirTests(unittest.TestCase):
    def test_tienda_es_el_resto(self) -> None:
        self.assertEqual(repartir(10, 6, 2).tienda, 2)

    def test_tienda_nunca_negativa(self) -> None:
        reparto = repartir(-3, 1, 0)
        self.assertEqual((reparto.tienda, reparto.descuadre), (0, 1))


if __name__ == "__main__":
    unittest.main()
