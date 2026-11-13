"""Cambios desde la venta (Daniel, 2026-11-12).

Reglas que eligió: lo que regresa vale lo que pagó; el Monedero que ganó por
eso se le quita; lo que queda a favor va a su Monedero (sin cliente, hay que
identificarlo); 15 días, después solo con el dueño. Y el stock cuadra: lo que
regresa entra, lo que se lleva sale.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Cliente, LibretaVenta, MovimientoInventario, RolUsuario, Usuario, Variante
from pos_uniformes.services import cambio_service as cs
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import monedero_service as mon
from pos_uniformes.tests._programa_de_prueba import inscribir, programa_de_prueba
from pos_uniformes.tests.test_conteo_jornada_service import _seed

D = Decimal


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        _seed(self.s, "Uno", stock=3)   # 2 prendas × tallas 6 y 8, stock 3
        self.admin = Usuario(username="admin", nombre_completo="Dueño", password_hash="x", rol=RolUsuario.ADMIN, activo=True)
        self.cliente = Cliente(codigo_cliente="CLI-000007", nombre="Ana")
        self.s.add_all([self.admin, self.cliente])
        self.s.flush()
        cfg = mon.guardar_config(self.s, tasa="10", habilitado=True, usuario_id=self.admin.id)
        cfg.vigente_desde = datetime(2020, 1, 1, tzinfo=UTC)
        inscribir(self.s, self.cliente.id, programa_de_prueba(self.s, "10"))
        self.s.flush()
        self.v = list(self.s.scalars(select(Variante).order_by(Variante.id)).all())

    def tearDown(self) -> None:
        self.s.close()

    def _linea(self, v, precio, cantidad=1, **kw):
        return {"sku": v.sku, "nombre": f"Prenda {v.id}", "talla": "6", "cantidad": cantidad, "precio": str(precio), **kw}

    def _venta(self, lineas, total, cliente=False, hace_dias=0):
        e = lib.registrar_operacion(
            self.s, employee_code="VEND-2", employee_name="Fanny", tipo="venta", items=lineas,
            monto_total=D(total), cliente_id=self.cliente.id if cliente else None,
            operacion_uuid=str(uuid.uuid4()),
        )
        if hace_dias:
            e.created_at = datetime.now(UTC) - timedelta(days=hace_dias)
        self.s.flush()
        return e

    def _stock(self, v) -> int:
        self.s.refresh(v)
        return v.stock_actual

    def _saldo(self) -> Decimal:
        return mon.resumen_cliente(self.s, self.cliente.id).disponible

    def _cambio(self, venta, regresa, lleva, **kw):
        return cs.registrar_cambio(self.s, venta_id=venta.id, regresa=regresa, lleva=lleva,
                                   employee_code="VEND-3", employee_name="Lupita", **kw)


class ValorTests(_Base):
    def test_vale_lo_que_pago_con_descuento_y_redondeo(self):
        venta = self._venta([self._linea(self.v[0], "179", desc_empleada_pct="5")], "170.00")
        self.assertEqual(cs.valores_por_pieza(venta)[0].quantize(D("0.01")), D("170.00"))

    def test_el_total_se_reparte_entre_renglones(self):
        venta = self._venta([self._linea(self.v[0], "450"), self._linea(self.v[1], "200")], "650")
        self.assertEqual([x.quantize(D("0.01")) for x in cs.valores_por_pieza(venta)], [D("450.00"), D("200.00")])

    def test_la_cuenta(self):
        c = cs.cuenta(D("450"), D("45"), D("200"))
        self.assertEqual((c.reconocido, c.a_pagar, c.a_favor), (D("405.00"), D("0.00"), D("205.00")))
        c = cs.cuenta(D("200"), D("0"), D("449.30"))
        self.assertEqual((c.a_pagar, c.a_favor), (D("249.50"), D("0.00")))   # R1


class CambioTests(_Base):
    def test_misma_prenda_otra_talla_cuadra_el_stock(self):
        venta = self._venta([self._linea(self.v[0], "450")], "450")
        self.assertEqual(self._stock(self.v[0]), 2)
        r = self._cambio(venta, {0: 1}, [self._linea(self.v[1], "450")])
        self.assertEqual((r.cuenta.a_pagar, r.cuenta.a_favor), (D("0.00"), D("0.00")))
        self.assertEqual((self._stock(self.v[0]), self._stock(self.v[1])), (3, 2))
        movs = self.s.scalars(select(MovimientoInventario).where(
            MovimientoInventario.referencia == f"libreta:{r.cambio.id}").order_by(MovimientoInventario.id)).all()
        self.assertEqual([(m.tipo_movimiento.value, m.cantidad) for m in movs],
                         [("CANCELACION_VENTA", 1), ("SALIDA_VENTA", -1)])
        self.assertEqual((r.cambio.tipo, r.cambio.piezas, r.cambio.comisiones, r.cambio.monto_total),
                         ("cambio", 0, 0, D("0.00")))

    def test_paga_la_diferencia_y_entra_al_corte(self):
        from pos_uniformes.services.corte_caja_service import resumir_periodo

        venta = self._venta([self._linea(self.v[0], "200")], "200")
        r = self._cambio(venta, {0: 1}, [self._linea(self.v[1], "450")], pago_tarjeta=True)
        self.assertEqual(r.cuenta.a_pagar, D("250.00"))
        self.assertEqual(r.cambio.monto_neto, lib.neto_de_cobro(D("250"), D("0"), True))
        resumen = resumir_periodo([r.cambio])
        self.assertEqual((resumen.ventas, resumen.tarjeta, resumen.piezas), (D("250.00"), D("250.00"), 0))

    def test_a_favor_va_al_monedero_menos_lo_que_gano(self):
        venta = self._venta([self._linea(self.v[0], "450")], "450", cliente=True)
        self.assertEqual(self._saldo(), D("45.00"))                 # 10 % de cashback
        r = self._cambio(venta, {0: 1}, [self._linea(self.v[1], "200")])
        self.assertEqual((r.cuenta.cashback_quitado, r.cuenta.a_favor), (D("45.00"), D("205.00")))
        self.assertEqual(self._saldo(), D("250.00"))                # 45 + 205
        mov = self.s.scalars(select(mon.MonederoMovimiento).where(
            mon.MonederoMovimiento.libreta_venta_id == r.cambio.id)).one()
        self.assertEqual((mov.tipo, mov.monto), (mon.AJUSTE_ABONO, D("205.00")))
        self.assertIn("cambio", mov.motivo)

    def test_sin_cliente_y_a_favor_hay_que_identificarlo(self):
        venta = self._venta([self._linea(self.v[0], "450")], "450")
        with self.assertRaises(cs.NecesitaCliente):
            self._cambio(venta, {0: 1}, [self._linea(self.v[1], "200")])
        r = self._cambio(venta, {0: 1}, [self._linea(self.v[1], "200")], cliente_id=self.cliente.id)
        self.assertEqual(r.cuenta.a_favor, D("250.00"))
        self.assertEqual(self._saldo(), D("250.00"))
        self.assertEqual((r.cambio.cliente_id, r.cambio.cliente), (self.cliente.id, "Ana"))

    def test_plazo_de_15_dias(self):
        venta = self._venta([self._linea(self.v[0], "450")], "450", hace_dias=20)
        with self.assertRaises(cs.FueraDePlazo):
            self._cambio(venta, {0: 1}, [self._linea(self.v[1], "450")])
        r = self._cambio(venta, {0: 1}, [self._linea(self.v[1], "450")], autorizo_dueno=True)
        self.assertTrue(r.cambio.calculo["cambio"]["autorizo_dueno"])

    def test_no_se_regresa_mas_de_lo_vendido_ni_dos_veces(self):
        venta = self._venta([self._linea(self.v[0], "100", cantidad=2)], "200")
        with self.assertRaises(cs.CambioError):
            self._cambio(venta, {0: 3}, [])
        self._cambio(venta, {0: 1}, [self._linea(self.v[1], "100")])
        self.assertEqual(cs.renglones_vendidos(self.s, venta)[0].disponibles, 1)
        with self.assertRaises(cs.CambioError):
            self._cambio(venta, {0: 2}, [self._linea(self.v[1], "200")])

    def test_el_cashback_se_quita_una_sola_vez_en_varios_cambios(self):
        venta = self._venta([self._linea(self.v[0], "100", cantidad=2)], "200", cliente=True)   # cashback 20
        r1 = self._cambio(venta, {0: 1}, [self._linea(self.v[1], "100")])
        r2 = self._cambio(venta, {0: 1}, [self._linea(self.v[1], "100")])
        self.assertEqual((r1.cuenta.cashback_quitado, r2.cuenta.cashback_quitado), (D("10.00"), D("10.00")))
        self.assertEqual((r1.cuenta.a_pagar, r2.cuenta.a_pagar), (D("10.00"), D("10.00")))

    def test_lo_rebajado_no_cuenta_para_el_cashback(self):
        venta = self._venta([
            self._linea(self.v[0], "100"),
            self._linea(self.v[1], "100", rebaja="oferta", precio_normal="150"),
        ], "200", cliente=True)
        _r, c = cs.preparar(self.s, venta, {1: 1}, [])
        self.assertEqual(c.cashback_quitado, D("0.00"))

    def test_sin_regresar_nada_no_es_cambio(self):
        venta = self._venta([self._linea(self.v[0], "100")], "100")
        with self.assertRaises(cs.CambioError):
            self._cambio(venta, {}, [self._linea(self.v[1], "100")])


class LiquidacionTests(_Base):
    """2026-11-12 (Daniel: «solucionemos estos»): lo de Liquidación no tiene
    cambio ni devolución, como dice el ticket; solo el dueño lo autoriza."""

    def _liq(self, v, precio, tipo="liquidacion"):
        return self._linea(v, precio, rebaja=tipo, precio_normal="450")

    def test_regla_pura(self):
        self.assertTrue(cs.vendida_en_liquidacion({"rebaja": "liquidacion"}))
        self.assertFalse(cs.vendida_en_liquidacion({"rebaja": "oferta"}))
        self.assertFalse(cs.vendida_en_liquidacion({"rebaja": True}))   # venta vieja: no se sabe
        self.assertFalse(cs.vendida_en_liquidacion({}))

    def test_renglon_marcado(self):
        venta = self._venta([self._liq(self.v[0], "200"), self._linea(self.v[1], "200")], "400")
        r = cs.renglones_vendidos(self.s, venta)
        self.assertEqual([x.liquidacion for x in r], [True, False])
        self.assertEqual(cs.liquidacion_que_regresa(r, {0: 1, 1: 1}), [r[0]])

    def test_regresar_liquidacion_sin_autorizacion_se_rechaza(self):
        venta = self._venta([self._liq(self.v[0], "200")], "200")
        with self.assertRaises(cs.EnLiquidacion) as e:
            self._cambio(venta, {0: 1}, [self._linea(self.v[1], "200")])
        self.assertEqual(str(e.exception), cs.MENSAJE_LIQUIDACION)
        self.assertEqual(self._stock(self.v[0]), 2)                 # no se movió nada

    def test_con_autorizacion_del_dueno_pasa(self):
        venta = self._venta([self._liq(self.v[0], "200")], "200")
        r = self._cambio(venta, {0: 1}, [self._linea(self.v[1], "200")], autorizo_dueno=True)
        self.assertTrue(r.cambio.calculo["cambio"]["autorizo_dueno"])
        self.assertEqual(self._stock(self.v[0]), 3)

    def test_oferta_si_se_cambia(self):
        venta = self._venta([self._liq(self.v[0], "200", "oferta")], "200")
        r = self._cambio(venta, {0: 1}, [self._linea(self.v[1], "200")])
        self.assertEqual(r.cuenta.a_pagar, D("0.00"))

    def test_llevarse_liquidacion_si_se_puede(self):
        venta = self._venta([self._linea(self.v[0], "200")], "200")
        r = self._cambio(venta, {0: 1}, [self._liq(self.v[1], "200")])
        self.assertEqual(r.lleva[0]["rebaja"], "liquidacion")

    def test_venta_vieja_sin_tipo_se_permite(self):
        venta = self._venta([self._linea(self.v[0], "200")], "200")
        venta.detalle = [{**venta.detalle[0], "rebaja": True}]
        self.s.flush()
        r = self._cambio(venta, {0: 1}, [self._linea(self.v[1], "200")])
        self.assertFalse(r.cambio.calculo["cambio"]["autorizo_dueno"])


class NoSeBorraTests(_Base):
    def test_ni_el_cambio_ni_la_venta_con_cambios(self):
        venta = self._venta([self._linea(self.v[0], "450")], "450")
        r = self._cambio(venta, {0: 1}, [self._linea(self.v[1], "450")])
        with patch.object(lib, "devolver_stock", return_value=0):
            for op in (r.cambio.id, venta.id):
                with self.assertRaises(lib.OperacionConCambios):
                    lib.eliminar_operacion(self.s, op)
                with self.assertRaises(lib.OperacionConCambios):
                    lib.borrar_desde_libreta(self.s, op, actor="VEND-1")
        self.assertIsNotNone(self.s.get(LibretaVenta, venta.id))

    def test_una_venta_sin_cambios_se_borra_como_siempre(self):
        venta = self._venta([self._linea(self.v[0], "450")], "450")
        self.assertTrue(lib.eliminar_operacion(self.s, venta.id))


class Promo3pzTests(_Base):
    """E7 y la promo 3pz en el cambio (Daniel, 2026-11-12: «Sí, que no
    aplique»): si regresa el pants base de la promo y se lleva un Pants 2pz
    deportivo rebajado, la playera que se queda se cobra a precio normal."""

    def setUp(self) -> None:
        super().setUp()
        self.v[1].precio_venta = Decimal("180.00")     # la playera, a precio normal
        self.s.flush()

    def _venta_3pz(self, con_foto=True):
        venta = self._venta([
            self._linea(self.v[0], "250", linea_uid="u-pants"),
            {**self._linea(self.v[1], "100", linea_uid="u-playera"), "nombre": "Playera Deportiva (promo 3pz)"},
        ], "350")
        if con_foto:
            venta.calculo = {"entrada": {"lineas": [
                {"linea_uid": "u-pants", "promo_3pz": True}, {"linea_uid": "u-playera", "promo_3pz": True},
            ]}}
            self.s.flush()
        return venta

    def _pants(self, rebaja="oferta", precio="175", deportivo=True):
        it = {"sku": self.v[2].sku, "nombre": "Pants 2pz Deportivo", "talla": "8", "cantidad": 1, "precio": precio}
        if rebaja:
            it.update(rebaja=rebaja, precio_normal="250")
        if deportivo:
            it[cs.LLAVE_PANTS_3PZ] = True
        return it

    def test_roles_desde_la_fotografia_o_la_marca(self):
        detalle = [{"linea_uid": "a"}, {"nombre": "Playera (promo 3pz)"}, {"promo_3pz": True}, {"linea_uid": "z"}]
        foto = {"entrada": {"lineas": [{"linea_uid": "a", "promo_3pz": True}, {"linea_uid": "z"}]}}
        self.assertEqual(cs.roles_promo_3pz(detalle, foto), ["base", "playera", "base", ""])
        self.assertEqual(cs.roles_promo_3pz(detalle, None), ["", "playera", "base", ""])

    def test_pants_por_uno_en_oferta_cobra_la_playera_a_precio_normal(self):
        venta = self._venta_3pz()
        renglones = cs.renglones_vendidos(self.s, venta)
        self.assertEqual([r.rol_3pz for r in renglones], ["base", "playera"])
        self.assertEqual(renglones[1].precio_normal, D("180.00"))
        self.assertEqual(cs.cargo_promo_3pz(renglones, {0: 1}, [self._pants()]), D("80.00"))
        self.assertEqual(cs.aviso_promo_3pz(renglones, {0: 1}, [self._pants()]),
                         "La playera iba en promo con ese pants: el pants nuevo está en Oferta, "
                         "la playera se cobra a precio normal.")
        r = self._cambio(venta, {0: 1}, [self._pants()])
        # 175 + 80 − 250: antes quedaban $75 a favor.
        self.assertEqual((r.cuenta.cargo_promo_3pz, r.cuenta.a_pagar, r.cuenta.a_favor), (D("80.00"), D("5.00"), D("0.00")))
        self.assertEqual(r.cambio.calculo["cambio"]["cargo_promo_3pz"], "80.00")

    def test_en_liquidacion_tambien(self):
        renglones = cs.renglones_vendidos(self.s, self._venta_3pz())
        self.assertEqual(cs.cargo_promo_3pz(renglones, {0: 1}, [self._pants("liquidacion", "150")]), D("80.00"))
        self.assertIn("Liquidación", cs.aviso_promo_3pz(renglones, {0: 1}, [self._pants("liquidacion", "150")]))

    def test_sin_cargo_si_no_aplica(self):
        renglones = cs.renglones_vendidos(self.s, self._venta_3pz())
        casos = {
            "pants a precio normal": ({0: 1}, [self._pants(rebaja=None, precio="250")]),
            "lo rebajado no es pants 2pz deportivo": ({0: 1}, [self._pants(deportivo=False)]),
            "la playera también regresa": ({0: 1, 1: 1}, [self._pants()]),
            "no regresa el pants": ({1: 1}, [self._pants()]),
        }
        for caso, (regresa, lleva) in casos.items():
            with self.subTest(caso):
                self.assertEqual(cs.cargo_promo_3pz(renglones, regresa, lleva), D("0.00"))
                self.assertEqual(cs.aviso_promo_3pz(renglones, regresa, lleva), "")

    def test_venta_sin_fotografia_ni_marca_no_se_sabe_cual_es_el_pants(self):
        renglones = cs.renglones_vendidos(self.s, self._venta_3pz(con_foto=False))
        self.assertEqual([r.rol_3pz for r in renglones], ["", "playera"])
        self.assertEqual(cs.cargo_promo_3pz(renglones, {0: 1}, [self._pants()]), D("0.00"))

    def test_la_playera_3pz_no_genero_monedero(self):
        """2026-11-13 («Solo la playera»): al regresarla no se le quita Monedero."""
        renglones = cs.renglones_vendidos(self.s, self._venta_3pz())
        self.assertEqual([r.sin_monedero for r in renglones], [False, True])
        self.assertEqual(cs.cashback_proporcional(D("12.50"), D("0"), renglones, {1: 1}), D("0.00"))
        self.assertEqual(cs.cashback_proporcional(D("12.50"), D("0"), renglones, {0: 1}), D("12.50"))

    def test_la_cuenta_suma_el_cargo(self):
        c = cs.cuenta(D("250"), D("0"), D("175"), D("80"))
        self.assertEqual((c.a_pagar, c.a_favor, c.cargo_promo_3pz), (D("5.00"), D("0.00"), D("80.00")))
        self.assertEqual(cs.cuenta(D("250"), D("0"), D("175")).a_favor, D("75.00"))


if __name__ == "__main__":
    unittest.main()
