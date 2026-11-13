"""Compras de empleadas a cuenta de su pago (Daniel, 2026-11-12).

«Pagan al momento, se les descuenta esa semana de su paga o de la siguiente,
siempre y cuando aún conserve el descuento que se ganó.» Solo con su nivel,
con el mismo tope que los préstamos y autorizado con el QR del dueño.
"""

from __future__ import annotations

import os
import unittest
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import CajaRetiro, Empleada, PrestamoEmpleada
from pos_uniformes.services import compra_a_cuenta_service as cac
from pos_uniformes.services import incentivo_empleada_service as inc
from pos_uniformes.services import prestamos_service as pr

SAB14 = date(2026, 11, 14)
CRISTAL = inc.EstadoCompradora("VEND-3", "Cristal", D("20"), D("3000"), D("0"))


class OpcionesTests(unittest.TestCase):
    def test_su_proximo_pago_y_el_siguiente(self):
        este, siguiente = cac.opciones_de_pago(SAB14, 7)
        self.assertEqual((este.fecha_pago, este.cobrar_desde), (SAB14, None))
        self.assertEqual(siguiente.fecha_pago, date(2026, 11, 21))
        # Se salta el pago del 14 aunque se lo paguen un par de días tarde.
        self.assertEqual(siguiente.cobrar_desde, date(2026, 11, 17))
        self.assertEqual(este.texto, "📅  Pago del sáb 14 nov")

    def test_sin_dia_de_pago_no_hay_opciones(self):
        self.assertEqual(cac.opciones_de_pago(None, 7), [])


class PorQueNoTests(unittest.TestCase):
    def test_con_su_nivel_y_cabe(self):
        self.assertIsNone(cac.por_que_no(CRISTAL, D("500"), D("700")))

    def test_sin_nivel_paga_al_momento(self):
        base = inc.EstadoCompradora("VEND-3", "Cristal", D("5"), D("3000"), D("0"))
        self.assertIn("Sin descuento de nivel", cac.por_que_no(base, D("100"), D("700")))

    def test_si_ya_se_acabo_su_tope_paga_al_momento(self):
        usada = inc.EstadoCompradora("VEND-3", "Cristal", D("20"), D("3000"), D("3000"))
        self.assertIn("Ya usó todo", cac.por_que_no(usada, D("100"), D("700")))

    def test_no_pasa_del_tope_de_prestamos(self):
        self.assertIn("$700.00", cac.por_que_no(CRISTAL, D("701"), D("700")))
        self.assertIn("Todavía no le cabe", cac.por_que_no(CRISTAL, D("1"), D("0")))

    def test_sin_compradora(self):
        self.assertIsNotNone(cac.por_que_no(None, D("1"), D("700")))


class RegistrarTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add(Empleada(codigo="VEND-3", nombre_completo="Cristal", activo=True))
        self.s.flush()
        p = patch.object(pr, "ganado_hasta_hoy", return_value=D("2000"))
        p.start()
        self.addCleanup(p.stop)

    def _registrar(self, opcion, monto="500"):
        return cac.registrar(self.s, employee_code="VEND-3", nombre="Cristal", monto=monto,
                             opcion=opcion, quien="VEND-1", folio="abcdef123456")

    def test_queda_por_autorizar_y_sale_del_cajon(self):
        este, _sig = cac.opciones_de_pago(SAB14, 7)
        p = self._registrar(este)
        self.assertEqual((p.estado, p.monto, p.cobrar_desde), (pr.PEDIDO, D("500.00"), None))
        self.assertIn("Compra a cuenta · pago del sáb 14 nov · ticket abcdef12", p.motivo)
        retiro = self.s.scalars(select(CajaRetiro)).one()
        self.assertEqual((retiro.monto, retiro.motivo), (D("500.00"), f"Compra a cuenta de Cristal · #{p.id}"))

    def test_autorizada_no_saca_otro_retiro(self):
        p = self._registrar(cac.opciones_de_pago(SAB14, 7)[0])
        pr.aprobar(self.s, p.id, quien="VEND-1")
        self.assertEqual(p.estado, pr.APROBADO)
        self.assertEqual(len(self.s.scalars(select(CajaRetiro)).all()), 1)
        self.assertEqual(pr.total_por_cobrar(self.s, "VEND-3", SAB14), D("500.00"))

    def test_sin_autorizar_se_quita_el_retiro_y_la_paga(self):
        p = self._registrar(cac.opciones_de_pago(SAB14, 7)[0])
        pr.rechazar(self.s, p.id, quien="VEND-1")
        self.assertEqual(self.s.scalars(select(CajaRetiro)).all(), [])
        self.assertEqual(pr.total_por_cobrar(self.s, "VEND-3"), D("0"))
        self.assertEqual([r.id for r in cac.rechazadas_recientes(self.s, "VEND-3")], [p.id])

    def test_un_prestamo_sigue_igual(self):
        p = pr.pedir(self.s, employee_code="VEND-3", nombre="Cristal", monto="300", motivo="renta")
        pr.aprobar(self.s, p.id, quien="VEND-1")
        retiro = self.s.scalars(select(CajaRetiro)).one()
        self.assertEqual(retiro.motivo, "Préstamo a Cristal")

    def test_cuenta_en_el_mismo_tope_que_los_prestamos(self):
        este, _sig = cac.opciones_de_pago(SAB14, 7)
        self._registrar(este, "1000")
        self.assertEqual(pr.disponible_para(self.s, "VEND-3"), D("400.00"))   # 70 % de 2000 − 1000
        with self.assertRaises(pr.NoSePuede):
            self._registrar(este, "401")

    def _venta_empleada(self, folio, descuento=True):
        from pos_uniformes.services import libreta_service as lib

        return lib.registrar_operacion(
            self.s, employee_code="VEND-3", employee_name="Cristal", tipo="venta",
            items=[{"sku": "S1", "nombre": "Pantalón", "precio": "369", "cantidad": 1}],
            monto_total=D("332"), descuento_empleada=descuento, compradora_code="VEND-3",
            operacion_uuid=folio,
        )

    def test_la_libreta_sabe_cual_venta_es_a_cuenta_y_como_va(self):
        """Daniel, 2026-11-12: «este dinero no entró… ¿puede verse de otro color?»"""
        folio = "abcdef12-0000-4000-8000-000000000001"
        venta = self._venta_empleada(folio)
        otra = self._venta_empleada("99999999-0000-4000-8000-000000000002")   # pagó al momento
        p = cac.registrar(self.s, employee_code="VEND-3", nombre="Cristal", monto="332",
                          opcion=cac.opciones_de_pago(SAB14, 7)[0], quien="VEND-1", folio=folio)
        self.assertEqual(cac.estados_en_libreta(self.s, [venta, otra]), {venta.id: cac.POR_AUTORIZAR})
        pr.aprobar(self.s, p.id, quien="VEND-1")
        self.assertEqual(cac.estados_en_libreta(self.s, [venta]), {venta.id: cac.AUTORIZADA})
        self.assertEqual(cac.etiqueta_libreta(cac.AUTORIZADA), "📅 A cuenta · autorizada")

    def test_el_aviso_dice_que_se_llevo_y_la_lista_las_separa(self):
        from pos_uniformes.services import telegram_prestamos_service as prs

        folio = "abcdef12-0000-4000-8000-000000000001"
        self._venta_empleada(folio)
        p = cac.registrar(self.s, employee_code="VEND-3", nombre="Cristal", monto="332",
                          opcion=cac.opciones_de_pago(SAB14, 7)[0], quien="VEND-1", folio=folio)
        pr.pedir(self.s, employee_code="VEND-3", nombre="Cristal", monto="20", motivo="comida")
        self.assertIn("Se llevó: Pantalón x1", prs.aviso_de_solicitud(p, session=self.s))
        with patch("pos_uniformes.services.telegram_service.teclado", side_effect=lambda filas: filas):
            texto, filas = prs.texto_y_botones(self.s)
        self.assertLess(texto.index("💵 PRÉSTAMOS"), texto.index("🛍️ COMPRAS A CUENTA"))
        self.assertNotIn("ticket", texto)
        etiquetas = [e for fila in filas for e, _d in fila]
        self.assertIn("✅ Cristal $332 a cuenta", etiquetas)
        self.assertIn("✖️ Que lo pague", etiquetas)

    def _corte(self):
        from datetime import datetime

        from pos_uniformes.services import corte_caja_service as cc
        from pos_uniformes.services import retiros_service as rs

        desde, hasta = datetime(2000, 1, 1), datetime(2100, 1, 1)
        rows = cc.operaciones_del_periodo(self.s, desde, hasta)
        return ([r.id for r in rows], [r.motivo for r in rs.retiros_del_periodo(self.s, desde, hasta)],
                rs.total_retiros(self.s, desde, hasta))

    def test_el_corte_no_ve_la_compra_a_cuenta_ni_su_retiro(self):
        """Daniel, 2026-11-12: «en el corte no quiero que aparezcan las compras
        a cuenta ni que se descuenten de la venta»."""
        folio = "abcdef12-0000-4000-8000-000000000001"
        compra = self._venta_empleada(folio)
        otra = self._venta_empleada("99999999-0000-4000-8000-000000000002")   # pagó al momento
        p = cac.registrar(self.s, employee_code="VEND-3", nombre="Cristal", monto="332",
                          opcion=cac.opciones_de_pago(SAB14, 7)[0], quien="VEND-1", folio=folio)
        from pos_uniformes.services import retiros_service as rs

        rs.registrar_retiro(self.s, monto="50", motivo="Proveedor", creado_por="VEND-1")
        ventas, retiros, total = self._corte()
        self.assertEqual(ventas, [otra.id])
        self.assertEqual((retiros, total), (["Proveedor"], D("50.00")))
        pr.aprobar(self.s, p.id, quien="VEND-1")
        self.assertEqual(self._corte()[0], [otra.id])
        self.assertNotIn(compra.id, self._corte()[0])

    def test_el_resumen_de_telegram_cuadra_con_el_corte(self):
        """Revisión de deuda, 2026-11-12: /resumen contaba la compra a cuenta
        como efectivo que entró, y no cuadraba con el corte."""
        from pos_uniformes.services import resumen_diario_service as rd

        folio = "abcdef12-0000-4000-8000-000000000001"
        self._venta_empleada(folio)
        self._venta_empleada("99999999-0000-4000-8000-000000000002")   # pagó al momento
        cac.registrar(self.s, employee_code="VEND-3", nombre="Cristal", monto="332",
                      opcion=cac.opciones_de_pago(SAB14, 7)[0], quien="VEND-1", folio=folio)
        d = rd.recolectar(self.s, todo_el_dia=True)
        self.assertEqual(d.efectivo, D("332.00"))   # solo la que sí pagó

    def test_si_no_la_autoriza_el_corte_si_la_espera(self):
        folio = "abcdef12-0000-4000-8000-000000000001"
        compra = self._venta_empleada(folio)
        p = cac.registrar(self.s, employee_code="VEND-3", nombre="Cristal", monto="332",
                          opcion=cac.opciones_de_pago(SAB14, 7)[0], quien="VEND-1", folio=folio)
        pr.rechazar(self.s, p.id, quien="VEND-1")
        self.assertEqual(self._corte(), ([compra.id], [], D("0.00")))

    def test_si_no_la_autoriza_vuelve_a_ser_venta(self):
        folio = "abcdef12-0000-4000-8000-000000000001"
        venta = self._venta_empleada(folio)
        p = cac.registrar(self.s, employee_code="VEND-3", nombre="Cristal", monto="332",
                          opcion=cac.opciones_de_pago(SAB14, 7)[0], quien="VEND-1", folio=folio)
        pr.rechazar(self.s, p.id, quien="VEND-1")
        self.assertEqual(cac.estados_en_libreta(self.s, [venta]), {})

    def test_lo_que_compra_una_empleada_no_da_comision(self):
        """Daniel, 2026-11-12: «no quiero que le cuente como comisión»."""
        self.assertEqual(self._venta_empleada("abcdef12-0000-4000-8000-000000000001").comisiones, 0)
        self.assertEqual(self._venta_empleada("abcdef12-0000-4000-8000-000000000003", descuento=False).comisiones, 1)

    def test_el_del_pago_siguiente_se_salta_el_proximo(self):
        este, siguiente = cac.opciones_de_pago(SAB14, 7)
        for op, monto in ((este, "300"), (siguiente, "200")):
            pr.aprobar(self.s, self._registrar(op, monto).id, quien="VEND-1")
        self.assertEqual(pr.total_por_cobrar(self.s, "VEND-3", SAB14), D("300.00"))
        self.assertEqual(pr.total_por_cobrar(self.s, "VEND-3", date(2026, 11, 21)), D("500.00"))
        self.assertEqual(pr.total_por_cobrar(self.s, "VEND-3"), D("500.00"))   # lo que debe en total
        pr.marcar_cobrados(self.s, "VEND-3", pago_id=None, hasta=SAB14)
        quedan = pr.por_cobrar(self.s, "VEND-3")
        self.assertEqual([(q.monto, q.cobrar_desde) for q in quedan], [(D("200.00"), date(2026, 11, 17))])


class BotTests(unittest.TestCase):
    def _compra(self):
        return SimpleNamespace(id=7, employee_code="VEND-3", employee_name="Cristal", monto=D("405.00"), tipo="compra_cuenta",
                               motivo="Compra a cuenta · pago del sáb 14 nov · ticket abcdef12")

    def test_el_aviso_dice_que_es_una_compra(self):
        from pos_uniformes.services import telegram_prestamos_service as prs

        texto = prs.aviso_de_solicitud(self._compra())
        self.assertTrue(texto.startswith("🛍️ COMPRA A CUENTA · Cristal compró a cuenta de su pago: $405.00"))
        self.assertIn("Se le descuenta completo en su pago del sáb 14 nov.", texto)
        self.assertIn("no entró dinero", texto)
        self.assertIn("la paga en caja", texto)
        self.assertNotIn("retiro", texto)      # palabra de sistema: confundía (2026-11-12)
        self.assertNotIn("ticket", texto)

    def test_al_decidir_dice_que_pasa_con_el_cajon(self):
        """Daniel, 2026-11-12: «queda medio confuso de entre y sale»."""
        from pos_uniformes.services import telegram_prestamos_service as prs

        si = prs.texto_al_decidir(self._compra(), True)
        self.assertIn("Compra a cuenta autorizada: Cristal, $405.00", si)
        self.assertIn("pago del sáb 14 nov", si)
        self.assertIn("El cajón no cambia", si)
        no = prs.texto_al_decidir(self._compra(), False)
        self.assertIn("NO autorizada: Cristal paga $405.00 en caja", no)
        self.assertIn("el corte sí espera esos $405.00", no)
        prestamo = SimpleNamespace(id=8, employee_code="VEND-3", employee_name="Cristal", monto=D("20"), motivo="comida")
        self.assertIn("Sale $20.00 del cajón", prs.texto_al_decidir(prestamo, True))
        self.assertIn("Del cajón no sale nada", prs.texto_al_decidir(prestamo, False))

    def test_sus_botones(self):
        from pos_uniformes.services import telegram_prestamos_service as prs

        with patch("pos_uniformes.services.telegram_service.teclado", side_effect=lambda filas: filas):
            filas = prs.botones_de(self._compra())
        self.assertEqual(filas[0], [("✅ Autorizar a Cristal", "pr:ok:7"), ("✖️ Que lo pague", "pr:no:7")])


class CajaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _kiosko(self):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code, w._employee_name = "VEND-2", "Fanny"
        w._poner_categorias = lambda items: None
        w._items = [{"sku": "S1", "nombre": "Pants", "talla": "8", "color": "", "precio": D("450.00"), "cantidad": 1}]
        w._discount_active = True
        w._compradora = CRISTAL
        w._refresh_totals()
        return w

    def test_le_ofrece_sus_dos_pagos(self):
        from PyQt6.QtCore import QTimer

        w = self._kiosko()
        opciones = cac.opciones_de_pago(SAB14, 7)
        visto = {}

        def _elegir():
            visto["textos"] = [b.text() for b in w._botones_a_cuenta]
            w._botones_a_cuenta[1].click()

        QTimer.singleShot(0, _elegir)
        with patch.object(cac, "opciones_para", return_value=(opciones, D("700"))), \
             patch("pos_uniformes.database.connection.get_session"):
            forma = w._ask_pago_empleada()
        self.assertEqual(visto["textos"], ["📅  Pago del sáb 14 nov", "📅  Pago del sáb 21 nov"])
        self.assertEqual(forma, opciones[1])

    def test_sin_su_nivel_solo_al_momento(self):
        from PyQt6.QtCore import QTimer

        w = self._kiosko()
        w._compradora = inc.EstadoCompradora("VEND-3", "Cristal", D("20"), D("3000"), D("3000"))

        def _ver():
            visto["botones"] = list(w._botones_a_cuenta)
            w._dialogo_pago_empleada.findChild(type(w._btn_cliente), "efectivo").click()

        visto = {}
        QTimer.singleShot(0, _ver)
        with patch.object(cac, "opciones_para", return_value=(cac.opciones_de_pago(SAB14, 7), D("700"))), \
             patch("pos_uniformes.database.connection.get_session"):
            forma = w._ask_pago_empleada()
        self.assertEqual((visto["botones"], forma), ([], "efectivo"))

    def test_la_copia_dice_que_fue_a_cuenta(self):
        w = self._kiosko()
        texto = w._build_employee_copy_text(a_cuenta=cac.opciones_de_pago(SAB14, 7)[0])
        self.assertIn("A CUENTA DE TU PAGO", texto)
        self.assertIn("Se descuenta el sáb 14 nov", texto)
        self.assertIn("Por autorizar", texto)


if __name__ == "__main__":
    unittest.main()
