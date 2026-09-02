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

    def test_venta_registra_en_libreta(self) -> None:
        widget = self._make_widget()
        with patch.object(widget, "_load_business_info", return_value=("M", "", "")), \
                patch.object(widget, "_ask_venta_options", return_value=(False, False)), \
                patch.object(widget, "_drenar_libreta_en_background"), \
                patch(
                    "pos_uniformes.services.libreta_local_queue_service.encolar_operacion"
                ) as encolar, \
                patch("pos_uniformes.ui.views.quick_sale_view.route_tickets"):
            widget._on_ticket_venta()
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
        with patch.object(widget, "_load_business_info", return_value=("M", "", "")), \
                patch.object(widget, "_ask_venta_options", return_value=(False, True)), \
                patch.object(widget, "_drenar_libreta_en_background"), \
                patch(
                    "pos_uniformes.services.libreta_local_queue_service.encolar_operacion"
                ) as encolar, \
                patch("pos_uniformes.ui.views.quick_sale_view.route_tickets"):
            widget._on_ticket_venta()
        entry = encolar.call_args.args[0]
        self.assertTrue(entry["pago_tarjeta"])
        self.assertEqual(entry["monto_total"], "1030.00")
        # 515 - 4.5% = 492.00 por pieza (regla de redondeo) × 2 = 984.00
        self.assertEqual(entry["monto_neto"], "984.00")

    def test_reimpresion_no_duplica_registro(self) -> None:
        widget = self._make_widget()
        with patch.object(widget, "_load_business_info", return_value=("M", "", "")), \
                patch.object(widget, "_ask_venta_options", return_value=(False, False)), \
                patch.object(widget, "_drenar_libreta_en_background"), \
                patch(
                    "pos_uniformes.services.libreta_local_queue_service.encolar_operacion"
                ) as encolar, \
                patch("pos_uniformes.ui.views.quick_sale_view.route_tickets"):
            widget._on_ticket_venta()
            widget._on_ticket_venta()  # reimpresión del mismo carrito
        encolar.assert_called_once()

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
        routed.assert_called_once()  # el ticket sale aunque la libreta falle

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
            libreta_summary_table=MagicMock(),
            libreta_daily_table=MagicMock(),
            libreta_table=MagicMock(),
            libreta_titular_label=MagicMock(),
            libreta_hoy_button=MagicMock(),
            libreta_semana_button=MagicMock(),
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
        fake.libreta_summary_table.setVisible.assert_called_once_with(False)
        fake.libreta_daily_table.setVisible.assert_called_once_with(False)
        fake._refresh_libreta_view.assert_called_once()

    def test_dueno_ve_todo(self) -> None:
        fake = self._gate_scan("EMP:VEND-1")  # gafete del dueño
        self.assertTrue(fake._libreta_is_owner)
        fake.libreta_table.setColumnHidden.assert_called_once_with(6, False)
        fake.libreta_summary_table.setVisible.assert_called_once_with(True)
        fake.libreta_daily_table.setVisible.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
