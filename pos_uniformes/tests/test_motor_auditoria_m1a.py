"""Auditoría de salida de M1a (Daniel, 2026-11-11).

Pruebas reproducibles de lo que revisó la auditoría:
- los cinco ejemplos económicos del informe M1a, con la cifra de hoy calculada
  con las funciones actuales y la del motor, línea por línea y con motivos;
- agrupación de líneas del mismo SKU (Q6, P3, Q2, I5, I8) y el centavo que
  hoy aparece al capturar por separado;
- trazabilidad cuando el mayoreo le gana a la empleada (corrección de la
  auditoría: `piezas_al_base` y el motivo EMPLEADA_BASE);
- las reglas del motor siguen a las del código de hoy (fuente única) y no
  cambian sin cambiar su versión;
- campos del contrato D6 y el modo sin conexión (C12, igual que el kiosko).

Puro: no toca base, Qt, red ni producción.
"""

from __future__ import annotations

import dataclasses
import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from pos_uniformes.services import incentivo_empleada_service as inc
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services.beneficios import motivos as M
from pos_uniformes.services.beneficios.contrato import (
    Calculo,
    ClienteCtx,
    CompradoraCtx,
    EntradaInvalida,
    EntradaVenta,
    LineaCalculo,
    LineaEntrada,
    Pago,
    Rebaja,
    ReglasCtx,
    SkuConCategoriasIncompatibles,
)
from pos_uniformes.services.beneficios.fotografia import fotografia, huella
from pos_uniformes.services.beneficios.motor import calcular
from pos_uniformes.services.fidelizacion import descuento_programa_service as dps
from pos_uniformes.services.sale_rounding_service import resolve_sale_rounding

D = Decimal
FECHA = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
CLUB = ClienteCtx(9, "CLUB", D("5"), None)
MAYORISTA = ClienteCtx(9, "MAYORISTA", D("15"), D("15"))


def uid(n: int) -> str:
    return str(uuid.UUID(int=n))


def venta(lineas, **kw) -> EntradaVenta:
    return EntradaVenta(tuple(lineas), FECHA, **kw)


def con_nivel(pct, restante) -> dict:
    return dict(descuento_empleada=True, compradora=CompradoraCtx("VEND-3", D(pct), D(restante)))


def _total_de_hoy_empleada(items, pct_nivel, restante) -> Decimal:
    """Hoy: `repartir` en el orden de captura y `dps.descuento` por renglón."""
    items = [dict(it) for it in items]
    for it, pct in zip(items, inc.repartir(items, pct_nivel=D(pct_nivel), restante=D(restante))):
        it[inc.LLAVE_PCT] = pct
    subtotal = sum((it["precio"] * it["cantidad"] for it in items), D("0"))
    return resolve_sale_rounding(subtotal - dps.descuento(items, empleada=D("5"))).collected_total


# ═══ 7. Los cinco ejemplos económicos del informe M1a ═══════════════════


class EjemplosEconomicosTests(unittest.TestCase):
    def test_c8_461_50_contra_466(self) -> None:
        """Nivel 20 %, tope $300, chamarra $280 y sudadera $250 (Ropa casual).

        Motor: la de $280 entra al tope (280 ≤ 300) → 20 % = $56; la de $250 ya
        no cabe (quedan $20) → 5 % = $12.50. 530 − 68.50 = $461.50 en cualquier orden.
        Hoy: con la sudadera primero, entra ella (250 ≤ 300) → $50, y la chamarra
        al 5 % → $14. 530 − 64 = $466."""
        ch = {"sku": "CH1", "precio": D("280"), "cantidad": 1, "categoria": "Ropa casual"}
        su = {"sku": "SU1", "precio": D("250"), "cantidad": 1, "categoria": "Ropa casual"}
        self.assertEqual(_total_de_hoy_empleada([ch, su], "20", "300"), D("461.50"))
        self.assertEqual(_total_de_hoy_empleada([su, ch], "20", "300"), D("466.00"))
        a = LineaEntrada(uid(1), "CH1", 1, D("280"), "Ropa casual")
        b = LineaEntrada(uid(2), "SU1", 1, D("250"), "Ropa casual")
        for orden in ([a, b], [b, a]):
            c = calcular(venta(orden, **con_nivel("20", "300")))
            self.assertEqual((c.total, c.descuento_total, c.consumo_tope_total), (D("461.50"), D("68.50"), D("280.00")))
            ch1, su1 = c.lineas
            self.assertEqual((ch1.sku, ch1.descuento.importe, ch1.piezas_con_nivel, ch1.cobrado), ("CH1", D("56.00"), 1, D("224.00")))
            self.assertEqual((su1.sku, su1.descuento.importe, su1.piezas_al_base, su1.cobrado), ("SU1", D("12.50"), 1, D("237.50")))
            self.assertIn(M.EMPLEADA_NIVEL, ch1.motivos)
            self.assertIn(M.TOPE_MES_AGOTADO, su1.motivos)

    def test_c9_342_contra_315(self) -> None:
        """«2 × $180» casual, nivel 20 %, tope $300.

        Hoy: el renglón completo ($360) no cabe → todo al 5 % = $18 → $342.
        Motor, por pieza: una cabe (180 ≤ 300) → $36; la otra no (quedan $120)
        → $9. 360 − 45 = $315."""
        hoy = _total_de_hoy_empleada([{"sku": "A", "precio": D("180"), "cantidad": 2, "categoria": "Ropa casual"}], "20", "300")
        self.assertEqual(hoy, D("342.00"))
        c = calcular(venta([LineaEntrada(uid(1), "A", 2, D("180"), "Ropa casual")], **con_nivel("20", "300")))
        [l] = c.lineas
        self.assertEqual((c.total, l.descuento.importe, l.piezas_con_nivel, l.piezas_al_base, l.consumo_tope),
                         (D("315.00"), D("45.00"), 1, 1, D("180.00")))
        self.assertEqual(l.motivos, (M.EMPLEADA_NIVEL, M.TOPE_MES_AGOTADO))

    def test_t4_430_50_contra_430_00(self) -> None:
        """3 × $150 con tarjeta.

        Hoy, el kiosko por pieza: R1(150 × 0.955 = 143.25) = $143.50 × 3 = $430.50.
        Motor (y hoy la Libreta): R1(450 × 0.955 = 429.75) = $430.00; comisión $20."""
        self.assertEqual(sum(lib.aplicar_comision_terminal(D("150")) for _ in range(3)), D("430.50"))
        self.assertEqual(lib.neto_de_cobro(D("450"), D("0"), True), D("430.00"))
        c = calcular(venta([LineaEntrada(uid(1), "PO1", 3, D("150"))], cliente=CLUB, pago_tarjeta=True))
        self.assertEqual((c.neto_tienda, c.comision_tarjeta, c.lineas[0].comision_linea), (D("430.00"), D("20.00"), D("20.00")))
        self.assertEqual(c.pagos, (Pago("tarjeta", D("450.00")),))
        self.assertIn(M.COMISION_UNICA, c.motivos_ticket)

    def test_c2_4_00_contra_7_37(self) -> None:
        """Pants en Oferta $175, sudadera en Liquidación $200, playera $180; saldo $100; CLUB 5 %.

        Hoy: base = max(555 − 100 − 375, 0) = $80 → abono $4.00 (todo el saldo
        se descuenta de lo no rebajado).
        Motor: el saldo se reparte en proporción a lo cobrado (Q2):
        100 × 175/555 = 31.53, 100 × 180/555 = 32.43, 100 × 200/555 = 36.04
        (el centavo sobrante va al mayor residuo). Base = 180 − 32.43 = $147.57;
        abono = trunc(147.57 × 5 %) = $7.37."""
        hoy_base = max(D("555") - D("100") - D("375"), D("0"))
        self.assertEqual((hoy_base * D("5") / 100).quantize(D("0.01")), D("4.00"))
        c = calcular(venta([LineaEntrada(uid(1), "PL2", 1, D("250"), "Uniformes", Rebaja("oferta", D("175"))),
                            LineaEntrada(uid(2), "SL1", 1, D("300"), "Ropa casual", Rebaja("liquidacion", D("200"))),
                            LineaEntrada(uid(3), "PO1", 1, D("180"))],
                           cliente=CLUB, saldo_a_usar=D("100"), saldo_disponible=D("100")))
        por_sku = {l.sku: l for l in c.lineas}
        self.assertEqual({s: l.parte_saldo for s, l in por_sku.items()},
                         {"PL2": D("31.53"), "PO1": D("32.43"), "SL1": D("36.04")})
        self.assertEqual({s: l.base_monedero for s, l in por_sku.items()},
                         {"PL2": D("0.00"), "PO1": D("147.57"), "SL1": D("0.00")})
        self.assertEqual((c.monedero.base, c.monedero.abono, por_sku["PO1"].abono_linea), (D("147.57"), D("7.37"), D("7.37")))
        self.assertIn(M.REBAJA_SIN_OTRO_BENEFICIO, por_sku["PL2"].motivos)
        self.assertIn(M.SALDO_REPARTIDO, por_sku["PO1"].motivos)

    def test_c4_mayorista_descuento_de_cero(self) -> None:
        """Mayorista elige «descuento» y solo lleva 3pz: el mayoreo no aplica a la 3pz.

        Hoy: la venta queda marcada con el 15 % aunque no se descontó nada.
        Motor: total $450, descuento $0, descuento_aplicado = False, la modalidad
        sigue siendo «descuento» y no hay abono (C4)."""
        c = calcular(venta([LineaEntrada(uid(1), "B3", 1, D("300"), "Deportivo", promo_3pz=True),
                            LineaEntrada(uid(2), "P3", 1, D("150"), "Deportivo", promo_3pz=True)],
                           cliente=MAYORISTA, modalidad_mayorista="descuento"))
        self.assertEqual((c.total, c.descuento_total, c.descuento_aplicado, c.modalidad_mayorista_elegida, c.monedero),
                         (D("450.00"), D("0.00"), False, "descuento", None))
        self.assertEqual(c.motivos_ticket, (M.MAYOREO_SIN_LINEAS_ELEGIBLES, M.MAYOREO_SIN_MONEDERO))
        self.assertTrue(all(l.motivos == (M.TRES_PZ_SIN_MAYOREO,) for l in c.lineas))


# ═══ 3. Agrupación de líneas y centavos ══════════════════════════════════


class AgrupacionAuditoriaTests(unittest.TestCase):
    """$12.90 con mayoreo 15 %: 1.935 por pieza, el caso que mueve centavos."""

    MAY = dict(cliente=MAYORISTA, modalidad_mayorista="descuento")

    def test_una_linea_varias_lineas_y_mezcla_dan_lo_mismo(self) -> None:
        una = calcular(venta([LineaEntrada(uid(1), "AC2", 3, D("12.90"))], **self.MAY))
        tres = calcular(venta([LineaEntrada(uid(i), "AC2", 1, D("12.90")) for i in (3, 1, 2)], **self.MAY))
        mezcla = calcular(venta([LineaEntrada(uid(2), "AC2", 1, D("12.90")), LineaEntrada(uid(1), "AC2", 2, D("12.90"))], **self.MAY))
        for c in (una, tres, mezcla):
            [l] = c.lineas
            # q(38.70 × 15 %) = q(5.805) = 5.80 (mitad al par); 32.90 → R1 → 33.00
            self.assertEqual((c.total, l.descuento.importe, l.parte_redondeo, l.cantidad), (D("33.00"), D("5.80"), D("0.10"), 3))
        # Trazabilidad (P3, D1): cada pieza conserva su línea original.
        self.assertEqual(una.lineas[0].lineas_origen, ((uid(1), 3),))
        self.assertEqual(tres.lineas[0].lineas_origen, ((uid(1), 1), (uid(2), 1), (uid(3), 1)))
        self.assertEqual(mezcla.lineas[0].lineas_origen, ((uid(1), 2), (uid(2), 1)))
        self.assertIn(M.LINEAS_AGRUPADAS, tres.lineas[0].motivos)
        self.assertNotIn(M.LINEAS_AGRUPADAS, una.lineas[0].motivos)

    def test_hoy_capturar_por_separado_mueve_el_centavo(self) -> None:
        """Hoy se redondea renglón por renglón: 3 × q(1.935) = 5.82 contra q(5.805) = 5.80."""
        una = [{"sku": "AC2", "precio": D("12.90"), "cantidad": 3}]
        tres = [{"sku": "AC2", "precio": D("12.90"), "cantidad": 1}] * 3
        self.assertEqual(dps.descuento(una, programa=D("15")), D("5.80"))
        self.assertEqual(dps.descuento(tres, programa=D("15")), D("5.82"))

    def test_mismo_sku_con_condiciones_distintas_no_se_agrupa_y_no_depende_del_orden(self) -> None:
        lineas = [LineaEntrada(uid(1), "PO1", 1, D("180")),
                  LineaEntrada(uid(2), "PO1", 1, D("180"), rebaja=Rebaja("oferta", D("150"))),
                  LineaEntrada(uid(3), "PO1", 1, D("180"), promo_3pz=True),
                  # A2: la categoría distinta ya no es una condición válida (ver A2Tests);
                  # la cuarta variante es ahora una Liquidación.
                  LineaEntrada(uid(4), "PO1", 1, D("180"), rebaja=Rebaja("liquidacion", D("90")))]
        a, b = calcular(venta(lineas, **self.MAY)), calcular(venta(lineas[::-1], **self.MAY))
        self.assertEqual(a, b)
        self.assertEqual([l.linea_uid for l in a.lineas], [uid(1), uid(2), uid(3), uid(4)])
        self.assertEqual([l.descuento.importe for l in a.lineas], [D("27.00"), D("0.00"), D("0.00"), D("0.00")])
        self.assertEqual([l.clasificacion_al_vender for l in a.lineas], ["normal", "oferta", "3pz", "liquidacion"])
        self.assertTrue(all(len(l.lineas_origen) == 1 for l in a.lineas))

    def test_tope_con_nivel_agrupado_o_separado(self) -> None:
        """Nivel 20 %, tope $15: cabe una pieza de $12.90. q(2.58) + q(25.80 × 5 % = 1.29) = 3.87."""
        kw = con_nivel("20", "15")
        una = calcular(venta([LineaEntrada(uid(1), "AC2", 3, D("12.90"), "Accesorio")], **kw))
        tres = calcular(venta([LineaEntrada(uid(i), "AC2", 1, D("12.90"), "Accesorio") for i in (1, 2, 3)], **kw))
        for c in (una, tres):
            [l] = c.lineas
            self.assertEqual((c.total, l.descuento.importe, l.piezas_con_nivel, l.piezas_al_base), (D("35.00"), D("3.87"), 1, 2))



# ═══ A2: SKU con categorías incompatibles (decisión de Daniel, 11/11) ════


class A2Tests(unittest.TestCase):
    """Antes de A2 el tope lo tomaba la línea de uid menor y el total salía $333 o
    $315 según un uid aleatorio. Ahora la entrada se rechaza y se conserva todo
    para investigar; ningún importe se calcula ni se elige categoría."""

    KW = con_nivel("20", "180")

    def _rechazo(self, lineas, **kw) -> SkuConCategoriasIncompatibles:
        with self.assertRaises(SkuConCategoriasIncompatibles) as ctx:
            calcular(venta(lineas, **(kw or self.KW)))
        return ctx.exception

    def test_rechaza_e_identifica_sku_y_lineas(self) -> None:
        e = self._rechazo([LineaEntrada(uid(2), "PO1", 1, D("180"), "Oficial"),
                           LineaEntrada(uid(1), "PO1", 1, D("180"), "Ropa casual")])
        self.assertIsInstance(e, EntradaInvalida)
        self.assertEqual(e.codigo, M.SKU_CATEGORIAS_INCOMPATIBLES)
        self.assertEqual(e.conflictos, (("PO1", ((uid(1), "Ropa casual"), (uid(2), "Oficial"))),))
        for texto in ("PO1", uid(1), uid(2), "Oficial", "Ropa casual"):
            self.assertIn(texto, str(e))

    def test_no_depende_del_uid_ni_del_orden(self) -> None:
        """Los dos casos que antes daban $333 y $315 ahora dan el mismo rechazo."""
        a = self._rechazo([LineaEntrada(uid(1), "PO1", 1, D("180"), "Oficial"),
                           LineaEntrada(uid(2), "PO1", 1, D("180"), "Ropa casual")])
        b = self._rechazo([LineaEntrada(uid(2), "PO1", 1, D("180"), "Ropa casual"),
                           LineaEntrada(uid(1), "PO1", 1, D("180"), "Oficial")])
        self.assertEqual(a.conflictos, b.conflictos)

    def test_no_normaliza_la_categoria(self) -> None:
        """Se compara como llegó: vacío contra nombre, o mayúsculas distintas, también es incompatible."""
        for otra in ("", "ropa casual", "Ropa  casual"):
            e = self._rechazo([LineaEntrada(uid(1), "SC1", 1, D("400"), "Ropa casual"),
                               LineaEntrada(uid(2), "SC1", 1, D("400"), otra)])
            self.assertEqual(e.conflictos, (("SC1", ((uid(1), "Ropa casual"), (uid(2), otra))),))

    def test_reporta_todos_los_sku_en_conflicto_y_todas_sus_lineas(self) -> None:
        e = self._rechazo([LineaEntrada(uid(1), "B", 1, D("10"), "Oficial"), LineaEntrada(uid(2), "B", 2, D("10"), "Temporada"),
                           LineaEntrada(uid(3), "B", 1, D("10"), "Oficial"), LineaEntrada(uid(4), "A", 1, D("10"), "Accesorio"),
                           LineaEntrada(uid(5), "A", 1, D("10"), ""), LineaEntrada(uid(6), "C", 1, D("10"), "Oficial")])
        self.assertEqual(e.conflictos, (
            ("A", ((uid(4), "Accesorio"), (uid(5), ""))),
            ("B", ((uid(1), "Oficial"), (uid(2), "Temporada"), (uid(3), "Oficial"))),
        ))

    def test_rechaza_en_cualquier_contexto(self) -> None:
        lineas = [LineaEntrada(uid(1), "PO1", 1, D("180"), "Oficial"), LineaEntrada(uid(2), "PO1", 1, D("180"), "Deportivo")]
        for kw in ({}, dict(cliente=CLUB), dict(cliente=MAYORISTA, modalidad_mayorista="descuento"),
                   dict(origen_calculo="kiosko_sin_conexion"), dict(descuento_empleada=True)):
            with self.subTest(kw=kw), self.assertRaises(SkuConCategoriasIncompatibles):
                calcular(venta(lineas, **kw))

    def test_lo_valido_sigue_pasando(self) -> None:
        mismo = calcular(venta([LineaEntrada(uid(1), "PO1", 1, D("180"), "Oficial"),
                                LineaEntrada(uid(2), "PO1", 1, D("180"), "Oficial")], **self.KW))
        self.assertEqual(len(mismo.lineas), 1)
        sin_sku = calcular(venta([LineaEntrada(uid(1), None, 1, D("180"), "Oficial"),
                                  LineaEntrada(uid(2), None, 1, D("180"), "Ropa casual")], **self.KW))
        self.assertEqual(len(sin_sku.lineas), 2)


# ═══ Corrección: trazabilidad cuando gana el mayoreo ═════════════════════


class TrazabilidadMayoreoTests(unittest.TestCase):
    def test_empate_gana_el_mayoreo_y_la_pieza_no_queda_al_base(self) -> None:
        c = calcular(venta([LineaEntrada(uid(1), "SC1", 1, D("200"), "Ropa casual")],
                           cliente=MAYORISTA, modalidad_mayorista="descuento", **con_nivel("15", "300")))
        [l] = c.lineas
        self.assertEqual((c.total, l.descuento.fuente, l.descuento.importe), (D("170.00"), "mayoreo", D("30.00")))
        self.assertEqual((l.piezas_con_nivel, l.piezas_al_base, l.consumo_tope), (0, 0, D("0.00")))
        self.assertNotIn(M.EMPLEADA_BASE, l.motivos)
        self.assertIn(M.GANA_MAYOREO, l.motivos)

    def test_empleada_sin_nivel_con_mayoreo_no_dice_empleada_base(self) -> None:
        c = calcular(venta([LineaEntrada(uid(1), "PO1", 2, D("180"))], cliente=MAYORISTA, modalidad_mayorista="descuento",
                           descuento_empleada=True, compradora=CompradoraCtx("VEND-3", None, None)))
        [l] = c.lineas
        self.assertEqual((l.descuento.fuente, l.piezas_al_base), ("mayoreo", 0))
        self.assertNotIn(M.EMPLEADA_BASE, l.motivos)

    def test_cuando_la_empleada_si_queda_al_base_se_dice(self) -> None:
        c = calcular(venta([LineaEntrada(uid(1), "PO1", 2, D("180"))], descuento_empleada=True,
                           compradora=CompradoraCtx("VEND-3", None, None)))
        [l] = c.lineas
        self.assertEqual((l.descuento.importe, l.piezas_al_base), (D("18.00"), 2))
        self.assertIn(M.EMPLEADA_BASE, l.motivos)

    def test_lo_que_queda_fuera_del_tope_lo_gana_el_mayoreo(self) -> None:
        """Nivel 20 % casual, mayoreo 15 %, tope $200: una pieza al 20 %, la otra al 15 % de mayoreo."""
        c = calcular(venta([LineaEntrada(uid(1), "SC1", 2, D("200"), "Ropa casual")],
                           cliente=MAYORISTA, modalidad_mayorista="descuento", **con_nivel("20", "200")))
        [l] = c.lineas
        self.assertEqual((l.descuento.importe, l.piezas_con_nivel, l.piezas_al_base), (D("70.00"), 1, 0))


# ═══ 4. Fuente única: las reglas del motor siguen al código de hoy ══════


class FuenteUnicaReglasTests(unittest.TestCase):
    def test_reglas_por_omision_iguales_a_las_de_hoy(self) -> None:
        r = ReglasCtx()
        self.assertEqual(r.categorias_no_uniforme, inc.CATEGORIAS_NO_UNIFORME)
        self.assertEqual(r.pct_base_empleada, inc.PCT_BASE)
        self.assertEqual(r.tope_pct_uniforme, inc.TOPE_PCT_UNIFORME)
        self.assertEqual(r.pct_comision_tarjeta, lib.TERMINAL_COMMISSION_PERCENT)

    def test_mismo_criterio_de_uniforme(self) -> None:
        for categoria in ("Oficial", "Deportivo", "", "  ropa   CASUAL ", "Temporada", "Accesorio", "Ropa interior",
                          "Deportivo casual", "Escolta", "Básico"):
            c = calcular(venta([LineaEntrada(uid(1), "X", 1, D("100"), categoria)], **con_nivel("20", "1000")))
            tope = M.TOPE_UNIFORME_10 in c.lineas[0].motivos
            self.assertEqual(tope, inc.es_uniforme({"categoria": categoria}), categoria)

    def test_las_reglas_no_cambian_sin_cambiar_su_version(self) -> None:
        """Si alguien cambia una regla, esta prueba obliga a subir `version`
        (y la fotografía de cada venta guarda la versión y las reglas aplicadas)."""
        r = ReglasCtx()
        contenido = {f.name: getattr(r, f.name) for f in dataclasses.fields(r)}
        self.assertEqual(contenido, {
            "version": "2026-11-11",
            "pct_base_empleada": D("5"),
            "tope_pct_uniforme": D("10"),
            "categorias_no_uniforme": frozenset({"ropa casual", "temporada", "accesorio", "ropa interior", "deportivo casual"}),
            "pct_comision_tarjeta": D("4.5"),
            "pct_otra_persona": D("5"),
        })

    def test_la_fotografia_guarda_la_clasificacion_aplicada(self) -> None:
        e = venta([LineaEntrada(uid(1), "PO1", 1, D("180"), "Oficial")], **con_nivel("20", "1000"))
        foto = fotografia(e, calcular(e))
        self.assertEqual(foto["entrada"]["reglas"]["categorias_no_uniforme"], sorted(inc.CATEGORIAS_NO_UNIFORME))
        self.assertEqual(foto["entrada"]["lineas"][0]["categoria"], "Oficial")
        self.assertIn(M.TOPE_UNIFORME_10, foto["calculo"]["lineas"][0]["motivos"])
        otras = dataclasses.replace(e, reglas=dataclasses.replace(ReglasCtx(), categorias_no_uniforme=frozenset({"oficial"})))
        self.assertNotEqual(huella(foto), huella(fotografia(otras, calcular(otras))))


# ═══ 6. Contrato D6 y sin conexión ═══════════════════════════════════════


class ContratoD6Tests(unittest.TestCase):
    def test_campos_de_d6(self) -> None:
        nombres = lambda cls: {f.name for f in dataclasses.fields(cls)}  # noqa: E731
        self.assertIn("linea_uid", nombres(LineaEntrada))
        self.assertTrue({"linea_uid", "lineas_origen", "comision_linea"} <= nombres(LineaCalculo))
        self.assertTrue({"pagos", "vendedora", "fecha_venta", "origen_calculo"} <= nombres(EntradaVenta))
        self.assertTrue({"pagos", "vendedora", "fecha_venta", "origen_calculo", "comision_tarjeta"} <= nombres(Calculo))

    def test_los_valores_pasan_tal_cual(self) -> None:
        e = EntradaVenta((LineaEntrada(uid(1), "PO1", 2, D("150")),), FECHA, origen_calculo="servidor", vendedora="VEND-2",
                         pagos=(Pago("efectivo", D("100.00")), Pago("tarjeta", D("200.00"))))
        c = calcular(e)
        self.assertEqual((c.fecha_venta, c.origen_calculo, c.vendedora), (FECHA, "servidor", "VEND-2"))
        self.assertEqual(c.pagos, e.pagos)
        self.assertEqual(c.lineas[0].comision_linea, c.comision_tarjeta)
        self.assertEqual(c.comision_tarjeta, D("200.00") - lib.aplicar_comision_terminal(D("200")))


class SinConexionAuditoriaTests(unittest.TestCase):
    """C12 y lo que hace hoy el kiosko sin conexión; nada de H1."""

    SIN = dict(origen_calculo="kiosko_sin_conexion")

    def test_empleada_con_nivel_al_base_como_hoy(self) -> None:
        """Hoy (`quick_sale_compradora_helper`): sin conexión queda el 5 % de siempre."""
        c = calcular(venta([LineaEntrada(uid(1), "SC1", 1, D("400"), "Ropa casual")], **self.SIN, **con_nivel("20", "3000")))
        self.assertEqual((c.total, c.consumo_tope_total, c.lineas[0].piezas_al_base), (D("380.00"), D("0.00"), 1))

    def test_mayorista_sin_descuento_y_con_monedero_como_hoy(self) -> None:
        """Hoy (`quick_sale_monedero_helper`): sin conexión se apaga el descuento y el
        cashback se acredita al sincronizar. El motor no cobra mayoreo ni bloquea el abono."""
        c = calcular(venta([LineaEntrada(uid(1), "PO1", 2, D("180"))], cliente=MAYORISTA, modalidad_mayorista="descuento",
                           saldo_a_usar=D("50"), saldo_disponible=D("50"), **self.SIN))
        self.assertEqual((c.total, c.descuento_aplicado, c.saldo_usado), (D("360.00"), False, D("0.00")))
        self.assertEqual(c.monedero.abono, D("54.00"))
        self.assertEqual(c.motivos_ticket, (M.SIN_CONEXION_SIN_MAYOREO, M.SIN_CONEXION_SIN_SALDO))

    def test_sin_programa_conocido_no_hay_abono(self) -> None:
        """Si el kiosko no conoce la tasa (cliente solo por código), no calcula abono: lo hace el servidor."""
        c = calcular(venta([LineaEntrada(uid(1), "PO1", 1, D("180"))], cliente=ClienteCtx(None, None, None, None), **self.SIN))
        self.assertIsNone(c.monedero)
        self.assertIn(M.SIN_PROGRAMA, c.motivos_ticket)


if __name__ == "__main__":
    unittest.main()
