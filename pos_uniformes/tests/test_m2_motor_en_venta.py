"""M2: el kiosko cobra con el motor de beneficios (T1–T4).

- El carrito se traduce a la entrada del motor sin perder la rebaja, la 3pz,
  el Mayorista ni quién compra (`beneficios_carrito`).
- La venta guarda su fotografía (`libreta_venta.calculo`, T2).
- El servidor recalcula: en la venta con saldo, un cobro distinto se detiene
  antes de cobrar (T3); en la que sube de la cola se anota la diferencia y la
  venta nunca se pierde.
- La comisión de tarjeta va una sola vez (T4).
- Ninguna parte del kiosko calcula descuentos por su cuenta (criterio 1).
"""

from __future__ import annotations

import inspect
import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Cliente, LibretaVenta, RolUsuario, Usuario
from pos_uniformes.services import beneficios_carrito as bc
from pos_uniformes.services import beneficios_servidor as srv
from pos_uniformes.services import incentivo_empleada_service as inc
from pos_uniformes.services import libreta_local_queue_service as cola
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import monedero_service as mon
from pos_uniformes.services.beneficios import calcular
from pos_uniformes.services.beneficios.fotografia import fotografia, huella
from pos_uniformes.tests._programa_de_prueba import inscribir, programa_de_prueba

D = Decimal
UTC = timezone.utc
AHORA = datetime(2026, 11, 12, 18, 0, tzinfo=UTC)


def playera(cantidad=1, sku="PO1", precio="180"):
    return {"sku": sku, "nombre": "Playera polo", "talla": "8", "precio": D(precio), "cantidad": cantidad}


def sudadera(precio="180", sku="SC1", cantidad=1):
    return {"sku": sku, "nombre": "Sudadera casual", "talla": "M", "precio": D(precio), "cantidad": cantidad,
            "categoria": "Ropa casual"}


def cliente_kiosko(cid=None, *, tasa="10", descuento=None, disponible="0"):
    return {"id": cid, "codigo": "CLI-000007", "estado": "activo", "tasa": D(tasa) if tasa else None,
            "descuento_disponible": D(descuento) if descuento else None, "disponible": D(disponible),
            "programa": None}


def foto_de(items, **kw):
    entrada = bc.entrada_desde_carrito(items, fecha_venta=AHORA, **kw)
    return fotografia(entrada, calcular(entrada))


# ─── El traductor del carrito ───────────────────────────────────────────


class TraductorTests(unittest.TestCase):
    def test_con_rebaja_el_precio_de_lista_es_el_normal(self):
        it = {**playera(precio="120"), "rebaja": "oferta", "precio_normal": D("180")}
        linea = bc.entrada_desde_carrito([it], fecha_venta=AHORA).lineas[0]
        self.assertEqual(linea.precio_lista, D("180.00"))
        self.assertEqual(linea.rebaja.precio, D("120.00"))

    def test_cada_renglon_con_su_uid_unico(self):
        a = playera()
        b = dict(a)  # un dict copiado traería el mismo uid
        bc.asegurar_uids([a])
        b["linea_uid"] = a["linea_uid"]
        entrada = bc.entrada_desde_carrito([a, b], fecha_venta=AHORA)
        uids = [l.linea_uid for l in entrada.lineas]
        self.assertEqual(len(set(uids)), 2)
        self.assertEqual(uids[0], a["linea_uid"])  # el primero conserva el suyo

    def test_la_3pz_se_marca_siempre(self):
        it = {**playera(), "sports_uniform_role": "base"}
        self.assertTrue(bc.entrada_desde_carrito([it], fecha_venta=AHORA).lineas[0].promo_3pz)

    def test_modalidad_del_mayorista(self):
        mayorista = cliente_kiosko(7, tasa="15", descuento="15")
        self.assertEqual(bc.modalidad(mayorista, usar_descuento=True), "descuento")
        self.assertEqual(bc.modalidad(mayorista, usar_descuento=False), "monedero")
        self.assertIsNone(bc.modalidad(cliente_kiosko(7), usar_descuento=True))
        self.assertEqual(bc.modalidad(None, usar_descuento=False, pct_mayoreo_fijo=D("15")), "descuento")

    def test_sin_compradora_es_otra_persona(self):
        self.assertIsNone(bc.compradora_ctx(None, descuento_empleada=True))
        ana = inc.EstadoCompradora("VEND-3", "Ana", D("20"), D("3000"), D("2700"))
        ctx = bc.compradora_ctx(ana, descuento_empleada=True)
        self.assertEqual((ctx.pct_nivel, ctx.restante_tope), (D("20"), D("300.00")))
        self.assertIsNone(bc.compradora_ctx(ana, descuento_empleada=False))

    def test_el_renglon_se_parte_por_pieza_para_la_libreta(self):
        """C9: «2 × $180» con $300 de tope: una pieza al 20 % y otra al 5 %, y el
        tope usado del mes (que se lee de `detalle`) es una sola pieza."""
        items = [sudadera(cantidad=2)]
        ana = inc.EstadoCompradora("VEND-3", "Ana", D("20"), D("3000"), D("2700"))
        entrada = bc.entrada_desde_carrito(items, fecha_venta=AHORA, descuento_empleada=True, compradora=ana)
        calculo = calcular(entrada)
        self.assertEqual(calculo.total, D("315.00"))
        renglones = bc.detalle_por_renglon(items, calculo)
        self.assertEqual([(r["cantidad"], r["desc_empleada_pct"]) for r in renglones], [(1, D("20")), (1, D("5"))])
        self.assertEqual(inc.importe_con_nivel(renglones), D("180.00"))

    def test_sin_descuento_de_empleada_no_se_marca(self):
        items = [{**playera(), "desc_empleada_pct": D("15")}]
        calculo = calcular(bc.entrada_desde_carrito(items, fecha_venta=AHORA))
        self.assertNotIn("desc_empleada_pct", bc.detalle_por_renglon(items, calculo)[0])

    def test_la_fotografia_se_puede_reconstruir(self):
        foto = foto_de([playera(2), sudadera()], cliente=cliente_kiosko(7), descuento_empleada=True)
        entrada = srv.entrada_desde_plano(foto["entrada"])
        self.assertEqual(huella(fotografia(entrada, calcular(entrada))), huella(foto))


# ─── El servidor ─────────────────────────────────────────────────────────


class _Db(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.admin = Usuario(username="admin", nombre_completo="Dueño", password_hash="x",
                             rol=RolUsuario.ADMIN, activo=True)
        self.cliente = Cliente(codigo_cliente="CLI-000007", nombre="Ana")
        self.s.add_all([self.admin, self.cliente])
        self.s.flush()
        cfg = mon.guardar_config(self.s, tasa="10", habilitado=True, usuario_id=self.admin.id)
        cfg.vigente_desde = datetime(2020, 1, 1, tzinfo=UTC)
        inscribir(self.s, self.cliente.id, programa_de_prueba(self.s, "10"))
        self.s.flush()
        stock = patch.object(lib, "descontar_stock", return_value=0)
        stock.start()
        self.addCleanup(stock.stop)

    def _items_payload(self, items):
        bc.asegurar_uids(items)
        return [{"sku": it["sku"], "nombre": it["nombre"], "talla": it["talla"], "cantidad": it["cantidad"],
                 "precio": str(it["precio"]), "linea_uid": it["linea_uid"]} for it in items]

    def _saldo(self):
        return mon.resumen_cliente(self.s, self.cliente.id).disponible


class ServidorColaTests(_Db):
    def _subir(self, items, foto, total, cliente_id=None):
        cola._subir(self.s, {
            "employee_code": "VEND-1", "employee_name": "Daniel", "tipo": "venta",
            "items": self._items_payload(items), "monto_total": str(total), "monto_neto": str(total),
            "operacion_uuid": str(uuid.uuid4()), "created_at": AHORA.isoformat(), "calculo": foto,
            **({"cliente_codigo": "CLI-000007"} if cliente_id else {}),
        })
        return self.s.scalars(select(LibretaVenta)).one()

    def test_guarda_la_fotografia_con_lo_del_servidor(self):
        items = [playera(2)]
        foto = foto_de(items, cliente=cliente_kiosko(self.cliente.id))
        v = self._subir(items, foto, "360.00", cliente_id=self.cliente.id)
        self.assertEqual(v.version_reglas, foto["version_reglas"])
        self.assertEqual(v.calculo["calculo"]["total"], "360.00")
        self.assertEqual(v.calculo["servidor"]["diferencias"], {})
        self.assertEqual(v.calculo["servidor"]["entrada"]["origen_calculo"], "servidor")
        self.assertEqual(v.detalle[0]["linea_uid"], items[0]["linea_uid"])
        self.assertEqual(self._saldo(), D("36.00"))  # el abono sigue como siempre

    def test_una_diferencia_se_anota_y_la_venta_no_se_pierde(self):
        """El kiosko creyó que era Mayorista con descuento; en la base no lo es.
        El cliente ya pagó: la venta queda con lo cobrado y la diferencia anotada."""
        items = [playera(2)]
        foto = foto_de(items, cliente=cliente_kiosko(self.cliente.id, descuento="15"), usar_descuento_programa=True)
        self.assertEqual(foto["calculo"]["total"], "306.00")
        v = self._subir(items, foto, "306.00", cliente_id=self.cliente.id)
        self.assertEqual(v.monto_total, D("306.00"))
        self.assertEqual(v.calculo["servidor"]["diferencias"]["total"], ["306.00", "360.00"])

    def test_sin_conexion_se_recalcula_con_las_reglas_sin_conexion(self):
        items = [playera()]
        foto = foto_de(items, en_linea=False, cliente={"id": None, "codigo": "CLI-000007", "estado": "activo"})
        v = self._subir(items, foto, "180.00", cliente_id=self.cliente.id)
        self.assertEqual(v.calculo["servidor"]["entrada"]["origen_calculo"], "kiosko_sin_conexion")
        self.assertEqual(v.calculo["servidor"]["diferencias"], {})

    def test_si_el_recalculo_falla_la_venta_queda(self):
        items = [playera()]
        foto = foto_de(items)
        with patch.object(srv, "recalcular", side_effect=RuntimeError("boom")):
            v = self._subir(items, foto, "180.00")
        self.assertIn("boom", v.calculo["servidor"]["error"])

    def test_las_ventas_de_antes_sin_fotografia(self):
        v = self._subir([playera()], None, "180.00")
        self.assertIsNone(v.calculo)
        self.assertIsNone(v.version_reglas)


class ServidorConSaldoTests(_Db):
    def setUp(self) -> None:
        super().setUp()
        lib.registrar_operacion(self.s, employee_code="VEND-1", employee_name="Daniel", tipo="venta", items=[],
                                monto_total=D("200"), cliente_id=self.cliente.id, operacion_uuid=str(uuid.uuid4()))
        self.assertEqual(self._saldo(), D("20.00"))

    def _cobrar(self, items, foto):
        return lib.registrar_venta_con_monedero(
            self.s, employee_code="VEND-1", employee_name="Daniel", items=self._items_payload(items),
            monto_total=D(foto["calculo"]["total"]), monto_monedero=D(foto["calculo"]["saldo_usado"]),
            cliente_id=self.cliente.id, operacion_uuid=str(uuid.uuid4()), calculo=foto,
        )

    def test_con_el_saldo_correcto_cobra_y_guarda_la_fotografia(self):
        items = [playera()]
        foto = foto_de(items, cliente=cliente_kiosko(self.cliente.id, disponible="20"), usar_saldo=True,
                       saldo_disponible=D("20"))
        v, canje, _ = self._cobrar(items, foto)
        self.assertEqual(canje.monto, D("-20.00"))
        self.assertEqual(v.calculo["servidor"]["diferencias"], {})

    def test_t3_si_el_saldo_cambio_no_se_cobra(self):
        """El kiosko leyó $50 de saldo; la base tiene $20. No se cobra con el
        importe viejo: la empleada ve el nuevo antes de cobrar."""
        items = [playera()]
        foto = foto_de(items, cliente=cliente_kiosko(self.cliente.id, disponible="50"), usar_saldo=True,
                       saldo_disponible=D("50"))
        with self.assertRaises(srv.CalculoCambio) as ctx:
            self._cobrar(items, foto)
        self.assertIn("$50.00 → $20.00", str(ctx.exception))
        self.s.rollback()
        self.assertEqual(self.s.scalars(select(LibretaVenta).where(LibretaVenta.monto_monedero > 0)).all(), [])


class ComisionUnicaTests(unittest.TestCase):
    def test_t4_el_kiosko_y_la_libreta_dan_el_mismo_neto(self):
        from pos_uniformes.services.beneficios.motor import neto_con_comision

        for total in ("450", "1030", "515", "89.50"):
            self.assertEqual(
                neto_con_comision(D(total), lib.TERMINAL_COMMISSION_PERCENT), lib.neto_de_cobro(D(total), D("0"), True)
            )


# ─── El kiosko ───────────────────────────────────────────────────────────


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _kiosko(self, items):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code = "VEND-1"
        w._employee_name = "Daniel"
        w._items = [dict(it) for it in items]
        return w

    def _anotacion(self, w, tarjeta=False):
        with patch.object(w, "_origen_satelite", return_value="Entrada"):
            (entrada,) = w._armar_anotacion("venta", cliente=None, pago_tarjeta=tarjeta, anticipo=None,
                                            anticipo_tarjeta=False)
        return entrada


class KioskoTests(_Qt):
    def test_la_anotacion_lleva_la_fotografia(self):
        w = self._kiosko([playera(2), sudadera("400")])
        entrada = self._anotacion(w, tarjeta=True)
        foto = entrada["calculo"]
        self.assertEqual(entrada["version_reglas"], foto["version_reglas"])
        self.assertEqual(entrada["monto_total"], foto["calculo"]["total"])
        self.assertEqual(entrada["monto_neto"], foto["calculo"]["neto_tienda"])
        self.assertTrue(foto["entrada"]["pago_tarjeta"])
        self.assertEqual([i["linea_uid"] for i in entrada["items"]], [l["linea_uid"] for l in foto["entrada"]["lineas"]])

    def test_si_el_motor_falla_se_anota_con_el_calculo_de_antes(self):
        w = self._kiosko([playera(2)])
        with patch.object(w, "_calculo_y_entrada", side_effect=RuntimeError("boom")):
            entrada = self._anotacion(w)
        self.assertNotIn("calculo", entrada)
        self.assertEqual(entrada["monto_total"], "360.00")

    def test_la_reimpresion_usa_lo_que_se_cobro(self):
        w = self._kiosko([])
        foto = {"calculo": {"subtotal": "360.00", "descuento_total": "18.00", "total": "342.00"}}
        with patch.object(w, "_load_business_info", return_value=("MAXIMODA", "", "")):
            texto = w.build_reprint_ticket(tipo="venta", detalle=[{**playera(2), "precio": "180"}], cliente=None,
                                           employee_name="Daniel", descuento_empleada=True,
                                           created_at=AHORA, calculo=foto)
        self.assertIn("$342.00", texto)
        self.assertIsNone(w._calculo_fijo)
        self.assertFalse(w._reimpresion_legada)

    def test_t3_si_el_tope_cambio_la_empleada_lo_ve_antes_de_cobrar(self):
        w = self._kiosko([sudadera("280")])
        w._discount_active = True
        w._compradora = inc.EstadoCompradora("VEND-3", "Ana", D("20"), D("3000"), D("2700"))  # le quedan 300

        def otro_kiosko_ya_lo_gasto():
            w._compradora = inc.EstadoCompradora("VEND-3", "Ana", D("20"), D("3000"), D("3000"))
            return True

        with patch.object(w, "_refrescar_contexto_motor", side_effect=otro_kiosko_ya_lo_gasto), \
             patch("PyQt6.QtWidgets.QMessageBox.information") as aviso:
            self.assertFalse(w._revisar_con_servidor())
        self.assertIn("$224.00", aviso.call_args.args[2])   # 280 al 20 %
        self.assertIn("$266.00", aviso.call_args.args[2])   # 280 al 5 %
        self.assertEqual(w._compute_totals()[2], D("266.00"))

    def test_t3_sin_cambios_se_cobra(self):
        w = self._kiosko([playera()])
        with patch.object(w, "_refrescar_contexto_motor", return_value=True):
            self.assertTrue(w._revisar_con_servidor())

    def test_t3_sin_conexion_se_cobra_con_lo_que_hay(self):
        w = self._kiosko([playera()])
        with patch.object(w, "_refrescar_contexto_motor", return_value=False):
            self.assertTrue(w._revisar_con_servidor())


class UnSoloMotorTests(unittest.TestCase):
    """Criterio 1: el cobro del kiosko no calcula descuentos ni comisiones por su cuenta."""

    PROHIBIDOS = ("dps.descuento(", "inc.repartir(", "porcentaje_de_linea(", "_apply_terminal_commission(",
                  "aplicar_comision_terminal(", "_DISCOUNT_PERCENT /")

    def test_el_cobro_no_calcula_por_su_cuenta(self):
        from pos_uniformes.ui.helpers import quick_sale_motor_helper
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        fuentes = {
            "_compute_totals": inspect.getsource(QuickSaleWidget._compute_totals),
            "_monto_neto_actual": inspect.getsource(QuickSaleWidget._monto_neto_actual),
            "_armar_anotacion": inspect.getsource(QuickSaleWidget._armar_anotacion),
            "_renglones_comision": inspect.getsource(QuickSaleWidget._renglones_comision),
            "motor_helper": inspect.getsource(quick_sale_motor_helper),
        }
        for nombre, fuente in fuentes.items():
            for prohibido in self.PROHIBIDOS:
                self.assertNotIn(prohibido, fuente, f"{nombre} usa {prohibido}")


if __name__ == "__main__":
    unittest.main()
