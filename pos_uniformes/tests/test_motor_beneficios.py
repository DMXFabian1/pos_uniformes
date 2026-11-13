"""M1a — Motor central de beneficios (Daniel, 2026-11-11).

Cubre el motor puro de `services/beneficios/`:
- R1, Q2, I5/D1 e I8/D2 (repartos exactos al centavo);
- los escenarios de oro de M0 calculados con el motor;
- las reglas aprobadas que cambian lo de hoy (C2, C4, C8, C9, T4, Q6),
  cada una con la cifra de hoy y la del motor;
- propiedades: orden de captura, agrupación, sumas exactas, sin negativos;
- equivalencia del total con el cálculo actual del kiosko en carritos
  aleatorios donde ninguna regla aprobada cambia el total;
- fotografía reproducible (T2), validación de la entrada y pureza.

No toca base, Qt, red ni producción.
"""

from __future__ import annotations

import ast
import random
import subprocess
import sys
import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from pos_uniformes.services import incentivo_empleada_service as inc
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import monedero_service as mon
from pos_uniformes.services import rebaja_service as reb
from pos_uniformes.services.beneficios import motivos as M
from pos_uniformes.services.beneficios.contrato import (
    ClienteCtx,
    CompradoraCtx,
    EntradaInvalida,
    EntradaVenta,
    LineaEntrada,
    Pago,
    Rebaja,
)
from pos_uniformes.services.beneficios.fotografia import a_json, fotografia, huella
from pos_uniformes.services.beneficios.motor import VERSION_MOTOR, calcular, canje_ajustado, neto_con_comision
from pos_uniformes.services.beneficios.reparto import (
    ErrorDeReparto,
    clave_orden,
    mayor_residuo,
    redondeo_tienda,
    repartir_redondeo,
)
from pos_uniformes.services.fidelizacion import descuento_programa_service as dps
from pos_uniformes.services.sale_rounding_service import resolve_sale_rounding

D = Decimal
FECHA = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
CLUB = ClienteCtx(9, "CLUB", D("5"), None)
LEAL = ClienteCtx(9, "LEAL", D("10"), None)
MAYORISTA = ClienteCtx(9, "MAYORISTA", D("15"), D("15"))


def uid(n: int) -> str:
    return str(uuid.UUID(int=n))


class _Fabrica:
    def __init__(self) -> None:
        self.n = 0

    def linea(self, sku, precio, cantidad=1, *, categoria="Oficial", oferta=None, liquidacion=None, promo=False,
              n=None) -> LineaEntrada:
        self.n += 1
        rebaja = None
        if oferta is not None:
            rebaja = Rebaja("oferta", D(oferta))
        if liquidacion is not None:
            rebaja = Rebaja("liquidacion", D(liquidacion))
        return LineaEntrada(uid(n if n is not None else self.n), sku, cantidad, D(precio), categoria, rebaja, promo)


def venta(lineas, **kw) -> EntradaVenta:
    return EntradaVenta(tuple(lineas), FECHA, **kw)


def con_nivel(pct, restante, codigo="VEND-3") -> dict:
    return dict(descuento_empleada=True,
                compradora=CompradoraCtx(codigo, D(pct), None if restante is None else D(restante)))


# ═══ 1. Repartos: R1, Q2, I5, I8 ═════════════════════════════════════════


class RedondeoR1Tests(unittest.TestCase):
    def test_coincide_con_la_regla_de_hoy_en_todos_los_centavos(self) -> None:
        for pesos in (0, 1, 152, 999):
            for centavos in range(100):
                monto = D(pesos) + D(centavos) / 100
                with self.subTest(monto=monto):
                    self.assertEqual(redondeo_tienda(monto), resolve_sale_rounding(monto).collected_total)

    def test_negativo_se_rechaza(self) -> None:
        with self.assertRaises(ErrorDeReparto):
            redondeo_tienda(D("-1"))


class MayorResiduoQ2Tests(unittest.TestCase):
    def test_suma_exacta_y_centavo_al_mayor_residuo(self) -> None:
        partes = mayor_residuo(D("37"), [D("150")] * 3, [("A", "1"), ("B", "2"), ("C", "3")])
        self.assertEqual(sum(partes), D("37"))
        self.assertEqual(partes, [D("12.34"), D("12.33"), D("12.33")])

    def test_empate_lo_decide_el_sku_menor(self) -> None:
        claves = [clave_orden("SKU000621", uid(1)), clave_orden("SKU000098", uid(2)), clave_orden("SKU001200", uid(3))]
        self.assertEqual(mayor_residuo(D("1.00"), [D("150")] * 3, claves), [D("0.33"), D("0.34"), D("0.33")])

    def test_el_orden_de_entrada_no_cambia_nada(self) -> None:
        pesos = [D("170.05"), D("142.50"), D("114.00"), D("0.01")]
        claves = [("S4", "d"), ("S1", "a"), ("S3", "c"), ("S2", "b")]
        base = dict(zip(claves, mayor_residuo(D("9.99"), pesos, claves)))
        rng = random.Random(7)
        for _ in range(50):
            idx = list(range(4))
            rng.shuffle(idx)
            otra = dict(zip([claves[i] for i in idx], mayor_residuo(D("9.99"), [pesos[i] for i in idx], [claves[i] for i in idx])))
            self.assertEqual(otra, base)

    def test_casos_limite(self) -> None:
        self.assertEqual(mayor_residuo(D("0"), [D("0"), D("0")], [("a",), ("b",)]), [D("0.00"), D("0.00")])
        with self.assertRaises(ErrorDeReparto):
            mayor_residuo(D("1"), [D("0")], [("a",)])
        with self.assertRaises(ErrorDeReparto):
            mayor_residuo(D("-1"), [D("1")], [("a",)])
        with self.assertRaises(ErrorDeReparto):
            mayor_residuo(D("0.001"), [D("1")], [("a",)])

    def test_propiedad_suma_exacta(self) -> None:
        rng = random.Random(11)
        for _ in range(500):
            n = rng.randint(1, 12)
            pesos = [D(rng.randint(0, 50000)) / 100 for _ in range(n)]
            if sum(pesos) == 0:
                continue
            total = D(rng.randint(0, 100000)) / 100
            partes = mayor_residuo(total, pesos, [(str(i),) for i in range(n)])
            self.assertEqual(sum(partes), total)
            self.assertTrue(all(p >= 0 for p in partes))
            for p, w in zip(partes, pesos):
                if w == 0:
                    self.assertEqual(p, 0)


class OrdenSkuI5Tests(unittest.TestCase):
    LISTA = ["SKU000621", "SKU99", "sku000050", "SKU001200", "PANTS-12", "SKU000098", "SKU1000000"]
    ESPERADO = ["PANTS-12", "SKU000098", "SKU000621", "SKU001200", "SKU1000000", "SKU99", "sku000050"]

    def test_orden_por_puntos_de_codigo(self) -> None:
        self.assertEqual([c[0] for c in sorted(clave_orden(s, uid(1)) for s in self.LISTA)], self.ESPERADO)

    def test_no_depende_del_idioma_del_sistema(self) -> None:
        codigo = (
            "import locale, sys\n"
            "from pos_uniformes.services.beneficios.reparto import clave_orden\n"
            "for loc in ('C', 'es_MX.UTF-8', 'en_US.UTF-8'):\n"
            "    try: locale.setlocale(locale.LC_ALL, loc)\n"
            "    except locale.Error: continue\n"
            f"    print(loc, [c[0] for c in sorted(clave_orden(s, 'u') for s in {self.LISTA!r})])\n"
        )
        raiz = Path(__file__).resolve().parents[2]
        salida = subprocess.run([sys.executable, "-c", codigo], cwd=raiz, capture_output=True, text=True, check=True)
        renglones = [r for r in salida.stdout.splitlines() if r]
        self.assertTrue(renglones)
        for r in renglones:
            self.assertTrue(r.endswith(repr(self.ESPERADO)), r)

    def test_espacios_minusculas_y_vacio_no_se_normalizan(self) -> None:
        claves = sorted([clave_orden(" SKU1", "u"), clave_orden("SKU1", "u"), clave_orden(None, "u"), clave_orden("sku1", "u")])
        self.assertEqual([c[0] for c in claves], ["", " SKU1", "SKU1", "sku1"])

    def test_mismo_sku_desempata_linea_uid(self) -> None:
        self.assertLess(clave_orden("SKU000621", uid(1)), clave_orden("SKU000621", uid(2)))


class RedondeoI8Tests(unittest.TestCase):
    """Los ejemplos de `decisiones_previas_M1.md` §2.2, calculados por el motor."""

    def _caso(self, precios_y_pct):
        f = _Fabrica()
        lineas = []
        for sku, precio, pct in precios_y_pct:
            lineas.append(f.linea(sku, precio))
        return lineas

    def _repartir(self, filas):
        cobrados = [D(c) for _, c, _ in filas]
        limites = [D(l) for _, _, l in filas]
        claves = [clave_orden(s, uid(i)) for i, (s, _, _) in enumerate(filas)]
        total = redondeo_tienda(sum(cobrados))
        res = repartir_redondeo(total - sum(cobrados), cobrados, limites, claves)
        return total, [c + p for c, p in zip(cobrados, res.partes)], res

    def test_ejemplos_aprobados(self) -> None:
        casos = [
            ([("SKU000621", "170.05", "179"), ("SKU000098", "142.50", "150")], "312.50", ["170.02", "142.48"]),
            ([("SKU000621", "170.05", "179"), ("SKU000098", "142.50", "150"), ("SKU001200", "114.00", "120")],
             "426.50", ["170.03", "142.48", "113.99"]),
            ([("SKU001000", "53.10", "59"), ("SKU001001", "161.10", "179")], "214.50", ["53.17", "161.33"]),
            ([("SKU000310", "141.30", "157"), ("SKU000415", "209.70", "233"), ("SKU000500", "86.40", "96")],
             "437.50", ["141.33", "209.75", "86.42"]),
            ([("SKU000101", "152.15", "179"), ("SKU000102", "169.15", "199"), ("SKU000103", "72.25", "85"),
              ("SKU000104", "204.00", "240"), ("SKU000105", "53.55", "63")],
             "651.00", ["152.13", "169.12", "72.24", "203.97", "53.54"]),
            ([("SKU001000", "53.10", "59"), ("SKU001001", "56.70", "63"), ("SKU001002", "76.50", "85"),
              ("SKU001003", "86.40", "96"), ("SKU001004", "108.00", "120")],
             "381.00", ["53.14", "56.74", "76.56", "86.47", "108.09"]),
            ([("SKU000621", "141.30", "157"), ("SKU000098", "141.30", "157"), ("SKU001200", "141.30", "157")],
             "424.00", ["141.33", "141.34", "141.33"]),
        ]
        for filas, total, cobrados in casos:
            with self.subTest(total=total):
                t, c, res = self._repartir(filas)
                self.assertEqual(t, D(total))
                self.assertEqual(c, [D(x) for x in cobrados])
                self.assertEqual(res.excepcion_d2, ())

    def test_redistribucion_por_limite(self) -> None:
        # A la primera le tocan $0.10 de $0.25, pero solo le caben $0.05: el resto pasa a la segunda.
        total, cobrados, res = self._repartir([("SKU000700", "99.95", "100"), ("SKU000701", "141.30", "157")])
        self.assertEqual(total, D("241.50"))
        self.assertEqual(cobrados, [D("100.00"), D("141.50")])
        self.assertEqual(res.rondas, 2)
        self.assertEqual(res.excepcion_d2, ())

    def test_linea_ya_en_su_limite_no_recibe_nada(self) -> None:
        total, cobrados, res = self._repartir([("SKU000700", "100.00", "100"), ("SKU000701", "141.30", "157")])
        self.assertEqual((total, cobrados, res.rondas), (D("241.50"), [D("100.00"), D("141.50")], 1))

    def test_excepcion_d2_sin_capacidad(self) -> None:
        """Todo a precio de lista con centavos que R1 sube: se reparte solo lo necesario y se registra."""
        total, cobrados, res = self._repartir([("A", "12.90", "12.90"), ("B", "12.90", "12.90")])
        self.assertEqual(total, D("26.00"))
        self.assertEqual(sum(cobrados), D("26.00"))
        self.assertEqual(cobrados, [D("13.00"), D("13.00")])
        self.assertEqual(res.importe_excepcion, D("0.20"))
        self.assertEqual(res.excepcion_d2, (0, 1))

    def test_propiedad_suma_exacta_sin_negativos_y_limites(self) -> None:
        rng = random.Random(23)
        for _ in range(2000):
            n = rng.randint(1, 30)
            filas = []
            for i in range(n):
                lista = D(rng.choice([0, 1, 12, 59, 85, 96, 120, 150, 179, 233, 400]))
                pct = D(rng.choice([0, 5, 10, 15, 20]))
                cobrado = (lista * (100 - pct) / 100).quantize(D("0.01"))
                filas.append((f"S{rng.randint(0, 99):03d}", format(cobrado, "f"), format(lista, "f")))
            if sum(D(c) for _, c, _ in filas) == 0:
                continue
            total, cobrados, res = self._repartir(filas)
            self.assertEqual(sum(cobrados), total)
            self.assertTrue(all(c >= 0 for c in cobrados))
            for i, (c, (_, _, lim)) in enumerate(zip(cobrados, filas)):
                if i not in res.excepcion_d2:
                    self.assertLessEqual(c, D(lim))


# ═══ 2. Escenarios de oro de M0, con el motor ════════════════════════════


class OroProgramasTests(unittest.TestCase):
    def test_e01_e02_e03_e05_abono_sobre_360(self) -> None:
        f = _Fabrica()
        for tasa, abono in (("5", "18.00"), ("10", "36.00"), ("13", "46.80"), ("15", "54.00")):
            with self.subTest(tasa=tasa):
                c = calcular(venta([f.linea("PO1", "180", 2)], cliente=ClienteCtx(9, "X", D(tasa), None)))
                self.assertEqual((c.total, c.monedero.abono), (D("360.00"), D(abono)))
                self.assertEqual(sum(l.abono_linea for l in c.lineas), D(abono))

    def test_e15_sin_programa_no_hay_monedero(self) -> None:
        c = calcular(venta([_Fabrica().linea("PO1", "180", 2)]))
        self.assertIsNone(c.monedero)
        self.assertIn(M.SIN_PROGRAMA, c.motivos_ticket)

    def test_abono_se_trunca(self) -> None:
        c = calcular(venta([_Fabrica().linea("X", "333.50")], cliente=ClienteCtx(1, "X", D("13"), None)))
        # 333.50 → R1 → 333.50; × 13 % = 43.355 → 43.35
        self.assertEqual(c.monedero.abono, D("43.35"))


class OroMayoristaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.f = _Fabrica()

    def _3pz(self):
        return [self.f.linea("B3", "300", categoria="Deportivo", promo=True),
                self.f.linea("P3", "150", categoria="Deportivo", promo=True)]

    def test_e04_descuento_dos_playeras(self) -> None:
        c = calcular(venta([self.f.linea("PO1", "180", 2)], cliente=MAYORISTA, modalidad_mayorista="descuento"))
        self.assertEqual((c.total, c.descuento_total, c.monedero), (D("306.00"), D("54.00"), None))
        self.assertTrue(c.descuento_aplicado)
        self.assertIn(M.MAYOREO_SIN_MONEDERO, c.motivos_ticket)

    def test_e05_monedero(self) -> None:
        c = calcular(venta([self.f.linea("PO1", "180", 2)], cliente=MAYORISTA, modalidad_mayorista="monedero"))
        self.assertEqual((c.total, c.monedero.abono), (D("360.00"), D("54.00")))

    def test_e06_t9_monedero_acumula_sobre_la_3pz(self) -> None:
        c = calcular(venta([self.f.linea("PO1", "180"), *self._3pz()], cliente=MAYORISTA, modalidad_mayorista="monedero"))
        self.assertEqual((c.total, c.monedero.abono), (D("630.00"), D("94.50")))

    def test_e07_descuento_con_3pz(self) -> None:
        c = calcular(venta([self.f.linea("PO1", "180"), *self._3pz()], cliente=MAYORISTA, modalidad_mayorista="descuento"))
        self.assertEqual((c.total, c.descuento_total, c.monedero), (D("603.00"), D("27.00"), None))
        tres = [l for l in c.lineas if l.clasificacion_al_vender == "3pz"]
        self.assertTrue(all(M.TRES_PZ_SIN_MAYOREO in l.motivos and l.descuento.importe == 0 for l in tres))

    def test_c4_descuento_de_cero_respeta_la_modalidad_y_no_marca_descuento(self) -> None:
        """CAMBIA (C4): hoy la venta queda «con descuento 15 %»; con el motor, descuento_aplicado = False."""
        c = calcular(venta(self._3pz(), cliente=MAYORISTA, modalidad_mayorista="descuento"))
        self.assertEqual(c.total, D("450.00"))
        self.assertEqual(c.modalidad_mayorista_elegida, "descuento")
        self.assertFalse(c.descuento_aplicado)
        self.assertIsNone(c.monedero)
        self.assertIn(M.MAYOREO_SIN_LINEAS_ELEGIBLES, c.motivos_ticket)

    def test_descuento_sin_pct_de_mayoreo_es_entrada_invalida(self) -> None:
        with self.assertRaises(EntradaInvalida):
            calcular(venta([self.f.linea("PO1", "180")], cliente=CLUB, modalidad_mayorista="descuento"))


class OroRebajasTests(unittest.TestCase):
    def _carrito(self, f):
        return [f.linea("PL2", "250", categoria="Uniformes", oferta="175"),
                f.linea("SL1", "300", categoria="Ropa casual", liquidacion="200"),
                f.linea("PO1", "180")]

    def test_e08_club_con_oferta_y_liquidacion(self) -> None:
        c = calcular(venta(self._carrito(_Fabrica()), cliente=CLUB))
        self.assertEqual((c.total, c.monedero.base, c.monedero.abono, c.ahorro_rebajas),
                         (D("555.00"), D("180.00"), D("9.00"), D("175.00")))
        clasif = {l.sku: l.clasificacion_al_vender for l in c.lineas}
        self.assertEqual(clasif, {"PL2": "oferta", "SL1": "liquidacion", "PO1": "normal"})

    def test_e08b_mayorista_descuento_con_rebajas(self) -> None:
        c = calcular(venta(self._carrito(_Fabrica()), cliente=MAYORISTA, modalidad_mayorista="descuento"))
        self.assertEqual((c.total, c.descuento_total), (D("528.00"), D("27.00")))

    def test_lo_rebajado_no_lleva_descuento_ni_tope_ni_leal(self) -> None:
        c = calcular(venta(self._carrito(_Fabrica()), **con_nivel("20", "3000")))
        for l in c.lineas:
            if l.clasificacion_al_vender in ("oferta", "liquidacion"):
                self.assertEqual((l.descuento.importe, l.consumo_tope, l.base_leal), (D("0"), D("0"), D("0")))
                self.assertIn(M.REBAJA_SIN_OTRO_BENEFICIO, l.motivos)


class OroEmpleadaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.f = _Fabrica()

    def test_e09_uniforme_llega_a_10(self) -> None:
        c = calcular(venta([self.f.linea("PO1", "180", 2)], **con_nivel("15", "3000")))
        self.assertEqual((c.total, c.consumo_tope_total), (D("324.00"), D("360.00")))
        self.assertIn(M.TOPE_UNIFORME_10, c.lineas[0].motivos)

    def test_e10_ropa_casual_lleva_el_nivel(self) -> None:
        c = calcular(venta([self.f.linea("SC1", "400", categoria="Ropa casual")], **con_nivel("15", "3000")))
        self.assertEqual((c.total, c.consumo_tope_total), (D("340.00"), D("400.00")))

    def test_kiosko_compradora_con_nivel(self) -> None:
        c = calcular(venta([self.f.linea("PO1", "180", 2), self.f.linea("SC1", "400", categoria="Ropa casual")],
                           **con_nivel("15", "3000")))
        self.assertEqual((c.total, c.descuento_total), (D("664.00"), D("96.00")))

    def test_c8_cualquier_orden_da_461_50(self) -> None:
        """CAMBIA (C8): hoy $461.50 o $466.00 según el orden; con el motor, siempre $461.50."""
        a = self.f.linea("CH1", "280", categoria="Ropa casual")
        b = self.f.linea("SU1", "250", categoria="Ropa casual")
        for orden in ([a, b], [b, a]):
            self.assertEqual(calcular(venta(orden, **con_nivel("20", "300"))).total, D("461.50"))

    def test_c9_por_pieza_junto_o_separado(self) -> None:
        """CAMBIA (C9): hoy «2 × $180» va todo al 5 % ($342); por pieza, una al 20 % y otra al 5 % ($315)."""
        junto = calcular(venta([self.f.linea("A", "180", 2, categoria="Ropa casual")], **con_nivel("20", "300")))
        separado = calcular(venta([self.f.linea("A", "180", categoria="Ropa casual"),
                                   self.f.linea("A", "180", categoria="Ropa casual")], **con_nivel("20", "300")))
        for c in (junto, separado):
            self.assertEqual(c.total, D("315.00"))
            self.assertEqual((c.lineas[0].piezas_con_nivel, c.lineas[0].piezas_al_base), (1, 1))
            self.assertEqual(c.consumo_tope_total, D("180.00"))
        self.assertEqual(len(separado.lineas[0].lineas_origen), 2)
        self.assertIn(M.LINEAS_AGRUPADAS, separado.lineas[0].motivos)

    def test_p4_mismo_precio_lo_decide_el_sku(self) -> None:
        """El ejemplo de $28: uniforme $280 (`SKU000415`) y casual $280 (`SKU000310`), tope $300 al 20 %."""
        pants = self.f.linea("SKU000415", "280", categoria="Oficial")
        sudadera = self.f.linea("SKU000310", "280", categoria="Ropa casual")
        for orden in ([pants, sudadera], [sudadera, pants]):
            self.assertEqual(calcular(venta(orden, **con_nivel("20", "300"))).total, D("490.00"))

    def test_una_linea_posterior_mas_chica_si_cabe(self) -> None:
        c = calcular(venta([self.f.linea("A", "400", categoria="Ropa casual"), self.f.linea("B", "100", categoria="Ropa casual")],
                           **con_nivel("20", "300")))
        self.assertEqual(c.total, D("460.00"))
        self.assertEqual(c.consumo_tope_total, D("100.00"))

    def test_3pz_y_rebajas_no_gastan_tope(self) -> None:
        c = calcular(venta([self.f.linea("B3", "300", categoria="Deportivo", promo=True),
                            self.f.linea("PL2", "250", categoria="Uniformes", oferta="175"),
                            self.f.linea("SC1", "400", categoria="Ropa casual")], **con_nivel("20", "400")))
        self.assertEqual(c.consumo_tope_total, D("400.00"))
        tres = next(l for l in c.lineas if l.sku == "B3")
        self.assertEqual(tres.descuento.pct, D("5"))
        self.assertIn(M.TRES_PZ_EMPLEADA_BASE, tres.motivos)

    def test_sin_tope_todo_con_nivel(self) -> None:
        c = calcular(venta([self.f.linea("SC1", "400", 3, categoria="Ropa casual")], **con_nivel("20", None)))
        self.assertEqual(c.lineas[0].piezas_con_nivel, 3)

    def test_d1_con_descuento_de_empleada_no_hay_monedero_ni_leal(self) -> None:
        c = calcular(venta([self.f.linea("PO1", "180", 2)], cliente=CLUB, descuento_empleada=True))
        self.assertEqual(c.total, D("342.00"))
        self.assertIsNone(c.monedero)
        self.assertEqual(c.base_leal_total, D("0"))
        self.assertIn(M.EMPLEADA_SIN_MONEDERO, c.motivos_ticket)

    def test_r2_otra_persona_5_parejo_con_3pz(self) -> None:
        c = calcular(venta([self.f.linea("B3", "300", categoria="Deportivo", promo=True),
                            self.f.linea("P3", "150", categoria="Deportivo", promo=True)], descuento_empleada=True))
        self.assertEqual((c.total, c.descuento_total), (D("427.50"), D("22.50")))
        self.assertIn(M.OTRA_PERSONA_5, c.motivos_ticket)

    def test_redondeo_puede_bajar(self) -> None:
        c = calcular(venta([self.f.linea("PO1", "179")], descuento_empleada=True))
        self.assertEqual((c.descuento_total, c.total, c.redondeo), (D("8.95"), D("170.00"), D("-0.05")))
        self.assertEqual(c.lineas[0].parte_redondeo, D("-0.05"))


class OroSaldoYTarjetaTests(unittest.TestCase):
    def test_e12_saldo_y_tarjeta(self) -> None:
        """CAMBIA (regla B, 2026-11-12): con tarjeta el Monedero se gana sobre lo
        que deja la terminal: $413 − $18.50 de comisión = $394.50 → 5 % = $19.72."""
        c = calcular(venta([_Fabrica().linea("PO1", "150", 3)], cliente=CLUB, saldo_a_usar=D("37.42"),
                           saldo_disponible=D("37.42"), pago_tarjeta=True))
        self.assertEqual((c.saldo_usado, c.monedero.base, c.monedero.abono, c.neto_tienda),
                         (D("37.00"), D("394.50"), D("19.72"), D("394.50")))
        self.assertIn(M.MONEDERO_SIN_COMISION, c.motivos_ticket)
        self.assertEqual(sum(l.base_monedero for l in c.lineas), c.monedero.base)
        self.assertEqual(c.pagos, (Pago("tarjeta", D("413.00")), Pago("monedero", D("37.00"))))
        self.assertEqual(sum(l.comision_linea for l in c.lineas), c.comision_tarjeta)

    def test_canje_igual_al_de_hoy(self) -> None:
        rng = random.Random(5)
        for _ in range(1000):
            total = D(rng.randint(0, 200000)) / 100
            disp = D(rng.randint(0, 50000)) / 100
            deseado = rng.choice([None, D(rng.randint(0, 50000)) / 100])
            self.assertEqual(canje_ajustado(total, disp, deseado), mon.canje_ajustado(total, disp, deseado))

    def test_comision_igual_a_la_de_hoy(self) -> None:
        for centavos in range(0, 200001, 37):
            monto = D(centavos) / 100
            self.assertEqual(neto_con_comision(monto, D("4.5")), lib.aplicar_comision_terminal(monto))

    def test_t4_una_sola_vez_sobre_el_total(self) -> None:
        """CAMBIA (T4): el kiosko hoy da $430.50 (por pieza); el motor, $430.00, como la Libreta.
        CAMBIA (regla B): el Monedero se gana sobre esos $430, no sobre $450."""
        c = calcular(venta([_Fabrica().linea("PO1", "150", 3)], cliente=CLUB, pago_tarjeta=True))
        self.assertEqual((c.total, c.neto_tienda), (D("450.00"), D("430.00")))
        self.assertEqual(c.neto_tienda, lib.neto_de_cobro(D("450"), D("0"), True))
        self.assertEqual((c.monedero.base, c.monedero.abono), (D("430.00"), D("21.50")))
        self.assertIn(M.COMISION_UNICA, c.motivos_ticket)

    def test_pago_mixto_comision_solo_a_la_tarjeta(self) -> None:
        c = calcular(venta([_Fabrica().linea("PO1", "150", 3)],
                           pagos=(Pago("efectivo", D("200.00")), Pago("tarjeta", D("250.00")))))
        self.assertEqual(c.comision_tarjeta, D("250.00") - lib.aplicar_comision_terminal(D("250")))
        self.assertEqual(c.neto_tienda, D("450.00") - c.comision_tarjeta)

    def test_c2_saldo_y_rebajas_en_proporcion(self) -> None:
        """CAMBIA (C2): hoy base $80 y abono $4.00 (D5); en proporción, base $147.57 y abono $7.37."""
        f = _Fabrica()
        c = calcular(venta([f.linea("PL2", "250", categoria="Uniformes", oferta="175"),
                            f.linea("SL1", "300", categoria="Ropa casual", liquidacion="200"),
                            f.linea("PO1", "180")], cliente=CLUB, saldo_a_usar=D("100"), saldo_disponible=D("100")))
        partes = {l.sku: l.parte_saldo for l in c.lineas}
        self.assertEqual(partes, {"PL2": D("31.53"), "SL1": D("36.04"), "PO1": D("32.43")})
        self.assertEqual((c.monedero.base, c.monedero.abono), (D("147.57"), D("7.37")))

    def test_c2_leal_sin_saldo_sin_rebajas_y_3pz_cuenta(self) -> None:
        f = _Fabrica()
        c = calcular(venta([f.linea("PO1", "180"), f.linea("PL2", "250", categoria="Uniformes", oferta="175"),
                            f.linea("B3", "300", categoria="Deportivo", promo=True)],
                           cliente=CLUB, saldo_a_usar=D("100"), saldo_disponible=D("100")))
        esperado = sum((l.cobrado - l.parte_saldo for l in c.lineas if l.clasificacion_al_vender != "oferta"), D("0"))
        self.assertEqual(c.base_leal_total, esperado)
        self.assertLess(c.base_leal_total, c.total - c.saldo_usado)

    def test_saldo_sin_cliente_es_invalido(self) -> None:
        with self.assertRaises(EntradaInvalida):
            calcular(venta([_Fabrica().linea("PO1", "180")], saldo_a_usar=D("10"), saldo_disponible=D("10")))


class SinConexionC12Tests(unittest.TestCase):
    def test_sin_conexion_la_venta_no_se_anota_con_descuento(self) -> None:
        """Revisión de deuda, 2026-11-12: el Mayorista que eligió descuento y
        compró sin conexión pagaba precio completo y, como la venta decía
        «descuento_programa», el servidor tampoco le abonaba Monedero."""
        from pos_uniformes.services.beneficios_carrito import descuento_programa_a_guardar

        f = _Fabrica()
        sin = calcular(venta([f.linea("PO1", "180")], cliente=MAYORISTA, modalidad_mayorista="descuento",
                             origen_calculo="kiosko_sin_conexion"))
        con = calcular(venta([f.linea("PO1", "180")], cliente=MAYORISTA, modalidad_mayorista="descuento"))
        self.assertIsNone(descuento_programa_a_guardar(D("15"), sin))
        self.assertEqual(descuento_programa_a_guardar(D("15"), con), D("15"))
        self.assertEqual(descuento_programa_a_guardar(D("15"), None), D("15"))   # cálculo de respaldo
        self.assertIsNone(descuento_programa_a_guardar(None, con))

    def test_sin_mayoreo_sin_saldo_y_empleada_al_base(self) -> None:
        f = _Fabrica()
        c = calcular(venta([f.linea("PO1", "180", 2)], cliente=MAYORISTA, modalidad_mayorista="descuento",
                           saldo_a_usar=D("50"), saldo_disponible=D("50"), origen_calculo="kiosko_sin_conexion"))
        self.assertEqual((c.total, c.saldo_usado, c.descuento_aplicado), (D("360.00"), D("0"), False))
        self.assertIn(M.SIN_CONEXION_SIN_MAYOREO, c.motivos_ticket)
        self.assertIn(M.SIN_CONEXION_SIN_SALDO, c.motivos_ticket)
        e = calcular(venta([f.linea("SC1", "400", categoria="Ropa casual")], origen_calculo="kiosko_sin_conexion",
                           **con_nivel("20", "3000")))
        self.assertEqual(e.total, D("380.00"))
        self.assertIn(M.SIN_CONEXION_EMPLEADA_BASE, e.motivos_ticket)


# ═══ 3. Propiedades ══════════════════════════════════════════════════════


CATALOGO = [
    ("PO1", "180", "Oficial"), ("PO2", "179", "Oficial"), ("PA1", "250", "Uniformes"), ("SC1", "400", "Ropa casual"),
    ("SC2", "233", "Temporada"), ("AC1", "59", "Accesorio"), ("AC2", "12.90", "Accesorio"), ("CH1", "280", "Ropa casual"),
    ("DE1", "157", "Deportivo"), ("BA1", "96", "Básico"), ("EX1", "85", ""), ("TE1", "63", "Temporada"),
]


def _carrito_aleatorio(rng: random.Random, *, repetir_sku=True):
    lineas = []
    usados = set()
    for _ in range(rng.randint(1, 8)):
        sku, precio, cat = rng.choice(CATALOGO)
        if not repetir_sku and sku in usados:
            continue
        usados.add(sku)
        tipo = rng.random()
        kw = {}
        if tipo < 0.12:
            kw["oferta"] = format((D(precio) * D("0.7")).quantize(D("1")), "f")
        elif tipo < 0.18:
            kw["liquidacion"] = format((D(precio) * D("0.5")).quantize(D("1")), "f")
        elif tipo < 0.28:
            kw["promo"] = True
        lineas.append(LineaEntrada(str(uuid.UUID(int=rng.getrandbits(128))), sku, rng.randint(1, 3), D(precio),
                                   cat, Rebaja("oferta", D(kw["oferta"])) if "oferta" in kw else
                                   Rebaja("liquidacion", D(kw["liquidacion"])) if "liquidacion" in kw else None,
                                   bool(kw.get("promo"))))
    return lineas


def _contexto_aleatorio(rng: random.Random) -> dict:
    caso = rng.randint(0, 6)
    if caso == 0:
        return {}
    if caso == 1:
        return dict(cliente=CLUB, saldo_a_usar=D(rng.randint(0, 300)), saldo_disponible=D(rng.randint(0, 300)))
    if caso == 2:
        return dict(cliente=MAYORISTA, modalidad_mayorista=rng.choice(["descuento", "monedero"]))
    if caso == 3:
        return dict(descuento_empleada=True)
    if caso == 4:
        return con_nivel(rng.choice(["10", "15", "20"]), rng.choice([None, "0", "300", "1000", "3000"]))
    if caso == 5:
        return dict(cliente=LEAL, pago_tarjeta=True)
    return dict(cliente=MAYORISTA, modalidad_mayorista="descuento", **con_nivel("20", "500"))


class PropiedadesTests(unittest.TestCase):
    N = 600

    def test_invariantes(self) -> None:
        rng = random.Random(2026)
        for _ in range(self.N):
            entrada = venta(_carrito_aleatorio(rng), **_contexto_aleatorio(rng))
            c = calcular(entrada)
            with self.subTest(entrada=entrada):
                self.assertEqual(sum(l.cobrado for l in c.lineas), c.total)
                self.assertEqual(sum(l.parte_redondeo for l in c.lineas), c.redondeo)
                self.assertEqual(sum(l.parte_saldo for l in c.lineas), c.saldo_usado)
                self.assertEqual(sum(l.comision_linea for l in c.lineas), c.comision_tarjeta)
                self.assertEqual(sum(p.importe for p in c.pagos), c.total)
                self.assertEqual(c.total, redondeo_tienda(c.total_antes_redondeo))
                self.assertTrue(all(l.cobrado >= 0 and l.parte_saldo <= l.cobrado for l in c.lineas))
                if c.monedero:
                    self.assertEqual(sum(l.abono_linea for l in c.lineas), c.monedero.abono)
                    self.assertFalse(c.descuento_aplicado)       # nunca mayoreo y abono a la vez (C4)
                for l in c.lineas:
                    if M.REDONDEO_EXCEPCION_D2 not in l.motivos:
                        self.assertLessEqual(l.cobrado, (l.precio_lista * l.cantidad))
                    if l.clasificacion_al_vender in ("oferta", "liquidacion"):
                        self.assertEqual((l.base_monedero, l.base_leal, l.descuento.importe), (0, 0, 0))
                comp = entrada.compradora
                if comp is not None and comp.restante_tope is not None:
                    self.assertLessEqual(c.consumo_tope_total, max(comp.restante_tope, D("0")))

    def test_el_orden_de_captura_no_cambia_nada(self) -> None:
        rng = random.Random(77)
        for _ in range(self.N):
            lineas = _carrito_aleatorio(rng)
            ctx = _contexto_aleatorio(rng)
            base = fotografia(venta(lineas, **ctx), calcular(venta(lineas, **ctx)))["calculo"]
            for _ in range(3):
                otra = list(lineas)
                rng.shuffle(otra)
                self.assertEqual(fotografia(venta(otra, **ctx), calcular(venta(otra, **ctx)))["calculo"], base)

    def test_agrupar_o_separar_no_cambia_el_resultado(self) -> None:
        """Q6/C9: «n × X» y n líneas de «1 × X» dan lo mismo."""
        rng = random.Random(99)
        for _ in range(300):
            lineas = _carrito_aleatorio(rng, repetir_sku=False)
            ctx = _contexto_aleatorio(rng)
            separadas = []
            for l in lineas:
                for k in range(l.cantidad):
                    separadas.append(LineaEntrada(str(uuid.UUID(int=rng.getrandbits(128))), l.sku, 1, l.precio_lista,
                                                  l.categoria, l.rebaja, l.promo_3pz))
            a, b = calcular(venta(lineas, **ctx)), calcular(venta(separadas, **ctx))
            for campo in ("total", "descuento_total", "saldo_usado", "comision_tarjeta", "base_leal_total",
                          "consumo_tope_total"):
                self.assertEqual(getattr(a, campo), getattr(b, campo), campo)
            self.assertEqual(a.monedero, b.monedero)
            self.assertEqual({l.sku: l.cobrado for l in a.lineas}, {l.sku: l.cobrado for l in b.lineas})


class EquivalenciaConElKioskoTests(unittest.TestCase):
    """Donde ninguna regla aprobada cambia el total, el motor cobra lo mismo que hoy."""

    def _total_de_hoy(self, lineas, ctx) -> Decimal:
        items = []
        for l in lineas:
            it = {"sku": l.sku, "precio": l.precio_lista, "cantidad": l.cantidad, "categoria": l.categoria}
            if l.promo_3pz:
                it["promo_3pz"] = True
            if l.rebaja is not None:
                reb.aplicar(it, reb.RebajaVigente(l.sku, l.rebaja.tipo, l.rebaja.precio, l.precio_lista, None))
            items.append(it)
        subtotal = sum((it["precio"] * it["cantidad"] for it in items), D("0"))
        programa = MAYORISTA.pct_mayoreo if ctx.get("modalidad_mayorista") == "descuento" else None
        empleada = ctx.get("descuento_empleada", False)
        if programa or (empleada and any(reb.es_rebajado(it) for it in items)):
            desc = dps.descuento(items, empleada=(D("5") if empleada else None), programa=programa)
        elif empleada:
            desc = (subtotal * D("5") / D("100")).quantize(D("0.01"))
        else:
            desc = D("0.00")
        return resolve_sale_rounding(subtotal - desc).collected_total

    def test_total_igual_en_carritos_aleatorios(self) -> None:
        rng = random.Random(4242)
        revisados = 0
        for _ in range(1500):
            lineas = _carrito_aleatorio(rng, repetir_sku=False)
            ctx = rng.choice([{}, dict(cliente=CLUB), dict(cliente=MAYORISTA, modalidad_mayorista="descuento"),
                              dict(cliente=MAYORISTA, modalidad_mayorista="monedero"), dict(descuento_empleada=True),
                              dict(cliente=MAYORISTA, modalidad_mayorista="descuento", descuento_empleada=True)])
            self.assertEqual(calcular(venta(lineas, **ctx)).total, self._total_de_hoy(lineas, ctx), (lineas, ctx))
            revisados += 1
        self.assertEqual(revisados, 1500)

    def test_abono_igual_sin_saldo(self) -> None:
        """Sin saldo, sin rebajas y sin redondeo repartido, el abono es el de hoy."""
        rng = random.Random(8)
        for _ in range(500):
            lineas = [l for l in _carrito_aleatorio(rng, repetir_sku=False) if l.rebaja is None]
            if not lineas:
                continue
            c = calcular(venta(lineas, cliente=LEAL))
            self.assertEqual(c.monedero.abono, mon.calcular_cashback(c.total, D("10")))

    def test_tope_igual_a_hoy_con_una_sola_linea_candidata(self) -> None:
        for precio, restante in (("400", "300"), ("280", "300"), ("100", "300"), ("400", None)):
            item = {"sku": "SC1", "precio": D(precio), "cantidad": 1, "categoria": "Ropa casual"}
            hoy = inc.repartir([item], pct_nivel=D("20"), restante=None if restante is None else D(restante))
            c = calcular(venta([_Fabrica().linea("SC1", precio, categoria="Ropa casual")], **con_nivel("20", restante)))
            self.assertEqual(c.lineas[0].descuento.pct, hoy[0])


# ═══ 4. Fotografía (T2) ══════════════════════════════════════════════════


class FotografiaTests(unittest.TestCase):
    def _entrada(self):
        f = _Fabrica()
        return venta([f.linea("PO1", "179"), f.linea("PL2", "250", categoria="Uniformes", oferta="175")],
                     cliente=CLUB, saldo_a_usar=D("20"), saldo_disponible=D("20"), pago_tarjeta=True, vendedora="VEND-2")

    def test_reproducible(self) -> None:
        e = self._entrada()
        a, b = fotografia(e, calcular(e)), fotografia(e, calcular(e))
        self.assertEqual(a_json(a), a_json(b))
        self.assertEqual(huella(a), huella(b))
        self.assertEqual(a["version_motor"], VERSION_MOTOR)
        self.assertEqual(a["version_reglas"], "2026-11-12")

    def test_importes_como_texto_y_campos_de_d6(self) -> None:
        e = self._entrada()
        foto = fotografia(e, calcular(e))
        self.assertIsInstance(foto["calculo"]["total"], str)
        for campo in ("linea_uid", "comision_linea"):
            self.assertIn(campo, foto["calculo"]["lineas"][0])
        for campo in ("vendedora", "fecha_venta", "origen_calculo", "pagos"):
            self.assertIn(campo, foto["calculo"])
        self.assertIn("pagos", foto["entrada"])

    def test_cambia_si_cambia_la_entrada(self) -> None:
        e = self._entrada()
        otra = venta(e.lineas, cliente=LEAL, saldo_a_usar=D("20"), saldo_disponible=D("20"), pago_tarjeta=True)
        self.assertNotEqual(huella(fotografia(e, calcular(e))), huella(fotografia(otra, calcular(otra))))

    def test_el_sku_no_se_modifica(self) -> None:
        e = venta([LineaEntrada(uid(1), " sku-raro ", 1, D("100"))])
        self.assertEqual(calcular(e).lineas[0].sku, " sku-raro ")


# ═══ 5. Validación y pureza ══════════════════════════════════════════════


class ValidacionTests(unittest.TestCase):
    def test_entradas_invalidas(self) -> None:
        bien = LineaEntrada(uid(1), "A", 1, D("100"))
        casos = {
            "sin líneas": venta([]),
            "float": venta([LineaEntrada(uid(1), "A", 1, 100.0)]),
            "fracción de centavo": venta([LineaEntrada(uid(1), "A", 1, D("100.001"))]),
            "uid repetido": venta([bien, LineaEntrada(uid(1), "B", 1, D("10"))]),
            "uid inválido": venta([LineaEntrada("no-uuid", "A", 1, D("10"))]),
            "cantidad cero": venta([LineaEntrada(uid(1), "A", 0, D("10"))]),
            "rebaja de $0": venta([LineaEntrada(uid(1), "A", 1, D("10"), rebaja=Rebaja("oferta", D("0")))]),
            "compradora sin descuento": venta([bien], compradora=CompradoraCtx("V", D("20"), None)),
            "modalidad rara": venta([bien], modalidad_mayorista="regalo"),
            "origen raro": venta([bien], origen_calculo="nube"),
            "pagos que no cuadran": venta([bien], pagos=(Pago("efectivo", D("10")),)),
            "saldo como pago": venta([bien], pagos=(Pago("monedero", D("100")),)),
        }
        for nombre, entrada in casos.items():
            with self.subTest(nombre):
                with self.assertRaises(EntradaInvalida):
                    calcular(entrada)


class PurezaTests(unittest.TestCase):
    CARPETA = Path(__file__).resolve().parents[1] / "services" / "beneficios"
    PROHIBIDOS = ("sqlalchemy", "PyQt6", "requests", "socket", "os", "random", "time", "subprocess",
                  "pos_uniformes.database", "pos_uniformes.ui")

    def test_no_importa_base_qt_red_ni_azar(self) -> None:
        for archivo in self.CARPETA.glob("*.py"):
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                nombres = []
                if isinstance(nodo, ast.Import):
                    nombres = [a.name for a in nodo.names]
                elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                    nombres = [nodo.module]
                for n in nombres:
                    with self.subTest(archivo=archivo.name, modulo=n):
                        self.assertFalse(any(n == p or n.startswith(p + ".") for p in self.PROHIBIDOS))
                        if n.startswith("pos_uniformes"):
                            self.assertTrue(n.startswith("pos_uniformes.services.beneficios"), n)

    def test_no_usa_el_reloj(self) -> None:
        for archivo in self.CARPETA.glob("*.py"):
            texto = archivo.read_text(encoding="utf-8")
            for prohibido in ("datetime.now", "date.today", "time.time", "uuid4("):
                self.assertNotIn(prohibido, texto, archivo.name)

    def test_importar_el_motor_no_carga_base_ni_qt(self) -> None:
        codigo = ("import sys, pos_uniformes.services.beneficios\n"
                  "print(sorted(m for m in sys.modules if m.split('.')[0] in ('sqlalchemy', 'PyQt6')))")
        raiz = Path(__file__).resolve().parents[2]
        salida = subprocess.run([sys.executable, "-c", codigo], cwd=raiz, capture_output=True, text=True, check=True)
        self.assertEqual(salida.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
