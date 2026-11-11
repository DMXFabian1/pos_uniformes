"""E5-A, parte B (Daniel, 2026-11-10): el Mayorista elige en cada compra su
15 % como descuento (precio de mayoreo) o al Monedero.

- Con descuento, esa venta no genera Monedero.
- No aplica a la promo 3pz.
- No se suma con el 5 % de empleada: por renglón gana el más alto.

Reglas puras, la Libreta en SQLite en memoria y el kiosko sin base.
"""

from __future__ import annotations

import os
import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Cliente, LibretaVenta, MonederoMovimiento, RolUsuario, Usuario
from pos_uniformes.services import libreta_local_queue_service as cola
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import monedero_service as mon
from pos_uniformes.services.fidelizacion import descuento_programa_service as dps
from pos_uniformes.tests._programa_de_prueba import inscribir, programa_de_prueba

D = Decimal
UTC = timezone.utc

PANTS = {"sku": "P1", "nombre": "Pants", "talla": "10", "precio": D("400"), "cantidad": 1}
PROMO_BASE = {"sku": "B1", "nombre": "Pants 2pz", "talla": "8", "precio": D("500"), "cantidad": 1,
              "sports_uniform_role": "base"}
PROMO_PLAYERA = {"sku": "PL", "nombre": "Playera promo", "talla": "8", "precio": D("100"), "cantidad": 1,
                 "sports_uniform_role": "playera"}


class ReglasTests(unittest.TestCase):
    def test_gana_el_mas_alto_y_la_promo_no_lleva_mayoreo(self) -> None:
        self.assertEqual(dps.porcentaje_de_linea(PANTS, empleada=5, programa=15), D("15"))
        self.assertEqual(dps.porcentaje_de_linea(PANTS, empleada=20, programa=15), D("20"))
        self.assertEqual(dps.porcentaje_de_linea(PROMO_BASE, empleada=None, programa=15), D("0"))
        self.assertEqual(dps.porcentaje_de_linea(PROMO_PLAYERA, empleada=5, programa=15), D("5"))
        self.assertEqual(dps.porcentaje_de_linea({"promo_3pz": True}, programa=15), D("0"))

    def test_descuento_del_carrito(self) -> None:
        self.assertEqual(dps.descuento([PANTS, PROMO_BASE, PROMO_PLAYERA], programa=15), D("60.00"))
        self.assertEqual(dps.descuento([PANTS, PROMO_BASE], empleada=5, programa=15), D("85.00"))
        self.assertEqual(dps.precio_con_descuento(D("400"), 15), D("340.00"))
        self.assertEqual(dps.precio_con_descuento(D("400"), 0), D("400"))
        self.assertEqual(dps.texto_boton(D("15.00")), "🏷 Descuento 15 %")


class _Db(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.admin = Usuario(username="admin", nombre_completo="Dueño", password_hash="x", rol=RolUsuario.ADMIN, activo=True)
        self.cliente = Cliente(codigo_cliente="CLI-000009", nombre="Papelería Ruiz")
        self.s.add_all([self.admin, self.cliente])
        self.s.flush()
        cfg = mon.guardar_config(self.s, tasa="1", habilitado=True, usuario_id=self.admin.id)
        cfg.vigente_desde = datetime(2020, 1, 1, tzinfo=UTC)
        self.mayorista = programa_de_prueba(self.s, "15", clave="MAYORISTA_PRUEBA")
        self.mayorista.permite_descuento = True
        inscribir(self.s, self.cliente.id, self.mayorista)
        stock = patch.object(lib, "descontar_stock", return_value=0)
        stock.start()
        self.addCleanup(stock.stop)

    def _cashbacks(self) -> int:
        return self.s.scalar(select(func.count(MonederoMovimiento.id)).where(MonederoMovimiento.tipo == mon.CASHBACK))


class LibretaTests(_Db):
    def test_el_resumen_ofrece_el_descuento_solo_si_el_programa_lo_permite(self) -> None:
        self.assertEqual(mon.resumen_cliente(self.s, self.cliente.id).descuento_disponible, D("15.00"))
        self.mayorista.permite_descuento = False
        self.assertIsNone(mon.resumen_cliente(self.s, self.cliente.id).descuento_disponible)

    def test_con_descuento_no_genera_monedero(self) -> None:
        v = lib.registrar_operacion(self.s, employee_code="VEND-2", employee_name="Fanny", tipo="venta",
                                    items=[], monto_total=D("340"), cliente_id=self.cliente.id,
                                    operacion_uuid=str(uuid.uuid4()), descuento_programa=D("15"))
        self.assertEqual(v.descuento_programa, D("15.00"))
        self.assertEqual(self._cashbacks(), 0)
        self.assertEqual(mon.acreditar_faltantes(self.s), 0, "la red de seguridad tampoco lo abona")

    def test_sin_descuento_abona_su_15(self) -> None:
        v = lib.registrar_operacion(self.s, employee_code="VEND-2", employee_name="Fanny", tipo="venta",
                                    items=[], monto_total=D("400"), cliente_id=self.cliente.id,
                                    operacion_uuid=str(uuid.uuid4()))
        self.assertIsNone(v.descuento_programa)
        self.assertEqual(mon.resumen_cliente(self.s, self.cliente.id).disponible, D("60.00"))

    def test_la_cola_sube_el_descuento(self) -> None:
        entrada = {"employee_code": "VEND-2", "employee_name": "Fanny", "tipo": "venta",
                   "items": [{"sku": "P1", "nombre": "Pants", "talla": "10", "cantidad": 1, "precio": "400"},
                             {"sku": "PL", "nombre": "Playera", "talla": "8", "cantidad": 1, "precio": "100",
                              "promo_3pz": True}],
                   "monto_total": "440", "monto_neto": "440", "descuento_programa": "15",
                   "cliente_id": self.cliente.id, "operacion_uuid": str(uuid.uuid4()),
                   "created_at": datetime.now(UTC).isoformat()}
        cola._subir(self.s, entrada)
        v = self.s.scalars(select(LibretaVenta)).one()
        self.assertEqual(v.descuento_programa, D("15.00"))
        self.assertEqual([bool(l.get("promo_3pz")) for l in v.detalle], [False, True])
        self.assertEqual(self._cashbacks(), 0)

    def test_corregir_a_tarjeta_recalcula_con_el_mayoreo(self) -> None:
        items = [{"sku": "P1", "nombre": "Pants", "talla": "10", "cantidad": 1, "precio": "400"},
                 {"sku": "PL", "nombre": "Playera", "talla": "8", "cantidad": 1, "precio": "100", "promo_3pz": True}]
        v = lib.registrar_operacion(self.s, employee_code="VEND-2", employee_name="Fanny", tipo="venta",
                                    items=items, monto_total=D("440"), cliente_id=self.cliente.id,
                                    operacion_uuid=str(uuid.uuid4()), descuento_programa=D("15"))
        lib.cambiar_pago_tarjeta(self.s, v.id, True)
        esperado = lib.aplicar_comision_terminal(D("340.00")) + lib.aplicar_comision_terminal(D("100"))
        self.assertEqual(v.monto_neto, esperado)


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _kiosko(self, descuento=D("15.00")):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code = "VEND-2"
        w._cliente = {"id": 9, "codigo": "CLI-000009", "nombre": "Papelería Ruiz", "por_qr": True, "en_linea": True,
                      "tiene_monedero": True, "estado": "activo", "disponible": D("0"), "tasa": D("15.00"),
                      "descuento_disponible": descuento, "proximo_vencimiento": None,
                      "monto_proximo_vencimiento": D("0")}
        w._items = [dict(PANTS), dict(PROMO_PLAYERA)]
        w._refresh_totals()
        return w


class KioskoTests(_Qt):
    def test_por_omision_va_al_monedero(self) -> None:
        w = self._kiosko()
        self.assertFalse(w._btn_descuento_programa.isHidden())
        self.assertEqual(w._btn_descuento_programa.text(), "🏷 Descuento 15 %")
        self.assertFalse(w._btn_descuento_programa.isChecked())
        self.assertEqual(w._compute_totals()[2], D("500"))
        self.assertEqual(w._cashback_estimado(D("500"), D("0")), D("75.00"))

    def test_al_elegir_descuento_baja_el_precio_y_no_suma_monedero(self) -> None:
        w = self._kiosko()
        w._btn_descuento_programa.click()
        self.assertEqual(w._compute_totals(), (D("500"), D("60.00"), D("440")))
        self.assertEqual(w._cashback_estimado(D("440"), D("0")), D("0"))
        self.assertIn("Precio de mayoreo", w._cliente_label.text())
        self.assertIn("mayoreo", w._total_meta.text())
        self.assertEqual(w._monto_neto_actual(D("440"), pago_tarjeta=True),
                         w._apply_terminal_commission(D("340.00")) + w._apply_terminal_commission(D("100")))

    def test_con_el_5_de_empleada_gana_el_mas_alto(self) -> None:
        w = self._kiosko()
        w._discount_active = True
        w._btn_descuento_programa.click()
        # Pants: 15 % (no 20); playera de promo: solo el 5 % de empleada.
        self.assertEqual(w._compute_totals()[1], D("65.00"))

    def test_lo_que_va_a_la_libreta(self) -> None:
        w = self._kiosko()
        w._btn_descuento_programa.click()
        entrada = _entrada(w)
        self.assertEqual(entrada["descuento_programa"], "15.00")
        self.assertEqual(entrada["monto_total"], "440.00")
        self.assertEqual(D(entrada["cashback_estimado"]), D("0"))
        self.assertEqual([bool(i.get("promo_3pz")) for i in entrada["items"]], [False, True])

    def test_sin_descuento_la_entrada_es_la_de_siempre(self) -> None:
        w = self._kiosko()
        entrada = _entrada(w)
        self.assertNotIn("descuento_programa", entrada)
        self.assertTrue(all("promo_3pz" not in i for i in entrada["items"]))

    def test_sin_programa_que_lo_permita_no_hay_boton(self) -> None:
        w = self._kiosko(descuento=None)
        self.assertTrue(w._btn_descuento_programa.isHidden())
        self.assertIsNone(w._pct_descuento_programa())

    def test_la_siguiente_venta_no_lo_hereda(self) -> None:
        w = self._kiosko()
        w._btn_descuento_programa.click()
        w._quitar_cliente()
        self.assertFalse(w._usar_descuento_programa)

    def test_el_ticket_dice_desc_mayoreo(self) -> None:
        w = self._kiosko()
        w._btn_descuento_programa.click()
        with patch.object(w, "_load_business_info", return_value=("Maximoda", "", "")):
            texto = w._build_venta_text()
        self.assertIn("Desc. mayoreo 15 %:", texto)
        self.assertIn("60.00", texto)
        self.assertIn("¡Hoy ahorraste $60!", texto)   # el mayoreo cuenta como ahorro

    def test_reimprimir_con_el_mayoreo_guardado(self) -> None:
        w = self._kiosko(descuento=None)
        detalle = [{"sku": "P1", "nombre": "Pants", "talla": "10", "cantidad": 1, "precio": "400"},
                   {"sku": "PL", "nombre": "Playera", "talla": "8", "cantidad": 1, "precio": "100", "promo_3pz": True}]
        with patch.object(w, "_load_business_info", return_value=("Maximoda", "", "")):
            texto = w.build_reprint_ticket(tipo="venta", detalle=detalle, cliente=None, employee_name="Fanny",
                                           descuento_empleada=False, created_at=datetime(2026, 11, 10, 12, 0),
                                           descuento_programa=D("15.00"))
        self.assertIn("Desc. mayoreo 15 %:", texto)
        self.assertIn("440.00", texto)
        self.assertIsNone(w._pct_descuento_programa(), "después de reimprimir todo queda como estaba")


def _entrada(w) -> dict:
    with patch.object(w, "_origen_satelite", return_value="Entrada"):
        (entrada,) = w._armar_anotacion("venta", cliente=None, pago_tarjeta=False, anticipo=None,
                                        anticipo_tarjeta=False)
    return entrada


if __name__ == "__main__":
    unittest.main()
