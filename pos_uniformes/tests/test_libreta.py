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
        self.assertIn("VENTA DE HOY:", texto)
        self.assertIn("$500.00", texto)
        self.assertIn("Ana", texto)
        self.assertIn("6 com.", texto)
        # Corte minimalista: sin desglose de dinero, sin montos por empleada
        # y sin piezas (ni arriba ni por empleada).
        for palabra in ("Ventas:", "Neto", "Apartados:", "Abonos:", "Monto:", "$700.00",
                        "Piezas:", "pzas"):
            self.assertNotIn(palabra, texto)
        self.assertIn("2 ops:", texto)
        # Ninguna línea se pasa del ancho del ticket térmico.
        for line in texto.splitlines():
            self.assertLessEqual(len(line), TICKET_CHAR_WIDTH)

        # El dueño edita la cifra final: el ticket imprime SOLO esa cifra —
        # sin esperado, sin faltante, sin rastro de la edición.
        editado = build_corte_ticket_text(
            periodo_label="HOY", cortes=cortes, por_empleada=por_empleada,
            generado_por="VEND-1", efectivo_real=Decimal("480.00"),
            nota="cierre normal",
        )
        self.assertIn("VENTA DE HOY:", editado)
        self.assertIn("$480.00", editado)
        self.assertNotIn("$500.00", editado.split("POR DIA")[0])  # esperado NO sale
        for palabra in ("FALTANTE", "SOBRANTE", "CONTADO", "esperado"):
            self.assertNotIn(palabra, editado)
        self.assertIn("cierre normal", editado)
        for line in editado.splitlines():
            self.assertLessEqual(len(line), TICKET_CHAR_WIDTH)


class HistorialCortesTests(unittest.TestCase):
    """El corte guarda SOLO la cifra final del dueño; León ve fecha y cifra."""

    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.database.models import LibretaCorte, LibretaVenta

        engine = create_engine("sqlite://")
        LibretaCorte.__table__.create(engine)
        LibretaVenta.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()

    def tearDown(self) -> None:
        self.session.close()

    def test_guardar_y_listar_solo_cifra_final(self) -> None:
        from pos_uniformes.services.libreta_service import guardar_corte, listar_cortes

        guardar_corte(
            self.session, fecha=date(2026, 9, 3), monto_final=Decimal("15000.00"),
            operaciones=20, piezas=50, creado_por="VEND-1",
        )
        guardar_corte(
            self.session, fecha=date(2026, 9, 4), monto_final=Decimal("17180.00"),
            operaciones=29, piezas=76, nota="cierre normal", creado_por="VEND-1",
        )
        cortes = listar_cortes(self.session)
        self.assertEqual(len(cortes), 2)
        self.assertEqual(cortes[0].fecha, date(2026, 9, 4))  # más reciente primero
        self.assertEqual(cortes[0].monto_final, Decimal("17180.00"))
        # La tabla NO tiene columnas de esperado/diferencia: sin rastro.
        columnas = {c.name for c in cortes[0].__table__.columns}
        self.assertNotIn("monto_esperado", columnas)
        self.assertNotIn("diferencia", columnas)

    def test_leon_ve_fecha_y_cifra(self) -> None:
        import os as _os

        _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication, QLabel

        QApplication.instance() or QApplication([])
        from pos_uniformes.services.libreta_service import guardar_corte

        guardar_corte(
            self.session, fecha=date(2026, 9, 4), monto_final=Decimal("17180.00"),
            operaciones=29, piezas=76, creado_por="VEND-1",
        )
        cm = MagicMock()
        cm.__enter__ = lambda s: self.session
        cm.__exit__ = lambda s, *a: False
        with patch(
            "pos_uniformes.database.connection.get_session", return_value=cm
        ):
            from pos_uniformes.ui.dialogs.calendario_empleadas_dialog import (
                CalendarioEncargadoDialog,
            )

            dlg = CalendarioEncargadoDialog(None)
            dlg._ir_a_cortes()
            textos = [
                dlg._cortes_lista.itemAt(i).widget().text()
                for i in range(dlg._cortes_lista.count())
                if isinstance(dlg._cortes_lista.itemAt(i).widget(), QLabel)
            ]
        self.assertEqual(len(textos), 1)
        self.assertIn("viernes 4 de septiembre", textos[0])
        self.assertIn("$17,180.00", textos[0])
        # Solo cifras: sin operaciones, piezas ni notas en su vista.
        self.assertNotIn("29", textos[0])
        self.assertNotIn("76", textos[0])

    def test_leon_hace_corte_sin_poder_editar(self) -> None:
        import os as _os

        _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from datetime import datetime

        from PyQt6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])
        from pos_uniformes.database.models import LibretaCorte, LibretaVenta

        self.session.add(
            LibretaVenta(
                employee_code="VEND-4", employee_name="Fanny", tipo="venta",
                piezas=2, comisiones=2, monto_total=Decimal("500.00"),
                monto_neto=Decimal("500.00"), detalle=[],
                # naive local: sqlite compara fechas como texto y un offset
                # de zona rompería la ventana de hoy
                created_at=datetime.now(),
            )
        )
        self.session.commit()

        cm = MagicMock()
        cm.__enter__ = lambda s: self.session
        cm.__exit__ = lambda s, *a: False
        with patch(
            "pos_uniformes.database.connection.get_session", return_value=cm
        ), patch(
            "pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets"
        ) as imprimir:
            from pos_uniformes.ui.dialogs.calendario_empleadas_dialog import (
                CalendarioEncargadoDialog,
            )

            dlg = CalendarioEncargadoDialog(None)
            dlg._ir_a_corte_hoy()
            # La cifra mostrada es la CALCULADA — no hay campo para editarla.
            self.assertIn("$500.00", dlg._corte_texto.text())
            dlg._hacer_corte()
            imprimir.assert_called_once()

        guardado = self.session.query(LibretaCorte).one()
        self.assertEqual(guardado.monto_final, Decimal("500.00"))
        self.assertEqual(guardado.creado_por, "ENC-1")
        self.assertIn("Corte hecho", dlg._listo_texto.text())
        self.assertFalse(dlg._btn_deshacer.isVisible())  # un corte no se deshace


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


class VentanaCicloTests(unittest.TestCase):
    """El periodo "Mi ciclo"/"Su ciclo": desde el último pago hasta hoy —
    el desglose que respalda el banner de comisiones."""

    def test_ventana_arranca_el_dia_despues_del_pago(self) -> None:
        from datetime import date, timedelta

        from pos_uniformes.services.libreta_service import ventana_ciclo

        ultimo_pago = date.today() - timedelta(days=5)
        inicio, fin = ventana_ciclo(ultimo_pago)
        self.assertEqual(inicio.date(), ultimo_pago + timedelta(days=1))
        self.assertEqual(fin.date(), date.today())

    def test_sin_pago_registrado_cubre_90_dias(self) -> None:
        from datetime import date, timedelta

        from pos_uniformes.services.libreta_service import ventana_ciclo

        inicio, _fin = ventana_ciclo(None)
        self.assertEqual(inicio.date(), date.today() - timedelta(days=90))

    def test_dueno_sin_empleada_elegida_no_activa_el_ciclo(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(
            _libreta_is_owner=True,
            _libreta_emp_filtro=None,
            _libreta_periodo="hoy",
            _sync_libreta_filtros=MagicMock(),
            _refresh_libreta_view=MagicMock(),
        )
        from PyQt6.QtWidgets import QMessageBox

        with patch.object(QMessageBox, "information") as aviso:
            QuoteSatelliteWindow._set_libreta_periodo(fake, "ciclo")
        aviso.assert_called_once()
        self.assertEqual(fake._libreta_periodo, "hoy")  # no cambió
        fake._refresh_libreta_view.assert_not_called()

    def test_empleada_activa_su_ciclo_directo(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(
            _libreta_is_owner=False,
            _libreta_emp_filtro=None,
            _libreta_periodo="hoy",
            _sync_libreta_filtros=MagicMock(),
            _refresh_libreta_view=MagicMock(),
        )
        QuoteSatelliteWindow._set_libreta_periodo(fake, "ciclo")
        self.assertEqual(fake._libreta_periodo, "ciclo")
        fake._refresh_libreta_view.assert_called_once()


class GateLibretaValidaTests(unittest.TestCase):
    """Un código inventado NO abre la Libreta; los reales sí."""

    def _fake(self, valido: bool):
        fake = SimpleNamespace(
            libreta_gate_input=SimpleNamespace(
                text=lambda: "CUALQUIERA", clear=MagicMock(), setFocus=MagicMock()
            ),
            libreta_gate_error=MagicMock(),
            _gafete_libreta_valido=lambda code: valido,
            _libreta_code=None,
        )
        return fake

    def test_codigo_invalido_no_abre_y_muestra_error(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = self._fake(valido=False)
        QuoteSatelliteWindow._on_libreta_gate_scan(fake)
        self.assertIsNone(fake._libreta_code)
        fake.libreta_gate_error.setVisible.assert_called_with(True)

    def test_validador_offline_exige_formato_vend(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(offline_mode=True)
        valido = QuoteSatelliteWindow._gafete_libreta_valido
        self.assertTrue(valido(fake, "VEND-2"))
        self.assertFalse(valido(fake, "PATITO"))

    def test_validador_online_consulta_empleada(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.database.models import Empleada
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        engine = create_engine("sqlite://")
        Empleada.__table__.create(engine)
        session = sessionmaker(bind=engine)()
        session.add(Empleada(codigo="VEND-2", nombre_completo="Ana", activo=True))
        session.add(Empleada(codigo="VEND-9", nombre_completo="Baja", activo=False))
        session.commit()

        cm = MagicMock()
        cm.__enter__ = lambda s: session
        cm.__exit__ = lambda s, *a: False
        fake = SimpleNamespace(offline_mode=False)
        with patch(
            "pos_uniformes.ui.quote_satellite_window.get_session", return_value=cm
        ):
            valido = QuoteSatelliteWindow._gafete_libreta_valido
            self.assertTrue(valido(fake, "VEND-2"))
            self.assertFalse(valido(fake, "VEND-9"))  # inactiva
            self.assertFalse(valido(fake, "NOEXISTE"))
        session.close()


class ColaCortesOfflineTests(unittest.TestCase):
    """Un corte sin conexión cae a la cola local y sube al reconectar."""

    def test_encolar_y_drenar_corte(self) -> None:
        import tempfile
        from pathlib import Path

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.database.models import LibretaCorte

        engine = create_engine("sqlite://")
        LibretaCorte.__table__.create(engine)
        session = sessionmaker(bind=engine)()

        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "pos_uniformes.services.libreta_local_queue_service.satellite_data_dir",
                return_value=Path(tmp),
            ):
                cola.encolar_corte(
                    {
                        "fecha": "2026-09-04",
                        "monto_final": "17180.00",
                        "operaciones": 29,
                        "piezas": 76,
                        "periodo_label": "HOY",
                        "nota": "",
                        "creado_por": "VEND-1",
                    }
                )
                self.assertEqual(len(cola.cortes_pendientes()), 1)
                subidos = cola.drenar_cortes(session)
                self.assertEqual(subidos, 1)
                self.assertEqual(cola.cortes_pendientes(), [])

        guardado = session.query(LibretaCorte).one()
        self.assertEqual(str(guardado.monto_final), "17180.00")
        self.assertEqual(guardado.fecha, date(2026, 9, 4))  # conserva su fecha
        self.assertEqual(guardado.creado_por, "VEND-1")
        session.close()

    def test_drenado_fallido_conserva_el_corte(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "pos_uniformes.services.libreta_local_queue_service.satellite_data_dir",
                return_value=Path(tmp),
            ):
                cola.encolar_corte(
                    {"fecha": "2026-09-04", "monto_final": "100.00", "creado_por": "VEND-1"}
                )
                sesion_rota = MagicMock()
                with patch(
                    "pos_uniformes.services.libreta_service.guardar_corte",
                    side_effect=OSError("sin red"),
                ):
                    subidos = cola.drenar_cortes(sesion_rota)
                self.assertEqual(subidos, 0)
                self.assertEqual(len(cola.cortes_pendientes()), 1)  # sigue ahí


class GafeteEncargadoTests(unittest.TestCase):
    """El gafete ENC-1 abre el calendario en modo encargado, sin entrar a
    la Libreta (no ve dinero)."""

    def test_enc1_va_directo_al_calendario(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(
            libreta_gate_input=SimpleNamespace(text=lambda: "ENC-1", clear=MagicMock()),
            _abrir_calendario_encargado=MagicMock(),
            _libreta_code=None,
        )
        QuoteSatelliteWindow._on_libreta_gate_scan(fake)
        fake._abrir_calendario_encargado.assert_called_once()
        self.assertIsNone(fake._libreta_code)  # la Libreta no se abrió


class CalendarioEncargadoSimpleTests(unittest.TestCase):
    """El modo de León: botones por empleada (sin Daniel ni él mismo) y
    marca con nota de auditoría."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _fake_session(self, emps):
        class FakeQuery:
            def __init__(self, items):
                self.items = items

            def filter(self, *a):
                return self

            def order_by(self, *a):
                return self

            def all(self):
                return self.items

        sesion = MagicMock()
        sesion.query.return_value = FakeQuery(emps)
        cm = MagicMock()
        cm.__enter__ = lambda s: sesion
        cm.__exit__ = lambda s, *a: False
        return cm

    def test_botones_sin_daniel_ni_leon_y_marca_con_nota(self) -> None:
        from datetime import date

        from PyQt6.QtWidgets import QPushButton

        emps = [
            SimpleNamespace(codigo=c, nombre_completo=n, activo=True)
            for c, n in (
                ("VEND-4", "Fanny Ruiz"),
                ("ENC-1", "León Fabian"),
                ("VEND-1", "Daniel"),
            )
        ]
        with patch(
            "pos_uniformes.database.connection.get_session",
            return_value=self._fake_session(emps),
        ):
            from pos_uniformes.ui.dialogs.calendario_empleadas_dialog import (
                CalendarioEncargadoDialog,
            )

            dlg = CalendarioEncargadoDialog(None)
            dlg._ir_a_quien()  # el inicio ahora es el menú; esto entra a Apuntar
            textos = [
                dlg._quien_botones.itemAt(i).widget().text()
                for i in range(dlg._quien_botones.count())
                if isinstance(dlg._quien_botones.itemAt(i).widget(), QPushButton)
            ]
            self.assertEqual(textos, ["👤  Fanny"])

            dlg._elegir_empleada("VEND-4", "Fanny")
            dlg._sel_tipo = "falta"
            with patch(
                "pos_uniformes.ui.dialogs.calendario_empleadas_dialog.marcar_dia"
            ) as marcar:
                dlg._aplicar(date(2026, 9, 4))
            marcar.assert_called_once()
            self.assertEqual(marcar.call_args.args[1:], ("VEND-4", date(2026, 9, 4), "falta"))
            self.assertIn("ENC-1", marcar.call_args.kwargs["nota"])
            self.assertIn("Fanny faltó", dlg._listo_texto.text())


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
            libreta_ciclo_button=MagicMock(),
            _gafete_libreta_valido=lambda code: True,
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


class ScrollLibretaTests(unittest.TestCase):
    """En táctil la página scrollea completa: la tabla de movimientos crece
    con sus filas (sin scroll interno) para alcanzar la info de abajo."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_tabla_crece_con_las_filas(self) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QTableWidget

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        tabla = QTableWidget(0, 7)
        fake = SimpleNamespace(libreta_table=tabla)

        tabla.setRowCount(3)
        QuoteSatelliteWindow._ajustar_alto_tabla_libreta(fake)
        alto_3 = tabla.height()

        tabla.setRowCount(30)
        QuoteSatelliteWindow._ajustar_alto_tabla_libreta(fake)
        alto_30 = tabla.height()

        self.assertGreater(alto_30, alto_3 + 20 * tabla.rowHeight(0) - 1)
        self.assertGreaterEqual(alto_3, 120)


class PaginacionLibretaTests(unittest.TestCase):
    """Movimientos del dueño: 25 por página, con ◀ ▶ desde el caché."""

    def test_cambiar_pagina_repinta_del_cache(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        rows = ["r"] * 60
        fake = SimpleNamespace(
            _libreta_pagina=0,
            _libreta_last_pintura=(rows, None),
            _pintar_libreta=MagicMock(),
        )
        QuoteSatelliteWindow._cambiar_pagina_libreta(fake, 1)
        self.assertEqual(fake._libreta_pagina, 1)
        fake._pintar_libreta.assert_called_once_with(rows, ranking_rows=None)

        # Nunca por debajo de cero.
        fake._libreta_pagina = 0
        QuoteSatelliteWindow._cambiar_pagina_libreta(fake, -1)
        self.assertEqual(fake._libreta_pagina, 0)

    def test_sin_pintura_previa_no_truena(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = SimpleNamespace(_libreta_pagina=0)
        QuoteSatelliteWindow._cambiar_pagina_libreta(fake, 1)  # no explota
        self.assertEqual(fake._libreta_pagina, 1)


class KioskoIgnoraGafeteTests(unittest.TestCase):
    """En la pestaña Kiosko (consulta de precios) el gafete de una empleada
    NO se busca como producto: se ignora con aviso y se limpia el input."""

    def test_gafete_se_ignora_sin_buscar(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        entrada = MagicMock()
        entrada.text.return_value = "EMP:VEND-2"
        fake = SimpleNamespace(
            kiosk_scan_input=entrada,
            _set_status=MagicMock(),
            offline_mode=True,
            _kiosk_lookup_from_cache=MagicMock(),
        )
        QuoteSatelliteWindow._handle_lookup_scan(fake)
        entrada.clear.assert_called_once()
        fake._kiosk_lookup_from_cache.assert_not_called()  # no lo buscó
        self.assertIn("Gafete ignorado", fake._set_status.call_args.args[0])

    def test_gafete_con_teclado_espanol_tambien_se_ignora(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        entrada = MagicMock()
        entrada.text.return_value = "EMPÑVEND-2"  # el escáner manda Ñ por :
        fake = SimpleNamespace(
            kiosk_scan_input=entrada,
            _set_status=MagicMock(),
            offline_mode=True,
            _kiosk_lookup_from_cache=MagicMock(),
        )
        QuoteSatelliteWindow._handle_lookup_scan(fake)
        fake._kiosk_lookup_from_cache.assert_not_called()


class ReimprimirDesdeLibretaTests(unittest.TestCase):
    """El botón del dueño reimprime SIN on_printed (no re-registra)."""

    def _fake(self, row, owner=True, idx=0):
        widget = MagicMock()
        widget.build_reprint_ticket.return_value = "TEXTO DEL TICKET"
        return SimpleNamespace(
            _libreta_is_owner=owner,
            _libreta_rows_pintadas=[row],
            libreta_table=SimpleNamespace(currentRow=lambda: idx),
            quick_sale_widget=widget,
        )

    def test_reimprime_sin_registrar(self) -> None:
        from datetime import datetime

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        row = SimpleNamespace(
            tipo="venta", detalle=[{"sku": "S"}], cliente=None, employee_name="Fanny",
            employee_code="VEND-4", descuento_empleada=False, created_at=datetime(2026, 9, 5, 12, 0),
        )
        fake = self._fake(row)
        with patch("pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets") as ruta:
            QuoteSatelliteWindow._reimprimir_ticket_libreta(fake)
        ruta.assert_called_once()
        self.assertEqual(ruta.call_args.args[2], ["TEXTO DEL TICKET"])
        self.assertNotIn("on_printed", ruta.call_args.kwargs)  # jamás re-registra

    def test_empleada_no_puede_reimprimir(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fake = self._fake(SimpleNamespace(), owner=False)
        with patch("pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets") as ruta:
            QuoteSatelliteWindow._reimprimir_ticket_libreta(fake)
        ruta.assert_not_called()
        fake.quick_sale_widget.build_reprint_ticket.assert_not_called()



class CambiarPagoTarjetaTests(unittest.TestCase):
    """El dueño corrige tarjeta/efectivo de un registro y el neto se recalcula."""

    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pos_uniformes.database.models import LibretaVenta

        engine = create_engine("sqlite://")
        LibretaVenta.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()

    def tearDown(self) -> None:
        self.session.close()

    def test_a_tarjeta_recalcula_neto_y_de_regreso(self) -> None:
        from datetime import datetime

        from pos_uniformes.database.models import LibretaVenta
        from pos_uniformes.services.libreta_service import cambiar_pago_tarjeta

        venta = LibretaVenta(
            employee_code="VEND-4", employee_name="Fanny", tipo="venta", piezas=1,
            comisiones=1, monto_total=Decimal("515.00"), monto_neto=Decimal("515.00"),
            pago_tarjeta=False, descuento_empleada=False,
            detalle=[{"sku": "S", "nombre": "Pants", "talla": "6", "cantidad": 1,
                      "precio": "515.00", "subtotal": "515.00"}],
            created_at=datetime.now(),
        )
        self.session.add(venta); self.session.commit()

        cambiar_pago_tarjeta(self.session, venta.id, True)
        self.assertTrue(venta.pago_tarjeta)
        # 515 − 4.5% = 491.82 → regla de redondeo de la tienda → 492.00
        self.assertEqual(venta.monto_neto, Decimal("492.00"))

        cambiar_pago_tarjeta(self.session, venta.id, False)
        self.assertFalse(venta.pago_tarjeta)
        self.assertEqual(venta.monto_neto, Decimal("515.00"))

    def test_abono_sin_detalle_usa_el_monto(self) -> None:
        from datetime import datetime

        from pos_uniformes.database.models import LibretaVenta
        from pos_uniformes.services.libreta_service import (
            aplicar_comision_terminal,
            cambiar_pago_tarjeta,
        )

        abono = LibretaVenta(
            employee_code="VEND-4", employee_name="Fanny", tipo="abono", piezas=0,
            comisiones=0, monto_total=Decimal("200.00"), monto_neto=Decimal("200.00"),
            detalle=[], created_at=datetime.now(),
        )
        self.session.add(abono); self.session.commit()
        cambiar_pago_tarjeta(self.session, abono.id, True)
        self.assertEqual(abono.monto_neto, aplicar_comision_terminal(Decimal("200.00")))

    def test_inexistente_devuelve_none(self) -> None:
        from pos_uniformes.services.libreta_service import cambiar_pago_tarjeta

        self.assertIsNone(cambiar_pago_tarjeta(self.session, 999, True))

    def test_boton_del_dueno_alterna_con_confirmacion(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        row = SimpleNamespace(id=7, pago_tarjeta=False)
        fake = SimpleNamespace(
            _libreta_is_owner=True,
            _libreta_rows_pintadas=[row],
            libreta_table=SimpleNamespace(currentRow=lambda: 0),
            _set_status=MagicMock(),
            _refresh_libreta_view=MagicMock(),
        )
        cm = MagicMock(); cm.__enter__ = lambda s: "sesion"; cm.__exit__ = lambda s, *a: False
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
                patch("pos_uniformes.ui.quote_satellite_window.get_session", return_value=cm), \
                patch("pos_uniformes.services.libreta_service.cambiar_pago_tarjeta") as cambiar:
            QuoteSatelliteWindow._cambiar_pago_libreta(fake)
        cambiar.assert_called_once_with("sesion", 7, True)  # efectivo → tarjeta
        fake._refresh_libreta_view.assert_called_once()

        # Una empleada no puede.
        fake._libreta_is_owner = False
        with patch("pos_uniformes.services.libreta_service.cambiar_pago_tarjeta") as cambiar:
            QuoteSatelliteWindow._cambiar_pago_libreta(fake)
        cambiar.assert_not_called()


class LibretaDuenoRedisenoTests(unittest.TestCase):
    """Vista del dueño sin saturar: tarjetas que no se confunden entre sí,
    desglose por día solo en periodos de varios días, y lo ocasional
    (rango/meta) plegado bajo "Más opciones"."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _ventana_dueno(self):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        win = QuoteSatelliteWindow(user_id=1, offline_mode=True)
        win._libreta_is_owner = True
        win._libreta_emp_filtro = "VEND-2"
        return win

    @staticmethod
    def _fila(i: int, tarjeta: bool, dias_atras: int = 0):
        from datetime import timedelta

        return SimpleNamespace(
            id=i, tipo="venta", piezas=2, comisiones=2,
            monto_total=Decimal("500.00"), monto_neto=Decimal("500.00"),
            pago_tarjeta=tarjeta, employee_code="VEND-2", employee_name="Ana",
            created_at=datetime.now() - timedelta(days=dias_atras), cliente=None,
            descuento_empleada=False, detalle=[],
        )

    def test_hoy_oculta_por_dia_y_tarjetas_son_especificas(self) -> None:
        win = self._ventana_dueno()
        win._libreta_periodo = "hoy"
        win._pintar_libreta([self._fila(1, False), self._fila(2, True)])
        self.assertTrue(win.libreta_daily_table.isHidden())
        self.assertTrue(win.libreta_daily_seccion.isHidden())
        titulos = [t.text() for _c, t, _v, _s in win._libreta_cards]
        self.assertEqual(
            titulos,
            ["EN EL CAJÓN (EFECTIVO)", "VENDIDO EN TOTAL",
             "ABONOS A APARTADOS", "COMISIONES"],
        )
        # Tarjeta 1 = solo efectivo ($500); tarjeta 2 = todo ($1,000) y
        # dice cuánto fue con tarjeta.
        self.assertEqual(win._libreta_cards[0][2].text(), "$500")
        self.assertEqual(win._libreta_cards[1][2].text(), "$1,000")
        self.assertIn("con tarjeta: $500", win._libreta_cards[1][3].text())

    def test_ciclo_muestra_por_dia_con_todos_los_dias(self) -> None:
        win = self._ventana_dueno()
        win._libreta_periodo = "ciclo"
        win._pintar_libreta([self._fila(i, False, dias_atras=i) for i in range(4)])
        self.assertFalse(win.libreta_daily_table.isHidden())
        self.assertEqual(win.libreta_daily_table.rowCount(), 4)
        # Sin scroll interno: la tabla mide lo que sus filas.
        alto_filas = sum(
            win.libreta_daily_table.rowHeight(i)
            for i in range(win.libreta_daily_table.rowCount())
        )
        self.assertGreaterEqual(win.libreta_daily_table.height(), alto_filas)

    def test_opciones_plegadas_y_rango_las_despliega(self) -> None:
        win = self._ventana_dueno()
        self.assertTrue(win.libreta_opciones_panel.isHidden())
        win.libreta_opciones_button.setChecked(True)
        self.assertFalse(win.libreta_opciones_panel.isHidden())
        win.libreta_opciones_button.setChecked(False)
        self.assertTrue(win.libreta_opciones_panel.isHidden())
        # Activar el rango deja el panel a la vista (ahí está el "Ver rango").
        win._libreta_periodo = "rango"
        win._sync_libreta_filtros()
        self.assertTrue(win.libreta_opciones_button.isChecked())
        self.assertFalse(win.libreta_opciones_panel.isHidden())
