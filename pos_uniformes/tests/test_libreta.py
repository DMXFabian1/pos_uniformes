"""Tests de la Libreta: registro digital de operaciones por empleada.

- El servicio arma la fila correcta (piezas, detalle, montos).
- Ventanas: hoy (día local) y semana calendario (lunes-domingo).
- La cola local nunca pierde operaciones y conserva la hora original.
- Venta rápida registra al generar ticket, sin duplicar en reimpresión.
- Privacidad: la vista de empleada oculta la columna de monto; la del dueño no.
"""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("POS_UNIFORMES_DB_HOST", "localhost")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.services import libreta_local_queue_service as cola
from pos_uniformes.services.libreta_service import (
    describir_detalle,
    registrar_operacion,
    resumir_por_empleada,
    ventana_hoy,
    ventana_semana,
)


class LibretaServiceTests(unittest.TestCase):
    def test_registrar_operacion_builds_row(self) -> None:
        session = MagicMock()
        entry = registrar_operacion(
            session,
            employee_code="vend-2",
            employee_name="Ana",
            tipo="venta",
            items=[
                {"sku": "SKU1", "nombre": "Pants", "talla": "6", "cantidad": 2, "precio": "515.00"},
                {"sku": "SKU2", "nombre": "Playera", "talla": "M", "cantidad": 1, "precio": "100.00"},
            ],
            monto_total=Decimal("1130.00"),
            descuento_empleada=False,
        )
        session.add.assert_called_once_with(entry)
        self.assertEqual(entry.employee_code, "VEND-2")  # normalizado
        self.assertEqual(entry.piezas, 3)
        self.assertEqual(entry.monto_total, Decimal("1130.00"))
        self.assertEqual(entry.detalle[0]["subtotal"], "1030.00")

    def test_registrar_respeta_created_at_explicito(self) -> None:
        session = MagicMock()
        original = datetime(2026, 9, 1, 12, 30, tzinfo=timezone.utc)
        entry = registrar_operacion(
            session,
            employee_code="VEND-2",
            employee_name="Ana",
            tipo="venta",
            items=[],
            monto_total=Decimal("0"),
            created_at=original,
        )
        self.assertEqual(entry.created_at, original)

    def test_ventana_semana_es_lunes_a_domingo(self) -> None:
        # 2026-09-02 es miércoles → semana del lunes 31/ago al domingo 6/sep
        inicio, fin = ventana_semana(date(2026, 9, 2))
        self.assertEqual(inicio.date(), date(2026, 8, 31))
        self.assertEqual(fin.date(), date(2026, 9, 6))
        self.assertEqual(inicio.weekday(), 0)  # lunes

    def test_ventana_hoy_cubre_dia_local(self) -> None:
        inicio, fin = ventana_hoy(date(2026, 9, 2))
        self.assertEqual(inicio.date(), date(2026, 9, 2))
        self.assertEqual(fin.date(), date(2026, 9, 2))

    def test_resumir_por_empleada(self) -> None:
        rows = [
            SimpleNamespace(employee_code="VEND-2", employee_name="Ana", piezas=3, comisiones=3, monto_total=Decimal("100")),
            SimpleNamespace(employee_code="VEND-3", employee_name="Bere", piezas=5, comisiones=7, monto_total=Decimal("200")),
            SimpleNamespace(employee_code="VEND-2", employee_name="Ana", piezas=1, comisiones=1, monto_total=Decimal("50")),
        ]
        resumen = resumir_por_empleada(rows)
        self.assertEqual(resumen[0].employee_code, "VEND-3")  # más comisiones primero
        ana = next(r for r in resumen if r.employee_code == "VEND-2")
        self.assertEqual(ana.operaciones, 2)
        self.assertEqual(ana.piezas, 4)
        self.assertEqual(ana.comisiones, 4)
        self.assertEqual(ana.monto_total, Decimal("150.00"))

    def test_resumir_por_dia_separa_ventas_apartados_y_abonos(self) -> None:
        from pos_uniformes.services.libreta_service import resumir_por_dia

        lunes = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc).astimezone()
        martes = datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc).astimezone()
        rows = [
            # Venta con TARJETA: cuenta en ventas/neto pero NO en caja
            SimpleNamespace(created_at=lunes, tipo="venta", piezas=2,
                            monto_total=Decimal("500"), monto_neto=Decimal("477.50"),
                            pago_tarjeta=True),
            SimpleNamespace(created_at=lunes, tipo="apartado", piezas=3,
                            monto_total=Decimal("900"), monto_neto=Decimal("900"),
                            pago_tarjeta=False),
            # Abono en efectivo: SÍ está en caja
            SimpleNamespace(created_at=lunes, tipo="abono", piezas=0,
                            monto_total=Decimal("200"), monto_neto=Decimal("200"),
                            pago_tarjeta=False),
            # Venta en efectivo: SÍ está en caja
            SimpleNamespace(created_at=lunes, tipo="venta", piezas=1,
                            monto_total=Decimal("300"), monto_neto=Decimal("300"),
                            pago_tarjeta=False),
            SimpleNamespace(created_at=martes, tipo="venta", piezas=1,
                            monto_total=Decimal("100"), monto_neto=Decimal("100"),
                            pago_tarjeta=False),
        ]
        cortes = resumir_por_dia(rows)
        self.assertEqual(len(cortes), 2)
        self.assertEqual(cortes[0].dia, martes.date())  # más reciente primero
        lunes_corte = cortes[1]
        self.assertEqual(lunes_corte.operaciones, 4)
        self.assertEqual(lunes_corte.piezas, 6)
        # Ventas, neto (tras tarjeta), apartados y abonos, cada uno aparte
        self.assertEqual(lunes_corte.monto_ventas, Decimal("800.00"))
        self.assertEqual(lunes_corte.monto_neto_ventas, Decimal("777.50"))
        self.assertEqual(lunes_corte.monto_apartados, Decimal("900.00"))
        self.assertEqual(lunes_corte.monto_abonos, Decimal("200.00"))
        # EN CAJA: venta efectivo 300 + abono efectivo 200 (la venta con
        # tarjeta no está en el cajón; el apartado no es dinero recibido)
        self.assertEqual(lunes_corte.monto_en_caja, Decimal("500.00"))

    def test_comisiones_regla_3pz(self) -> None:
        from pos_uniformes.services.libreta_service import comisiones_de_items

        items = [
            {"nombre": "Pants 3pz Deportivo", "cantidad": 2},  # 3 × 2 = 6
            {"nombre": "Pants 2pz Deportivo", "cantidad": 2},  # 1 × 2 = 2
            {"nombre": "Sueter Escolar", "cantidad": 1},       # 1
        ]
        self.assertEqual(comisiones_de_items(items), 9)

    def test_registrar_calcula_comisiones_y_abono_cero(self) -> None:
        session = MagicMock()
        entry = registrar_operacion(
            session,
            employee_code="VEND-2",
            employee_name="Ana",
            tipo="apartado",
            items=[{"sku": "S", "nombre": "Pants 3pz", "talla": "6", "cantidad": 2, "precio": "600"}],
            monto_total=Decimal("1200"),
        )
        self.assertEqual(entry.comisiones, 6)  # apartado SÍ da comisiones
        abono = registrar_operacion(
            session,
            employee_code="VEND-2",
            employee_name="Ana",
            tipo="abono",
            items=[],
            monto_total=Decimal("200"),
            comisiones=0,
        )
        self.assertEqual(abono.comisiones, 0)
        self.assertEqual(abono.monto_neto, Decimal("200.00"))  # default = total

    def test_describir_detalle(self) -> None:
        texto = describir_detalle(
            [
                {"nombre": "Pants", "talla": "6", "cantidad": 2},
                {"nombre": "Playera", "talla": "-", "cantidad": 1},
            ]
        )
        self.assertEqual(texto, "Pants T:6 x2 · Playera x1")


class LibretaQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(
            os.environ.get("TMPDIR", "/tmp")
        ) / f"libreta_test_{os.getpid()}_{id(self)}"
        self._patcher = patch(
            "pos_uniformes.services.libreta_local_queue_service.satellite_data_dir",
            return_value=self._tmp,
        )
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        queue_file = self._tmp / "data" / "libreta_pendiente.json"
        if queue_file.exists():
            queue_file.unlink()

    def test_encolar_y_drenar(self) -> None:
        cola.encolar_operacion(
            {
                "employee_code": "VEND-2",
                "employee_name": "Ana",
                "tipo": "venta",
                "items": [{"sku": "S", "nombre": "P", "talla": "6", "cantidad": 2, "precio": "10"}],
                "monto_total": "20.00",
                "created_at": "2026-09-01T12:30:00+00:00",
            }
        )
        self.assertEqual(len(cola.pendientes()), 1)
        session = MagicMock()
        subidas = cola.drenar_pendientes(session)
        self.assertEqual(subidas, 1)
        session.commit.assert_called_once()
        self.assertEqual(cola.pendientes(), [])  # cola vacía tras subir

    def test_drenado_fallido_conserva_la_cola(self) -> None:
        cola.encolar_operacion({"employee_code": "VEND-2", "tipo": "venta", "items": [], "monto_total": "0"})
        session = MagicMock()
        session.commit.side_effect = RuntimeError("sin red")
        with self.assertRaises(RuntimeError):
            cola.drenar_pendientes(session)
        self.assertEqual(len(cola.pendientes()), 1)  # nada se perdió

    def test_archivo_corrupto_no_truena(self) -> None:
        path = self._tmp / "data" / "libreta_pendiente.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{corrupto", encoding="utf-8")
        self.assertEqual(cola.pendientes(), [])
        cola.encolar_operacion({"employee_code": "X", "tipo": "venta", "items": [], "monto_total": "0"})
        self.assertEqual(len(cola.pendientes()), 1)


class QuickSaleLibretaHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _make_widget(self):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        satellite = SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None)
        widget = QuickSaleWidget(satellite)
        widget._employee_code = "VEND-2"
        widget._employee_name = "Ana"
        widget._items = [
            {"sku": "SKU1", "nombre": "Pants", "talla": "6", "color": "",
             "precio": Decimal("515.00"), "cantidad": 2},
        ]
        return widget

    def _run_venta(self, widget, encolar, *, card: bool = False) -> None:
        """Dispara Ticket Venta y simula que la impresión SÍ arrancó."""
        llamadas_previas = encolar.call_count
        with patch.object(widget, "_load_business_info", return_value=("M", "", "")), \
                patch.object(widget, "_ask_venta_options", return_value=(False, card)), \
                patch.object(widget, "_drenar_libreta_en_background"), \
                patch("pos_uniformes.ui.views.quick_sale_view.route_tickets") as route:
            widget._on_ticket_venta()
            # Nada se registra hasta que la impresión arranca de verdad.
            self.assertEqual(encolar.call_count, llamadas_previas)
            route.call_args.kwargs["on_printed"]()

    def test_venta_registra_en_libreta(self) -> None:
        widget = self._make_widget()
        with patch(
            "pos_uniformes.services.libreta_local_queue_service.encolar_operacion"
        ) as encolar:
            self._run_venta(widget, encolar)
        encolar.assert_called_once()
        entry = encolar.call_args.args[0]
        self.assertEqual(entry["employee_code"], "VEND-2")
        self.assertEqual(entry["tipo"], "venta")
        self.assertEqual(entry["items"][0]["cantidad"], 2)
        self.assertEqual(entry["monto_total"], "1030.00")
        # Efectivo: neto = total, sin bandera de tarjeta.
        self.assertEqual(entry["monto_neto"], "1030.00")
        self.assertFalse(entry["pago_tarjeta"])

    def test_venta_con_tarjeta_registra_neto(self) -> None:
        widget = self._make_widget()
        with patch(
            "pos_uniformes.services.libreta_local_queue_service.encolar_operacion"
        ) as encolar:
            self._run_venta(widget, encolar, card=True)
        entry = encolar.call_args.args[0]
        self.assertTrue(entry["pago_tarjeta"])
        self.assertEqual(entry["monto_total"], "1030.00")
        # 515 - 4.5% = 492.00 por pieza (regla de redondeo) × 2 = 984.00
        self.assertEqual(entry["monto_neto"], "984.00")

    def test_reimpresion_no_duplica_registro(self) -> None:
        # Al arrancar la impresión el carrito se vacía, así que "volver a
        # imprimir" ya ni siquiera es posible: el segundo intento topa con
        # "Sin piezas" y no imprime ni registra nada.
        widget = self._make_widget()
        with patch(
            "pos_uniformes.services.libreta_local_queue_service.encolar_operacion"
        ) as encolar:
            self._run_venta(widget, encolar)
            self.assertEqual(widget._items, [])  # carrito vacío tras imprimir
            from PyQt6.QtWidgets import QMessageBox

            with patch.object(QMessageBox, "information") as aviso, \
                    patch("pos_uniformes.ui.views.quick_sale_view.route_tickets") as route:
                widget._on_ticket_venta()  # reintento con el carrito ya vacío
            aviso.assert_called_once()
            route.assert_not_called()
        encolar.assert_called_once()

    def test_cerrar_sin_imprimir_no_registra(self) -> None:
        # Se contesta el diálogo pero NUNCA se imprime: cero registro.
        widget = self._make_widget()
        with patch.object(widget, "_load_business_info", return_value=("M", "", "")), \
                patch.object(widget, "_ask_venta_options", return_value=(True, False)), \
                patch(
                    "pos_uniformes.services.libreta_local_queue_service.encolar_operacion"
                ) as encolar, \
                patch("pos_uniformes.ui.views.quick_sale_view.route_tickets"):
            widget._on_ticket_venta()
        encolar.assert_not_called()

    def test_registro_fallido_no_rompe_tickets(self) -> None:
        widget = self._make_widget()
        with patch.object(widget, "_load_business_info", return_value=("M", "", "")), \
                patch.object(widget, "_ask_venta_options", return_value=(False, False)), \
                patch(
                    "pos_uniformes.services.libreta_local_queue_service.encolar_operacion",
                    side_effect=OSError("disco lleno"),
                ), \
                patch("pos_uniformes.ui.views.quick_sale_view.route_tickets") as routed:
            widget._on_ticket_venta()
            # La impresión arrancó y la libreta falló: no debe tronar nada.
            routed.call_args.kwargs["on_printed"]()
        routed.assert_called_once()

    def test_abono_se_registra_sin_comision(self) -> None:
        widget = self._make_widget()
        with patch.object(widget, "_drenar_libreta_en_background"), \
                patch(
                    "pos_uniformes.services.libreta_local_queue_service.encolar_operacion"
                ) as encolar:
            widget._registrar_abono("Ana Lopez", Decimal("200.00"), pago_tarjeta=False)
        entry = encolar.call_args.args[0]
        self.assertEqual(entry["tipo"], "abono")
        self.assertEqual(entry["cliente"], "Ana Lopez")
        self.assertEqual(entry["monto_total"], "200.00")
        self.assertEqual(entry["comisiones"], 0)  # abonos no dan comisión

    def test_abono_sin_cliente_es_valido(self) -> None:
        # El nombre del cliente es opcional (petición de Daniel).
        widget = self._make_widget()
        with patch.object(widget, "_drenar_libreta_en_background"), \
                patch(
                    "pos_uniformes.services.libreta_local_queue_service.encolar_operacion"
                ) as encolar:
            widget._registrar_abono(None, Decimal("150.00"), pago_tarjeta=False)
        entry = encolar.call_args.args[0]
        self.assertIsNone(entry["cliente"])
        self.assertEqual(entry["monto_total"], "150.00")

    def test_abono_con_tarjeta_calcula_neto(self) -> None:
        widget = self._make_widget()
        with patch.object(widget, "_drenar_libreta_en_background"), \
                patch(
                    "pos_uniformes.services.libreta_local_queue_service.encolar_operacion"
                ) as encolar:
            widget._registrar_abono("Ana", Decimal("500.00"), pago_tarjeta=True)
        entry = encolar.call_args.args[0]
        self.assertTrue(entry["pago_tarjeta"])
        # 500 - 4.5% = 477.50 con la regla de redondeo
        self.assertEqual(entry["monto_neto"], "477.50")


class LibretaMetaServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(
            os.environ.get("TMPDIR", "/tmp")
        ) / f"libreta_meta_test_{os.getpid()}_{id(self)}"
        self._patcher = patch(
            "pos_uniformes.services.libreta_meta_service.satellite_data_dir",
            return_value=self._tmp,
        )
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()

    def test_default_sin_meta(self) -> None:
        from pos_uniformes.services.libreta_meta_service import load_meta_semanal

        self.assertEqual(load_meta_semanal(), 0)

    def test_guardar_y_leer(self) -> None:
        from pos_uniformes.services.libreta_meta_service import (
            load_meta_semanal,
            save_meta_semanal,
        )

        save_meta_semanal(50)
        self.assertEqual(load_meta_semanal(), 50)
        save_meta_semanal(-5)  # negativo se normaliza a 0
        self.assertEqual(load_meta_semanal(), 0)

    def test_archivo_corrupto_sin_meta(self) -> None:
        from pos_uniformes.services.libreta_meta_service import load_meta_semanal

        path = self._tmp / "data" / "libreta_meta.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{corrupto", encoding="utf-8")
        self.assertEqual(load_meta_semanal(), 0)


class FiltrarDeHoyTests(unittest.TestCase):
    def test_solo_deja_el_dia_pedido(self) -> None:
        from pos_uniformes.services.libreta_service import filtrar_de_hoy

        lunes = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc).astimezone()
        martes = datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc).astimezone()
        rows = [
            SimpleNamespace(created_at=lunes, tipo="venta"),
            SimpleNamespace(created_at=martes, tipo="venta"),
        ]
        hoy = filtrar_de_hoy(rows, reference=martes.date())
        self.assertEqual(len(hoy), 1)
        self.assertEqual(hoy[0].created_at, martes)


class CorteTicketTests(unittest.TestCase):
    def test_ticket_incluye_en_caja_y_empleadas(self) -> None:
        from pos_uniformes.services.libreta_service import CorteDia, ResumenEmpleada
        from pos_uniformes.ui.helpers.libreta_corte_ticket_helper import (
            build_corte_ticket_text,
        )
        from pos_uniformes.ui.helpers.ticket_print_layout_helper import TICKET_CHAR_WIDTH

        cortes = [
            CorteDia(
                dia=date(2026, 9, 2), dia_label="Mié 02/09", operaciones=3, piezas=5,
                monto_ventas=Decimal("800.00"), monto_neto_ventas=Decimal("777.50"),
                monto_apartados=Decimal("900.00"), monto_abonos=Decimal("200.00"),
                monto_en_caja=Decimal("500.00"),
            ),
        ]
        por_empleada = [
            ResumenEmpleada(
                employee_code="VEND-2", employee_name="Ana", operaciones=2,
                piezas=4, comisiones=6, monto_total=Decimal("700.00"),
            ),
        ]
        texto = build_corte_ticket_text(
            periodo_label="HOY", cortes=cortes, por_empleada=por_empleada,
            generado_por="VEND-1",
        )
        self.assertIn("CORTE DE LIBRETA", texto)
        self.assertIn("EN CAJA:", texto)
        self.assertIn("$500.00", texto)
        self.assertIn("Ana", texto)
        self.assertIn("6 com.", texto)
        # Ninguna línea se pasa del ancho del ticket térmico.
        for line in texto.splitlines():
            self.assertLessEqual(len(line), TICKET_CHAR_WIDTH)


class LibretaListaAmigableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_lista_habla_simple_y_sin_dinero(self) -> None:
        from PyQt6.QtWidgets import QListWidget

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(
            libreta_emp_list=QListWidget(),
            _libreta_periodo="hoy",
        )
        ahora = datetime(2026, 9, 2, 10, 32, tzinfo=timezone.utc).astimezone()
        rows = [
            SimpleNamespace(
                created_at=ahora, tipo="venta", piezas=2, comisiones=2,
                monto_total=Decimal("1030.00"), cliente=None,
                detalle=[{"nombre": "Pants", "talla": "6", "cantidad": 2}],
            ),
            SimpleNamespace(
                created_at=ahora, tipo="abono", piezas=0, comisiones=0,
                monto_total=Decimal("200.00"), cliente="Ana",
                detalle=[],
            ),
        ]
        QuoteSatelliteWindow._llenar_libreta_lista(fake, rows)
        textos = [
            fake.libreta_emp_list.item(i).text()
            for i in range(fake.libreta_emp_list.count())
        ]
        self.assertIn("Vendiste 2 pieza(s)", textos[0])
        self.assertIn("Pants T:6 x2", textos[0])
        self.assertIn("+2 com.", textos[0])
        self.assertIn("Recibiste un abono de Ana", textos[1])
        # Privacidad: NINGÚN monto en la vista de la empleada.
        for texto in textos:
            self.assertNotIn("$", texto)
            self.assertNotIn("1030", texto)
            self.assertNotIn("200", texto)


class EliminarOperacionTests(unittest.TestCase):
    def test_elimina_existente(self) -> None:
        from pos_uniformes.services.libreta_service import eliminar_operacion

        session = MagicMock()
        entry = object()
        session.get.return_value = entry
        self.assertTrue(eliminar_operacion(session, 5))
        session.delete.assert_called_once_with(entry)

    def test_inexistente_devuelve_false(self) -> None:
        from pos_uniformes.services.libreta_service import eliminar_operacion

        session = MagicMock()
        session.get.return_value = None
        self.assertFalse(eliminar_operacion(session, 99))
        session.delete.assert_not_called()


class BorrarRegistroLibretaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _fake_owner(self, rows, current_row: int):
        fake = SimpleNamespace(
            _libreta_is_owner=True,
            _libreta_rows_pintadas=rows,
            libreta_table=MagicMock(),
            _set_status=MagicMock(),
            _refresh_libreta_view=MagicMock(),
        )
        fake.libreta_table.currentRow.return_value = current_row
        return fake

    def _row(self, entry_id):
        return SimpleNamespace(
            id=entry_id,
            created_at=datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc),
            tipo="venta",
            employee_name="Ana",
            employee_code="VEND-2",
            monto_total=Decimal("500.00"),
        )

    def test_borra_con_confirmacion(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = self._fake_owner([self._row(7)], current_row=0)
        ctx = MagicMock()
        ctx.__enter__.return_value = MagicMock()
        with patch(
            "pos_uniformes.ui.quote_satellite_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch(
            "pos_uniformes.ui.quote_satellite_window.get_session", return_value=ctx
        ), patch(
            "pos_uniformes.services.libreta_service.eliminar_operacion",
            return_value=True,
        ) as eliminar:
            QuoteSatelliteWindow._borrar_registro_libreta(fake)
        eliminar.assert_called_once()
        self.assertEqual(eliminar.call_args.args[1], 7)
        fake._refresh_libreta_view.assert_called_once()

    def test_cancelar_no_borra(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = self._fake_owner([self._row(7)], current_row=0)
        with patch(
            "pos_uniformes.ui.quote_satellite_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ), patch(
            "pos_uniformes.services.libreta_service.eliminar_operacion"
        ) as eliminar:
            QuoteSatelliteWindow._borrar_registro_libreta(fake)
        eliminar.assert_not_called()
        fake._refresh_libreta_view.assert_not_called()

    def test_empleada_no_puede_borrar(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = self._fake_owner([self._row(7)], current_row=0)
        fake._libreta_is_owner = False
        with patch(
            "pos_uniformes.services.libreta_service.eliminar_operacion"
        ) as eliminar:
            QuoteSatelliteWindow._borrar_registro_libreta(fake)
        eliminar.assert_not_called()


class LibretaPeriodosYFiltrosTests(unittest.TestCase):
    """Semana pasada, rango por calendario y filtros de la vista del dueño."""

    def test_ventana_semana_anterior_es_lunes_a_domingo_previos(self) -> None:
        from pos_uniformes.services.libreta_service import ventana_semana_anterior

        # 2026-09-02 es miércoles → semana pasada: lun 24/ago a dom 30/ago
        inicio, fin = ventana_semana_anterior(date(2026, 9, 2))
        self.assertEqual(inicio.date(), date(2026, 8, 24))
        self.assertEqual(fin.date(), date(2026, 8, 30))
        self.assertEqual(inicio.weekday(), 0)

    def test_ventana_rango_corrige_fechas_volteadas(self) -> None:
        from pos_uniformes.services.libreta_service import ventana_rango

        inicio, fin = ventana_rango(date(2026, 9, 10), date(2026, 9, 1))
        self.assertEqual(inicio.date(), date(2026, 9, 1))
        self.assertEqual(fin.date(), date(2026, 9, 10))

    def test_filtrar_operaciones(self) -> None:
        from pos_uniformes.services.libreta_service import filtrar_operaciones

        rows = [
            SimpleNamespace(tipo="venta", employee_code="VEND-2", pago_tarjeta=True),
            SimpleNamespace(tipo="venta", employee_code="VEND-3", pago_tarjeta=False),
            SimpleNamespace(tipo="abono", employee_code="VEND-2", pago_tarjeta=False),
        ]
        self.assertEqual(len(filtrar_operaciones(rows, tipo="venta")), 2)
        self.assertEqual(len(filtrar_operaciones(rows, employee_code="vend-2")), 2)
        self.assertEqual(len(filtrar_operaciones(rows, solo_tarjeta=True)), 1)
        combinado = filtrar_operaciones(rows, tipo="venta", employee_code="VEND-2")
        self.assertEqual(len(combinado), 1)

    def test_lineas_detalle_respeta_privacidad(self) -> None:
        from pos_uniformes.services.libreta_service import lineas_detalle

        detalle = [
            {"nombre": "Pants", "talla": "6", "cantidad": 2,
             "precio": "515.00", "subtotal": "1030.00"},
        ]
        con = lineas_detalle(detalle, con_precios=True)
        sin = lineas_detalle(detalle, con_precios=False)
        self.assertEqual(con[0], ["Pants", "6", "2", "$515.00", "$1,030.00"])
        self.assertEqual(sin[0], ["Pants", "6", "2"])  # ni un peso para empleadas

    def test_set_periodo_y_toggle_de_empleada(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(
            _libreta_periodo="hoy",
            _libreta_emp_filtro=None,
            _libreta_ranking_codes=["VEND-2", "VEND-3"],
            libreta_ranking_list=MagicMock(),
            _sync_libreta_filtros=MagicMock(),
            _refresh_libreta_view=MagicMock(),
        )
        QuoteSatelliteWindow._set_libreta_periodo(fake, "semana_pasada")
        self.assertEqual(fake._libreta_periodo, "semana_pasada")
        fake._refresh_libreta_view.assert_called_once()

        # Clic en una empleada filtra; clic en la misma quita el filtro.
        fake.libreta_ranking_list.row.return_value = 0
        QuoteSatelliteWindow._on_libreta_ranking_click(fake, MagicMock())
        self.assertEqual(fake._libreta_emp_filtro, "VEND-2")
        QuoteSatelliteWindow._on_libreta_ranking_click(fake, MagicMock())
        self.assertIsNone(fake._libreta_emp_filtro)


class LibretaCicloBannerTests(unittest.TestCase):
    """Banner "Comisiones desde tu último pago" en la vista de la empleada."""

    def test_sin_ciclo_configurado_devuelve_none(self) -> None:
        from datetime import date as _date

        from pos_uniformes.services.calendario_empleadas_service import HorarioEmpleada
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        vacio = HorarioEmpleada(employee_code="VEND-2")
        fake = SimpleNamespace(_libreta_code="VEND-2")
        with patch(
            "pos_uniformes.services.calendario_empleadas_service.cargar_horario",
            return_value=vacio,
        ):
            texto = QuoteSatelliteWindow._texto_ciclo_libreta(fake, session=MagicMock())
        self.assertIsNone(texto)

    def test_con_ciclo_arma_el_banner(self) -> None:
        from datetime import date as _date

        from pos_uniformes.services.calendario_empleadas_service import HorarioEmpleada
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        horario = HorarioEmpleada(
            employee_code="VEND-2",
            descanso_weekday=3,
            ciclo_dias_pago=6,
            fecha_ultimo_pago=_date.today(),
        )
        fake = SimpleNamespace(_libreta_code="VEND-2")
        with patch(
            "pos_uniformes.services.calendario_empleadas_service.cargar_horario",
            return_value=horario,
        ), patch(
            "pos_uniformes.services.calendario_empleadas_service.comisiones_desde_ultimo_pago",
            return_value=47,
        ):
            texto = QuoteSatelliteWindow._texto_ciclo_libreta(fake, session=MagicMock())
        self.assertIn("Comisiones desde tu último pago: 47", texto)
        self.assertIn("jueves", texto)


class LibretaAutoLogoutTests(unittest.TestCase):
    """Salir de la página Libreta cierra la sesión (no queda abierta la
    vista del dueño con dinero en el kiosko)."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_navegar_a_otra_pagina_cierra_libreta(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(_libreta_code="VEND-1", _libreta_logout=MagicMock())
        try:
            QuoteSatelliteWindow._set_page(fake, "kiosk")
        except AttributeError:
            pass  # el resto del método necesita widgets reales; no importa aquí
        fake._libreta_logout.assert_called_once()

    def test_esc_en_libreta_cierra_sesion(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(
            _search_results_widget=None,
            current_page_key="libreta",
            _libreta_code="VEND-1",
            _libreta_logout=MagicMock(),
        )
        QuoteSatelliteWindow._handle_escape_key(fake)
        fake._libreta_logout.assert_called_once()

    def test_esc_sin_sesion_libreta_no_hace_nada(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(
            _search_results_widget=None,
            current_page_key="libreta",
            _libreta_code=None,
            _libreta_logout=MagicMock(),
        )
        try:
            QuoteSatelliteWindow._handle_escape_key(fake)
        except AttributeError:
            pass  # cae a las ramas de otras páginas, que usan widgets reales
        fake._libreta_logout.assert_not_called()

    def test_entrar_a_libreta_enfoca_el_gafete(self) -> None:
        # Réplica del comportamiento de venta rápida: al entrar a la página,
        # el cursor cae solo en el campo del gafete.
        import inspect

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        source = inspect.getsource(QuoteSatelliteWindow._set_page)
        self.assertIn("libreta_gate_input.setFocus", source)

    def test_quedarse_en_libreta_no_cierra(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(_libreta_code="VEND-1", _libreta_logout=MagicMock())
        try:
            QuoteSatelliteWindow._set_page(fake, "libreta")
        except AttributeError:
            pass
        fake._libreta_logout.assert_not_called()


class LibretaPagePrivacyTests(unittest.TestCase):
    """El gate decide qué se ve: empleada sin montos, dueño con todo."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _gate_scan(self, code: str):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(
            libreta_gate_input=MagicMock(),
            libreta_gate_error=MagicMock(),
            libreta_gate=MagicMock(),
            libreta_view=MagicMock(),
            libreta_owner_panel=MagicMock(),
            libreta_owner_bar=MagicMock(),
            libreta_meta_bar=MagicMock(),
            libreta_meta_spin=MagicMock(),
            libreta_emp_list=MagicMock(),
            libreta_table=MagicMock(),
            libreta_titular_label=MagicMock(),
            _sync_libreta_filtros=MagicMock(),
            _refresh_libreta_view=MagicMock(),
        )
        fake.libreta_gate_input.text.return_value = code
        QuoteSatelliteWindow._on_libreta_gate_scan(fake)
        return fake

    def test_empleada_no_ve_montos(self) -> None:
        fake = self._gate_scan("EMP:VEND-2")
        self.assertFalse(fake._libreta_is_owner)
        # Columna de monto oculta y sin resumen por empleada
        fake.libreta_table.setColumnHidden.assert_called_once_with(6, True)
        # El panel técnico completo (corte, ranking, movimientos) y los
        # controles de corte/meta son del dueño, no de la empleada.
        fake.libreta_owner_panel.setVisible.assert_called_once_with(False)
        fake.libreta_owner_bar.setVisible.assert_called_once_with(False)
        # Ella ve su lista amigable.
        fake.libreta_emp_list.setVisible.assert_called_once_with(True)
        fake._refresh_libreta_view.assert_called_once()

    def test_dueno_ve_todo(self) -> None:
        fake = self._gate_scan("EMP:VEND-1")  # gafete del dueño
        self.assertTrue(fake._libreta_is_owner)
        fake.libreta_table.setColumnHidden.assert_called_once_with(6, False)
        fake.libreta_owner_panel.setVisible.assert_called_once_with(True)
        fake.libreta_owner_bar.setVisible.assert_called_once_with(True)
        fake.libreta_emp_list.setVisible.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
