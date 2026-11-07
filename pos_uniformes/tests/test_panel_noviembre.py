"""El Panel de Uniformes, puesto al día (2026-11-07).

Daniel: «también actualicemos panel de uniformes» → «hazlo completo, la de solo
lectura». Una sola cifra de agotadas, el valor explicado, «Actualizado hace…»,
la paleta de la tienda y la pestaña de conteos de solo lectura."""

from __future__ import annotations

import unittest

from pos_uniformes.scripts import generar_panel_uniformes as gen


class _Ultimo:
    def __init__(self, texto):
        self._t = texto

    def texto(self):
        return self._t


class _Estado:
    def __init__(self, nombre, salud, *, faltan=0, tallas=20, al_dia=20, agotadas=0, quien=""):
        self.nombre, self.salud = nombre, salud
        self.faltan_de_contar, self.tallas, self.al_dia = faltan, tallas, al_dia
        self.pct_al_dia = round(100 * al_dia / tallas) if tallas else 0
        self.agotadas, self.quien_en_proceso = agotadas, quien
        self.titular = {"rojo": "nunca se ha contado", "ambar": f"faltan {faltan} de {tallas} tallas por contar",
                        "verde": "al día"}[salud]
        self.ultimo_conteo = _Ultimo("hace 3 días (Fanny)")


class ConteosDeSoloLecturaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = gen.build_conteo({
            1: _Estado("Benito Juárez", "verde", agotadas=4),
            2: _Estado("CBTIS 148", "rojo", tallas=30, al_dia=0),
            3: _Estado("Patria", "ambar", faltan=6, al_dia=14, quien="Stayce Chavarria"),
        })

    def test_ya_no_es_el_conteo_viejo(self) -> None:
        self.assertIn("Cómo van los conteos", self.html)
        self.assertIn("El conteo se hace en el kiosko", self.html)
        for viejo in ("conteo-escuela", "conteoGuardar", "conteoApplyAdjustments", "conteo-app"):
            self.assertNotIn(viejo, self.html)

    def test_lo_mas_urgente_primero_con_el_semaforo_del_mapa(self) -> None:
        orden = [self.html.index(n) for n in ("CBTIS 148", "Patria", "Benito Juárez")]
        self.assertEqual(orden, sorted(orden))
        self.assertIn(gen.SALUD_COLOR["rojo"], self.html)
        self.assertIn("Stayce Chavarria", self.html)          # quién cuenta ahora
        self.assertIn("14 de 20", self.html)

    def test_cuenta_cuantas_hay_en_cada_color(self) -> None:
        for texto in ("No sabemos qué hay", "Le falta contarse", "Al día"):
            self.assertIn(texto, self.html)

    def test_sin_estados_lo_dice(self) -> None:
        self.assertIn("No se pudo leer cómo van los conteos", gen.build_conteo(None))


class UnaSolaCifraTests(unittest.TestCase):
    def tearDown(self) -> None:
        gen.DISPONIBILIDAD.clear()

    def _stats(self):
        return {
            "por_nivel": {}, "escuelas": 2, "productos": 10, "stock_tienda": 100, "stock_total": 120,
            "stock_piso": 10, "stock_bodega": 10, "valor_inventario": 4_500_000.0,
            "variantes_con_escuela": 999, "variantes_sin_stock": 1230, "variantes_bajo_min": 50,
        }

    def test_el_resumen_dice_lo_mismo_que_disponibilidad(self) -> None:
        gen.DISPONIBILIDAD.update(tallas=1500, agotadas=1192, bajo=170, prendas_con_faltantes=291,
                                  cobertura=65, escuelas_con_faltantes=40)
        html = gen.build_resumen(self._stats(), [], {}, {"Primaria": 1_500_000.0, "Secundaria": 900_000.0})
        self.assertIn("Agotadas <b>1,192</b>", html)
        self.assertNotIn("1,230", html)
        self.assertIn("igual que Disponibilidad", html)

    def test_el_valor_dice_de_donde_sale_la_diferencia(self) -> None:
        html = gen.build_resumen(self._stats(), [], {}, {"Primaria": 1_500_000.0, "Secundaria": 900_000.0})
        self.assertIn("$2.4M uniformes de escuela · $2.1M básicos y ropa", html)
        self.assertIn("Uniformes de escuela, por nivel", html)

    def test_la_alerta_usa_la_cifra_de_disponibilidad(self) -> None:
        gen.DISPONIBILIDAD.update(tallas=1500, agotadas=1192, bajo=170, prendas_con_faltantes=291,
                                  cobertura=65, escuelas_con_faltantes=40)
        insights, _ = gen.compute_insights(
            {"por_nivel": {}, "escuelas": 0}, [], {}, [], ["producto_id"], set()
        )
        alerta = [i for i in insights if i[0] == "alert"]
        self.assertEqual(alerta[0][1], "1,192 tallas agotadas en 291 prendas")
        self.assertNotIn("productos sin stock", " ".join(i[1] for i in insights))


class CabeceraTests(unittest.TestCase):
    def test_dice_hace_cuanto_se_actualizo_y_lleva_la_paleta(self) -> None:
        html = gen.generate_html("", "", "", "", "", "")
        self.assertIn('id="frescura"', html)
        self.assertIn("function pintarFrescura", html)
        self.assertIn("--brand: #6b1f3a", html)
        self.assertIn(">Conteos</div>", html)
