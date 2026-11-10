"""T-A2 (E1-A): normalización, clasificación y enmascarado del teléfono."""

from __future__ import annotations

import unittest

from pos_uniformes.services.clientes.telefono import (
    INVALIDO,
    VACIO,
    VALIDO,
    clasificar_telefono,
    enmascarar_telefono,
    normalizar_telefono,
)


class NormalizarTelefonoTests(unittest.TestCase):
    CASOS = (
        # (telefono, normalizado esperado, clase esperada)
        (None, None, VACIO),
        ("", None, VACIO),
        ("   ", None, VACIO),
        ("sin telefono", None, VACIO),
        ("6671234567", "6671234567", VALIDO),
        (" 667 123 4567 ", "6671234567", VALIDO),
        ("667-123-45-67", "6671234567", VALIDO),
        ("(667) 123.4567", "6671234567", VALIDO),
        ("+52 667 123 4567", "6671234567", VALIDO),
        ("526671234567", "6671234567", VALIDO),
        ("+52 1 667 123 4567", "6671234567", VALIDO),
        ("5216671234567", "6671234567", VALIDO),
        ("667123456", None, INVALIDO),  # 9 dígitos
        ("66712345678", None, INVALIDO),  # 11 dígitos
        ("12345678901234", None, INVALIDO),  # 14 dígitos
        ("536671234567", None, INVALIDO),  # 12 dígitos sin lada 52
        ("5226671234567", None, INVALIDO),  # 13 dígitos sin 521
        ("0000000000", None, INVALIDO),
        ("111-111-1111", None, INVALIDO),
        ("520000000000", None, INVALIDO),  # lada válida, número repetido
        ("abc6671234567xyz", "6671234567", VALIDO),  # letras se ignoran
        ("tel 667", None, INVALIDO),
    )

    def test_casos_k6(self) -> None:
        for telefono, esperado, clase in self.CASOS:
            with self.subTest(telefono=telefono):
                self.assertEqual(normalizar_telefono(telefono), esperado)
                self.assertEqual(clasificar_telefono(telefono), clase)

    def test_compartido_da_el_mismo_valor(self) -> None:
        self.assertEqual(normalizar_telefono("667 123 4567"), normalizar_telefono("+52 1 6671234567"))

    def test_no_modifica_la_entrada(self) -> None:
        original = "+52 667 123 4567"
        normalizar_telefono(original)
        self.assertEqual(original, "+52 667 123 4567")


class EnmascararTelefonoTests(unittest.TestCase):
    def test_muestra_solo_los_ultimos_cuatro(self) -> None:
        self.assertEqual(enmascarar_telefono("667 123 1234"), "•••• ••12 34")
        self.assertEqual(enmascarar_telefono("+52 1 667 123 9876"), "•••• ••98 76")
        self.assertNotIn("667", enmascarar_telefono("6671239876"))

    def test_vacio(self) -> None:
        self.assertEqual(enmascarar_telefono(None), "")
        self.assertEqual(enmascarar_telefono(""), "")

    def test_invalido_tambien_se_enmascara(self) -> None:
        enmascarado = enmascarar_telefono("667123456")
        self.assertTrue(enmascarado.endswith("34 56"))
        self.assertNotIn("6671", enmascarado)

    def test_muy_corto_no_revela_nada(self) -> None:
        self.assertEqual(enmascarar_telefono("12"), "•••• ••••")


if __name__ == "__main__":
    unittest.main()
