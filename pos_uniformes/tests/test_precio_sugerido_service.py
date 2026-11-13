"""Precio sugerido por talla: de dónde sale, 5/9 solo sugerido y nunca bajar
(tanda 2 del alta, 2026-11-13). Puro: sin base."""

from __future__ import annotations

import unittest
from collections import Counter
from decimal import Decimal

from pos_uniformes.services import precio_sugerido_service as ps

D = Decimal


class RedondeoTests(unittest.TestCase):
    def test_hacia_arriba_al_5_o_al_9(self) -> None:
        casos = {280: 285, 281: 285, 285: 285, 286: 289, 288: 289, 289: 289, 290: 295, 52: 55, 70: 75,
                 "285.40": 289, "199": 199}
        for entrada, salida in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(ps.redondeo_5_9(entrada), D(salida))

    def test_nunca_redondea_hacia_abajo(self) -> None:
        for n in range(1, 2000):
            self.assertGreaterEqual(ps.redondeo_5_9(n), D(n))

    def test_vacio_o_cero(self) -> None:
        self.assertIsNone(ps.redondeo_5_9(None))
        self.assertIsNone(ps.redondeo_5_9(0))
        self.assertIsNone(ps.redondeo_5_9("abc"))

    def test_termina_en_5_o_9(self) -> None:
        self.assertTrue(ps.termina_en_5_o_9(245))
        self.assertTrue(ps.termina_en_5_o_9("289.00"))
        self.assertFalse(ps.termina_en_5_o_9(70))
        self.assertFalse(ps.termina_en_5_o_9("245.50"))


class NoBajarTests(unittest.TestCase):
    def test_max(self) -> None:
        self.assertEqual(ps.no_bajar(300, 280), D(300))
        self.assertEqual(ps.no_bajar(280, 300), D(300))
        self.assertEqual(ps.no_bajar(None, 280), D(280))
        self.assertEqual(ps.no_bajar(280, None), D(280))


class ModaTests(unittest.TestCase):
    def test_a_empate_la_mas_alta(self) -> None:
        self.assertEqual(ps.moda(Counter({D(245): 2, D(255): 2, D(235): 1})), D(255))
        self.assertIsNone(ps.moda(Counter()))


class SugerirTests(unittest.TestCase):
    conteos = {
        "4": Counter({D(245): 14, D(235): 1}),
        "6": Counter({D(245): 14}),
        "GD": Counter({D(295): 12}),
        "Unitalla": Counter({D(70): 9}),
    }

    def test_como_las_demas(self) -> None:
        filas = ps.sugerir_desde(["4", "6"], self.conteos)
        self.assertEqual([(f.precio, f.origen) for f in filas], [(D(245), "como las demás")] * 2)
        self.assertEqual(filas[0].prendas_con_moda, 14)
        self.assertEqual(filas[0].aviso, "")
        self.assertIsNone(filas[0].sugerencia_5_9)

    def test_del_modelo_si_la_base_no_tiene_la_talla(self) -> None:
        filas = ps.sugerir_desde(["GD", "EXG"], self.conteos, modelo={"GD": 295, "EXG": 305})
        self.assertEqual(
            [(f.precio, f.origen) for f in filas], [(D(295), "como las demás"), (D(305), "del modelo")]
        )

    def test_preferir_el_modelo_al_copiar_una_escuela(self) -> None:
        filas = ps.sugerir_desde(["4"], self.conteos, modelo={"4": 255}, preferir=ps.PREFERIR_MODELO)
        self.assertEqual((filas[0].precio, filas[0].origen), (D(255), "del modelo"))

    def test_a_mano_gana_y_avisa_si_queda_mas_bajo(self) -> None:
        f = ps.sugerir_desde(["4"], self.conteos, a_mano={"4": "$230"})[0]
        self.assertEqual((f.precio, f.origen), (D(230), "a mano"))
        self.assertEqual(f.aviso, "Queda más bajo que en las demás escuelas ($245).")
        self.assertEqual(f.texto_sugerencia, "¿$235?")

    def test_5_9_solo_se_sugiere(self) -> None:
        f = ps.sugerir_desde(["6"], self.conteos, a_mano={"6": 288})[0]
        self.assertEqual(f.precio, D(288))  # no se cambia solo
        self.assertEqual(f.sugerencia_5_9, D(289))
        self.assertEqual(f.texto_sugerencia, "¿$289?")

    def test_excepciones_validas_no_se_discuten(self) -> None:
        # Corbata a $70 en todas: es el precio de las demás, no se sugiere $75.
        f = ps.sugerir_desde(["Uni"], self.conteos)[0]
        self.assertEqual((f.talla, f.precio, f.origen), ("Unitalla", D(70), "como las demás"))
        self.assertIsNone(f.sugerencia_5_9)

    def test_sin_precio(self) -> None:
        f = ps.sugerir_desde(["EXG"], self.conteos)[0]
        self.assertTrue(f.falta)
        self.assertEqual(f.origen, "falta precio")
        self.assertEqual(f.aviso, "Falta el precio.")

    def test_cero_no_pasa(self) -> None:
        f = ps.sugerir_desde(["4"], self.conteos, a_mano={"4": 0})[0]
        self.assertTrue(f.falta)
        self.assertEqual(f.aviso, "El precio no puede quedar en $0.")
        with self.assertRaisesRegex(ValueError, r"\$0"):
            ps.validar(0)
        with self.assertRaisesRegex(ValueError, "Falta"):
            ps.validar("")
        self.assertEqual(ps.validar("245"), D("245"))


class OrigenDeTests(unittest.TestCase):
    def test_se_recalcula_al_editar(self) -> None:
        from pos_uniformes.services.precio_sugerido_service import origen_de

        D = Decimal
        self.assertEqual(origen_de(D(295), D(295), D(290), "a mano"), "como las demás")
        self.assertEqual(origen_de(D(290), D(295), D(290), "como las demás"), "del modelo")
        self.assertEqual(origen_de(D(299), D(295), D(290), "como las demás"), "a mano")
        self.assertEqual(origen_de(None, D(295), None, "a mano"), "falta precio")
        # Sin moda ni modelo para comparar, se respeta el que traía.
        self.assertEqual(origen_de(D(70), None, None, "a mano"), "a mano")


if __name__ == "__main__":
    unittest.main()
