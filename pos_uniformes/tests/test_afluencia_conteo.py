"""Conteo de afluencia: cruces de línea, personas que pasan y acumulado por hora."""

from __future__ import annotations

import unittest
from datetime import datetime

from pos_uniformes.afluencia.conteo import (
    AcumuladorHora,
    ContadorLinea,
    ContadorPaso,
    Linea,
    inicio_de_hora,
    pies,
)

# Línea horizontal a media altura; la tienda queda abajo.
PUERTA = Linea(0.3, 0.5, 0.7, 0.5, lado_dentro="abajo")


class LineaTests(unittest.TestCase):
    def test_lado_dentro_abajo(self) -> None:
        self.assertEqual(PUERTA.lado(0.5, 0.8), 1)
        self.assertEqual(PUERTA.lado(0.5, 0.2), -1)
        self.assertEqual(PUERTA.lado(0.5, 0.5), 0)

    def test_lado_dentro_arriba_invierte(self) -> None:
        linea = Linea(0.3, 0.5, 0.7, 0.5, lado_dentro="arriba")
        self.assertEqual(linea.lado(0.5, 0.2), 1)
        self.assertEqual(linea.lado(0.5, 0.8), -1)

    def test_linea_vertical_izquierda_derecha(self) -> None:
        linea = Linea(0.5, 0.2, 0.5, 0.8, lado_dentro="derecha")
        self.assertEqual(linea.lado(0.9, 0.5), 1)
        self.assertEqual(linea.lado(0.1, 0.5), -1)

    def test_segmento_con_margen(self) -> None:
        self.assertTrue(PUERTA.dentro_del_segmento(0.5, 0.5))
        self.assertTrue(PUERTA.dentro_del_segmento(0.28, 0.5))  # dentro del margen 0.05
        self.assertFalse(PUERTA.dentro_del_segmento(0.1, 0.5))

    def test_validaciones(self) -> None:
        with self.assertRaises(ValueError):
            Linea(0.1, 0.1, 0.1, 0.1)
        with self.assertRaises(ValueError):
            Linea(0.1, 0.1, 0.9, 0.1, lado_dentro="norte")


class ContadorLineaTests(unittest.TestCase):
    def test_entra_al_cruzar_hacia_adentro(self) -> None:
        c = ContadorLinea(PUERTA)
        self.assertEqual(c.actualizar([(1, 0.5, 0.3)]), [])
        self.assertEqual(c.actualizar([(1, 0.5, 0.45)]), [])
        eventos = c.actualizar([(1, 0.5, 0.6)])
        self.assertEqual(eventos, [(1, "entra")])
        self.assertEqual((c.entradas, c.salidas), (1, 0))

    def test_sale_al_cruzar_hacia_afuera(self) -> None:
        c = ContadorLinea(PUERTA)
        c.actualizar([(7, 0.5, 0.7)])
        self.assertEqual(c.actualizar([(7, 0.5, 0.3)]), [(7, "sale")])
        self.assertEqual((c.entradas, c.salidas), (0, 1))

    def test_no_cuenta_doble_si_se_queda_del_mismo_lado(self) -> None:
        c = ContadorLinea(PUERTA)
        c.actualizar([(1, 0.5, 0.3)])
        c.actualizar([(1, 0.5, 0.6)])
        c.actualizar([(1, 0.5, 0.7)])
        c.actualizar([(1, 0.5, 0.9)])
        self.assertEqual(c.entradas, 1)

    def test_ida_y_vuelta_cuenta_entra_y_sale(self) -> None:
        c = ContadorLinea(PUERTA)
        c.actualizar([(1, 0.5, 0.3)])
        c.actualizar([(1, 0.5, 0.6)])
        c.actualizar([(1, 0.5, 0.3)])
        self.assertEqual((c.entradas, c.salidas), (1, 1))

    def test_cruce_fuera_del_segmento_no_cuenta(self) -> None:
        c = ContadorLinea(PUERTA)
        c.actualizar([(1, 0.1, 0.3)])
        self.assertEqual(c.actualizar([(1, 0.1, 0.7)]), [])
        self.assertEqual(c.entradas, 0)

    def test_primer_cuadro_sobre_la_linea_se_ignora(self) -> None:
        c = ContadorLinea(PUERTA)
        c.actualizar([(1, 0.5, 0.5)])
        c.actualizar([(1, 0.5, 0.6)])
        self.assertEqual(c.entradas, 0)  # nunca se supo de qué lado venía

    def test_varias_personas_en_el_mismo_cuadro(self) -> None:
        c = ContadorLinea(PUERTA)
        c.actualizar([(1, 0.4, 0.3), (2, 0.6, 0.7)])
        eventos = c.actualizar([(1, 0.4, 0.6), (2, 0.6, 0.3)])
        self.assertEqual(sorted(eventos), [(1, "entra"), (2, "sale")])

    def test_olvidar_ausentes_y_tomar(self) -> None:
        c = ContadorLinea(PUERTA)
        c.actualizar([(1, 0.5, 0.3), (2, 0.5, 0.3)])
        c.olvidar_ausentes({2})
        # El id 1 reaparece adentro: sin historial, no cuenta.
        self.assertEqual(c.actualizar([(1, 0.5, 0.7)]), [])
        c.actualizar([(2, 0.5, 0.7)])
        self.assertEqual(c.tomar_y_reiniciar(), (1, 0))
        self.assertEqual(c.tomar_y_reiniciar(), (0, 0))


class ContadorPasoTests(unittest.TestCase):
    def test_cuenta_ids_distintos_una_vez(self) -> None:
        c = ContadorPaso()
        self.assertEqual(c.actualizar([1, 2]), 2)
        self.assertEqual(c.actualizar([2, 3]), 1)
        self.assertEqual(c.actualizar([1, 2, 3]), 0)
        self.assertEqual(c.tomar_y_reiniciar(), 3)
        self.assertEqual(c.actualizar([4]), 1)


class AcumuladorHoraTests(unittest.TestCase):
    def test_suma_por_camara_y_hora(self) -> None:
        a = AcumuladorHora()
        a.agregar("ENTRADA1.1", datetime(2026, 9, 8, 12, 5), entradas=1)
        a.agregar("ENTRADA1.1", datetime(2026, 9, 8, 12, 50), entradas=2, salidas=1)
        a.agregar("ENTRADA1", datetime(2026, 9, 8, 12, 10), pasan=5)
        a.agregar("ENTRADA1.1", datetime(2026, 9, 8, 13, 1), entradas=1)
        a.agregar("ENTRADA1.1", datetime(2026, 9, 8, 13, 2))  # nada que sumar
        filas = a.vaciar()
        self.assertEqual(filas, [
            ("ENTRADA1", datetime(2026, 9, 8, 12, 0), 0, 0, 5),
            ("ENTRADA1.1", datetime(2026, 9, 8, 12, 0), 3, 1, 0),
            ("ENTRADA1.1", datetime(2026, 9, 8, 13, 0), 1, 0, 0),
        ])
        self.assertTrue(a.vacio())
        self.assertEqual(a.vaciar(), [])

    def test_inicio_de_hora(self) -> None:
        self.assertEqual(inicio_de_hora(datetime(2026, 9, 8, 12, 59, 59, 5)), datetime(2026, 9, 8, 12))


class PiesTests(unittest.TestCase):
    def test_centro_inferior_normalizado(self) -> None:
        self.assertEqual(pies((100, 50, 300, 450), 1000, 500), (0.2, 0.9))


if __name__ == "__main__":
    unittest.main()
