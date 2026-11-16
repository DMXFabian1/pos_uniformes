"""El motor con el QR de descuento de temporada (Daniel, 2026-11-16).

Solo ropa normal; ni rebajas ni promo 3pz; por línea gana el mayor entre
mayoreo, empleada y QR; las líneas con QR no abonan Monedero; el 15 % baja a
10 % bajo $600; vencido o sin conexión no aplica; el servidor recalcula igual.
"""

from __future__ import annotations

import dataclasses
import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from pos_uniformes.services import beneficios_carrito as bc
from pos_uniformes.services.beneficios import motivos as M
from pos_uniformes.services.beneficios.contrato import (
    ORIGEN_KIOSKO_SIN_CONEXION,
    ClienteCtx,
    CompradoraCtx,
    EntradaInvalida,
    EntradaVenta,
    LineaEntrada,
    Rebaja,
)
from pos_uniformes.services.beneficios.fotografia import _plano, fotografia
from pos_uniformes.services.beneficios.motor import FUENTE_QR, calcular
from pos_uniformes.services.beneficios_servidor import diferencias, entrada_desde_plano

D = Decimal
AHORA = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
CLUB = ClienteCtx(id=7, programa_clave="club", tasa_monedero=D("5"), pct_mayoreo=None, activo=True)


def uid(n: int) -> str:
    return str(uuid.UUID(int=n, version=4))


def linea(n, precio, categoria="Ropa casual", cantidad=1, sku=None, **kw) -> LineaEntrada:
    return LineaEntrada(uid(n), sku or f"S{n}", cantidad, D(precio), categoria, **kw)


def venta(lineas, qr=None, **kw) -> EntradaVenta:
    return EntradaVenta(lineas=tuple(lineas), fecha_venta=kw.pop("fecha_venta", AHORA),
                        descuento_qr_pct=(D(qr) if qr is not None else None), **kw)


def por_sku(calculo):
    return {l.sku: l for l in calculo.lineas}


class SoloRopaNormalTests(unittest.TestCase):
    def test_solo_las_lineas_de_ropa_normal(self) -> None:
        c = calcular(venta([
            linea(1, "400", "Ropa casual"),
            linea(2, "180", "Oficial"),
            linea(3, "45", "Accesorio"),       # calcetas escolares: uniforme
            linea(4, "200", "Temporada"),
            linea(5, "150", ""),               # sin categoría cuenta como uniforme
        ], qr="10"))
        lineas = por_sku(c)
        self.assertEqual(lineas["S1"].descuento.importe, D("40.00"))
        self.assertEqual(lineas["S1"].descuento.fuente, FUENTE_QR)
        self.assertEqual(lineas["S4"].descuento.importe, D("20.00"))
        for sku in ("S2", "S3", "S5"):
            self.assertEqual(lineas[sku].descuento.importe, D("0.00"), sku)
            self.assertIsNone(lineas[sku].descuento.fuente, sku)
        self.assertEqual(c.descuento_qr.importe, D("60.00"))
        self.assertEqual(c.descuento_qr.pct, D("10"))
        self.assertEqual(c.descuento_qr.base_elegible, D("600.00"))
        self.assertIn(M.DESCUENTO_QR, lineas["S1"].motivos)

    def test_no_aplica_a_rebajas_ni_a_la_promo_3pz(self) -> None:
        c = calcular(venta([
            linea(1, "300", "Ropa casual", rebaja=Rebaja("oferta", D("200"))),
            linea(2, "300", "Deportivo casual", promo_3pz=True),
            linea(3, "100", "Deportivo casual", promo_3pz=True, playera_3pz=True),
            linea(4, "100", "Ropa interior"),
        ], qr="5"))
        lineas = por_sku(c)
        for sku in ("S1", "S2", "S3"):
            self.assertEqual(lineas[sku].descuento.importe, D("0.00"), sku)
        self.assertEqual(lineas["S4"].descuento.importe, D("5.00"))
        self.assertEqual(c.descuento_qr.base_elegible, D("100.00"))

    def test_sin_ropa_normal_no_descuenta_y_lo_dice(self) -> None:
        c = calcular(venta([linea(1, "180", "Oficial")], qr="10"))
        self.assertEqual(c.descuento_total, D("0.00"))
        self.assertEqual(c.descuento_qr.importe, D("0.00"))
        self.assertIn(M.QR_SIN_LINEAS_ELEGIBLES, c.motivos_ticket)

    def test_sin_qr_no_cambia_nada(self) -> None:
        e = venta([linea(1, "400"), linea(2, "180", "Oficial")])
        c = calcular(e)
        self.assertIsNone(c.descuento_qr)
        self.assertEqual(c.descuento_total, D("0.00"))
        self.assertEqual(c.lineas[0].descuento_qr, D("0.00"))

    def test_solo_5_10_o_15(self) -> None:
        for malo in ("7", "20", "0.5"):
            with self.assertRaises(EntradaInvalida, msg=malo):
                calcular(venta([linea(1, "400")], qr=malo))
        with self.assertRaises(EntradaInvalida):
            calcular(dataclasses.replace(venta([linea(1, "400")]), descuento_qr_pct=10.0))


class GanaElMayorTests(unittest.TestCase):
    def _mayorista(self, pct):
        return dict(cliente=ClienteCtx(id=9, programa_clave="mayorista", tasa_monedero=D("15"),
                                       pct_mayoreo=D(pct), activo=True),
                    modalidad_mayorista="descuento")

    def test_mayoreo_mayor_gana(self) -> None:
        c = calcular(venta([linea(1, "1000")], qr="10", **self._mayorista("15")))
        l = c.lineas[0]
        self.assertEqual((l.descuento.pct, l.descuento.fuente), (D("15"), "mayoreo"))
        self.assertEqual(l.descuento.importe, D("150.00"))   # no se suman
        self.assertIn(M.GANA_MAYOREO, l.motivos)
        self.assertEqual(c.descuento_qr.importe, D("0.00"))

    def test_qr_mayor_gana_al_mayoreo(self) -> None:
        c = calcular(venta([linea(1, "1000"), linea(2, "200", "Oficial")], qr="15", **self._mayorista("10")))
        lineas = por_sku(c)
        self.assertEqual(lineas["S1"].descuento.fuente, FUENTE_QR)
        self.assertEqual(lineas["S1"].descuento.importe, D("150.00"))
        self.assertIn(M.GANA_QR, lineas["S1"].motivos)
        # El uniforme sigue con su mayoreo.
        self.assertEqual(lineas["S2"].descuento.fuente, "mayoreo")
        self.assertEqual(lineas["S2"].descuento.importe, D("20.00"))

    def test_empate_gana_el_mayoreo(self) -> None:
        c = calcular(venta([linea(1, "1000")], qr="10", **self._mayorista("10")))
        self.assertEqual(c.lineas[0].descuento.fuente, "mayoreo")

    def test_qr_gana_al_5_de_empleada(self) -> None:
        compradora = CompradoraCtx(codigo="VEND-2", pct_nivel=None, restante_tope=None)
        c = calcular(venta([linea(1, "400"), linea(2, "180", "Oficial")], qr="10",
                           descuento_empleada=True, compradora=compradora))
        lineas = por_sku(c)
        self.assertEqual((lineas["S1"].descuento.fuente, lineas["S1"].descuento.importe), (FUENTE_QR, D("40.00")))
        self.assertEqual((lineas["S2"].descuento.fuente, lineas["S2"].descuento.importe), ("empleada", D("9.00")))

    def test_otra_persona_contra_qr(self) -> None:
        c = calcular(venta([linea(1, "400")], qr="5", descuento_empleada=True))
        # 5 contra 5: empate, se queda la empleada (el QR solo gana si es mayor).
        self.assertEqual(c.lineas[0].descuento.fuente, "otra_persona")
        self.assertEqual(c.lineas[0].descuento.importe, D("20.00"))

    def test_nivel_de_empleada_mayor_gana_al_qr(self) -> None:
        compradora = CompradoraCtx(codigo="VEND-2", pct_nivel=D("20"), restante_tope=D("5000"))
        c = calcular(venta([linea(1, "1000")], qr="15", descuento_empleada=True, compradora=compradora))
        l = c.lineas[0]
        self.assertEqual((l.descuento.pct, l.descuento.fuente), (D("20"), "empleada"))
        self.assertIn(M.GANA_EMPLEADA, l.motivos)
        self.assertEqual(c.descuento_qr.importe, D("0.00"))

    def test_qr_mayor_que_el_nivel_consume_el_tope_como_el_mayoreo(self) -> None:
        compradora = CompradoraCtx(codigo="VEND-2", pct_nivel=D("10"), restante_tope=D("5000"))
        c = calcular(venta([linea(1, "1000")], qr="15", descuento_empleada=True, compradora=compradora))
        l = c.lineas[0]
        self.assertEqual((l.descuento.pct, l.descuento.fuente), (D("15"), FUENTE_QR))
        self.assertIn(M.TOPE_CONSUMIDO_CON_QR, l.motivos)
        self.assertEqual(l.consumo_tope, D("1000.00"))


class MonederoTests(unittest.TestCase):
    def test_las_lineas_con_qr_no_abonan(self) -> None:
        c = calcular(venta([linea(1, "400"), linea(2, "200", "Oficial")], qr="10", cliente=CLUB))
        lineas = por_sku(c)
        self.assertEqual(lineas["S1"].base_monedero, D("0.00"))
        self.assertIn(M.QR_SIN_MONEDERO, lineas["S1"].motivos)
        self.assertEqual(lineas["S2"].base_monedero, D("200.00"))
        self.assertEqual(c.monedero.base, D("200.00"))
        self.assertEqual(c.monedero.abono, D("10.00"))

    def test_sin_qr_la_misma_venta_si_abona_todo(self) -> None:
        c = calcular(venta([linea(1, "400"), linea(2, "200", "Oficial")], cliente=CLUB))
        self.assertEqual(c.monedero.base, D("600.00"))

    def test_qr_que_no_aplico_no_quita_monedero(self) -> None:
        c = calcular(venta([linea(1, "400")], qr="10", cliente=CLUB,
                           fecha_venta=datetime(2027, 2, 1, 18, tzinfo=timezone.utc)))
        self.assertEqual(c.monedero.base, D("400.00"))


class MinimoDel15Tests(unittest.TestCase):
    def test_con_600_aplica_15(self) -> None:
        c = calcular(venta([linea(1, "300", cantidad=2)], qr="15"))
        self.assertEqual(c.descuento_qr.pct, D("15"))
        self.assertEqual(c.descuento_total, D("90.00"))
        self.assertIsNone(c.descuento_qr.motivo)

    def test_bajo_600_baja_a_10_con_motivo(self) -> None:
        # $599 de ropa normal; el uniforme no cuenta para el mínimo.
        c = calcular(venta([linea(1, "599"), linea(2, "500", "Oficial")], qr="15"))
        self.assertEqual(c.descuento_qr.pct_pedido, D("15"))
        self.assertEqual(c.descuento_qr.pct, D("10"))
        self.assertEqual(c.descuento_qr.motivo, M.QR_15_A_10)
        self.assertIn(M.QR_15_A_10, c.motivos_ticket)
        self.assertEqual(c.descuento_total, D("59.90"))

    def test_la_rebaja_no_cuenta_para_el_minimo(self) -> None:
        c = calcular(venta([linea(1, "500"), linea(2, "300", rebaja=Rebaja("liquidacion", D("150")))], qr="15"))
        self.assertEqual(c.descuento_qr.base_elegible, D("500.00"))
        self.assertEqual(c.descuento_qr.pct, D("10"))


class VencidoYSinConexionTests(unittest.TestCase):
    def test_el_6_de_enero_aun_aplica(self) -> None:
        local = datetime(2027, 1, 6, 23, 0).astimezone()
        c = calcular(venta([linea(1, "400")], qr="10", fecha_venta=local))
        self.assertEqual(c.descuento_total, D("40.00"))

    def test_vencido_no_aplica_aunque_venga_en_la_entrada(self) -> None:
        local = datetime(2027, 1, 7, 0, 5).astimezone()
        c = calcular(venta([linea(1, "400")], qr="10", fecha_venta=local))
        self.assertEqual(c.descuento_total, D("0.00"))
        self.assertEqual(c.descuento_qr.pct, D("0"))
        self.assertIn(M.QR_VENCIDO, c.motivos_ticket)

    def test_sin_conexion_no_aplica(self) -> None:
        c = calcular(venta([linea(1, "400")], qr="10", origen_calculo=ORIGEN_KIOSKO_SIN_CONEXION))
        self.assertEqual(c.descuento_total, D("0.00"))
        self.assertIn(M.QR_SIN_CONEXION, c.motivos_ticket)


class ServidorTests(unittest.TestCase):
    def _foto(self, **kw):
        e = venta([linea(1, "400"), linea(2, "350", "Temporada"), linea(3, "180", "Oficial")], cliente=CLUB, **kw)
        return fotografia(e, calcular(e))

    def test_el_servidor_recalcula_igual(self) -> None:
        for pct in ("5", "10", "15"):
            foto = self._foto(qr=pct)
            entrada = entrada_desde_plano(foto["entrada"])
            self.assertEqual(entrada.descuento_qr_pct, D(pct))
            otra = calcular(entrada)
            self.assertEqual(diferencias(foto["calculo"], otra), {}, pct)
            self.assertEqual(_plano(otra), foto["calculo"])

    def test_fotografia_de_antes_sin_el_campo(self) -> None:
        foto = self._foto()
        del foto["entrada"]["descuento_qr_pct"]
        for campo in ("qr_categorias", "qr_minimo_15", "qr_vence"):
            del foto["entrada"]["reglas"][campo]
        entrada = entrada_desde_plano(foto["entrada"])
        self.assertIsNone(entrada.descuento_qr_pct)
        self.assertEqual(diferencias(foto["calculo"], calcular(entrada)), {})

    def test_un_kiosko_no_alarga_el_vencimiento(self) -> None:
        foto = self._foto(qr="10")
        foto["entrada"]["reglas"]["qr_vence"] = "2030-01-01"
        foto["entrada"]["fecha_venta"] = datetime(2027, 3, 1, 18, tzinfo=timezone.utc).isoformat()
        c = calcular(entrada_desde_plano(foto["entrada"]))
        self.assertEqual(c.descuento_qr.pct, D("0"))

    def test_desde_el_carrito(self) -> None:
        items = [{"sku": "SC1", "nombre": "Sudadera", "talla": "M", "precio": D("400"), "cantidad": 1,
                  "categoria": "Ropa casual"}]
        e = bc.entrada_desde_carrito(items, fecha_venta=AHORA, descuento_qr_pct="10")
        self.assertEqual(e.descuento_qr_pct, D("10"))
        self.assertEqual(calcular(e).descuento_total, D("40.00"))
        self.assertIsNone(bc.entrada_desde_carrito(items, fecha_venta=AHORA).descuento_qr_pct)


if __name__ == "__main__":
    unittest.main()
