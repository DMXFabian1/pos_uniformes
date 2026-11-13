"""Ritmo de venta por talla para Inventario (tanda 5): «Se va a acabar»."""

from __future__ import annotations

import unittest

from pos_uniformes.services.analitica_tablero_service import SEMANAS_DE_ALERTA, por_acabarse
from pos_uniformes.services.inventario_ritmo_service import (
    DIAS_PARA_ACABARSE,
    LLAVE_PEDIDAS,
    LLAVE_VENDIDAS,
    SE_ACABO_Y_SE_VENDE,
    SE_VA_A_ACABAR,
    CacheVentas,
    Ritmo,
    estado_de_fila,
    poner_datos_de_venta,
    ritmo_de_fila,
)


class RitmoTests(unittest.TestCase):
    def test_el_umbral_es_el_de_analitica(self) -> None:
        self.assertEqual(DIAS_PARA_ACABARSE, 14)
        self.assertEqual(DIAS_PARA_ACABARSE, int(SEMANAS_DE_ALERTA * 7))

    def test_se_va_a_acabar_con_poco_para_su_ritmo(self) -> None:
        # 12 en 30 días = 0.4 al día; 2 piezas alcanzan para 5 días.
        ritmo = Ritmo(vendidas=12, existencia=2)
        self.assertEqual(ritmo.estado, SE_VA_A_ACABAR)
        self.assertEqual(ritmo.texto(), "Se vende ~3 por semana · alcanza para 5 días")

    def test_alcanza_de_sobra_no_es_alerta(self) -> None:
        ritmo = Ritmo(vendidas=12, existencia=20)  # 50 días
        self.assertIsNone(ritmo.estado)
        self.assertEqual(ritmo.texto(), "Se vende ~3 por semana · alcanza para ~7 semanas")

    def test_se_acabo_y_se_vende(self) -> None:
        for existencia in (0, -2):
            ritmo = Ritmo(vendidas=4, existencia=existencia)
            self.assertEqual(ritmo.estado, SE_ACABO_Y_SE_VENDE)
            self.assertTrue(ritmo.texto().endswith("· ya no hay"))

    def test_una_sola_venta_no_es_ritmo(self) -> None:
        self.assertIsNone(Ritmo(vendidas=1, existencia=0).estado)
        self.assertEqual(Ritmo(vendidas=1, existencia=0).texto(), "Se vendió 1 en 30 días · ya no hay")
        self.assertEqual(Ritmo(vendidas=1, existencia=5).texto(), "Se vendió 1 en 30 días")

    def test_sin_ventas(self) -> None:
        self.assertEqual(Ritmo(vendidas=0, existencia=3).texto(), "Sin ventas en 30 días")
        self.assertIsNone(Ritmo(vendidas=0, existencia=0).estado)

    def test_menos_de_una_por_semana(self) -> None:
        self.assertEqual(Ritmo(vendidas=3, existencia=1).texto_venta(), "Se vendieron 3 en 30 días")

    def test_coincide_con_por_acabarse_de_analitica(self) -> None:
        vendidas = {"A": 12, "B": 12, "C": 4, "D": 1, "E": 30}
        stock = {"A": 2, "B": 20, "C": 0, "D": 0, "E": 13}
        analitica = {p.sku for p in por_acabarse(vendidas, {k: {"stock": v} for k, v in stock.items()}, tope=99)}
        aqui = {sku for sku in vendidas if Ritmo(vendidas[sku], stock[sku]).estado}
        self.assertEqual(aqui, analitica)


class FilaTests(unittest.TestCase):
    def test_sin_dato_de_ventas_no_hay_ritmo(self) -> None:
        self.assertIsNone(ritmo_de_fila({"sku": "A", "stock_actual": 3}))

    def test_conjunto_no_tiene_ritmo_propio(self) -> None:
        fila = {"sku": "A", "stock_actual": 0, "es_conjunto": True, LLAVE_VENDIDAS: 9}
        self.assertIsNone(ritmo_de_fila(fila))

    def test_desactivada_no_se_marca(self) -> None:
        fila = {"sku": "A", "stock_actual": 0, LLAVE_VENDIDAS: 9, "variante_activa": False}
        self.assertIsNone(estado_de_fila(fila))
        fila["variante_activa"] = True
        self.assertEqual(estado_de_fila(fila), SE_ACABO_Y_SE_VENDE)

    def test_poner_datos_de_venta(self) -> None:
        filas = [{"sku": "A"}, {"sku": "B"}]
        poner_datos_de_venta(filas, {"A": 5}, {"B": 2})
        self.assertEqual([f[LLAVE_VENDIDAS] for f in filas], [5, 0])
        self.assertEqual([f[LLAVE_PEDIDAS] for f in filas], [0, 2])
        # Sin dato (la Libreta no respondió, o no es ADMIN para la demanda) la llave se quita.
        poner_datos_de_venta(filas, None, {})
        self.assertTrue(all(LLAVE_VENDIDAS not in f and LLAVE_PEDIDAS not in f for f in filas))


class CacheTests(unittest.TestCase):
    def test_lee_una_vez_por_ventana_de_tiempo(self) -> None:
        reloj = [0.0]
        lecturas = []
        cache = CacheVentas(lambda: lecturas.append(1) or {"A": 2}, segundos=300, reloj=lambda: reloj[0])
        self.assertEqual(cache.obtener(), {"A": 2})
        reloj[0] = 299
        cache.obtener()
        self.assertEqual(len(lecturas), 1)
        reloj[0] = 301
        cache.obtener()
        self.assertEqual(len(lecturas), 2)

    def test_si_falla_sigue_sin_dato_y_no_reintenta_en_cada_refresco(self) -> None:
        reloj = [0.0]
        llamadas = []

        def falla():
            llamadas.append(1)
            raise RuntimeError("sin base")

        cache = CacheVentas(falla, segundos=300, reloj=lambda: reloj[0])
        self.assertIsNone(cache.obtener())
        self.assertIsNone(cache.obtener())
        self.assertEqual(len(llamadas), 1)

    def test_si_falla_despues_conserva_lo_ultimo(self) -> None:
        reloj = [0.0]
        respuestas = [{"A": 3}]

        def cargar():
            if not respuestas:
                raise RuntimeError("se cayó")
            return respuestas.pop()

        cache = CacheVentas(cargar, segundos=10, reloj=lambda: reloj[0])
        self.assertEqual(cache.obtener(), {"A": 3})
        reloj[0] = 20
        self.assertEqual(cache.obtener(), {"A": 3})

    def test_invalidar_obliga_a_leer(self) -> None:
        lecturas = []
        cache = CacheVentas(lambda: lecturas.append(1) or {}, reloj=lambda: 0.0)
        cache.obtener()
        cache.invalidar()
        cache.obtener()
        self.assertEqual(len(lecturas), 2)


if __name__ == "__main__":
    unittest.main()
