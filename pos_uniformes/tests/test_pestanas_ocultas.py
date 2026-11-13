"""Las pestañas cuyo trabajo se mudó al kiosko ya no se muestran.

2026-11-12: Caja y Apartados ya no solo se ocultan, se retiraron del POS.

Se ocultan, no se borran: el código y los datos siguen ahí. Lo que estas
pruebas cuidan es que ocultarlas no deje al POS parado en una pestaña
invisible.
"""

from __future__ import annotations

import unittest

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget  # noqa: E402

from pos_uniformes.ui.main_window import (  # noqa: E402
    PESTANAS_MUDADAS_AL_KIOSKO,
    MainWindow,
)

_APP = QApplication.instance() or QApplication([])

# 2026-11-12: "Caja" y "Apartados" ya no están: se retiraron del POS.
_ORDEN = [
    "Resumen", "Presupuestos", "Catálogo", "Inventario",
    "Bodega", "Historial inventarios", "Panel Uniformes", "Analítica", "Configuración",
]


def _cerrar(ventana: MainWindow) -> None:
    """2026-11-12: cada MainWindow que arma una prueba se cierra y se libera.

    Ventanas sueltas acumuladas hacían tronar pytest (Segmentation fault en
    BusyFeedbackScope → processEvents) al correr este archivo junto con otros.
    """
    ventana._force_close = True
    ventana.close()
    ventana.deleteLater()
    QApplication.processEvents()


def _tabs() -> QTabWidget:
    t = QTabWidget()
    for nombre in _ORDEN:
        t.addTab(QWidget(), nombre)
    return t


class PestanasOcultasTests(unittest.TestCase):
    def test_son_las_dos_que_se_mudaron(self) -> None:
        """La Caja y Apartados ya no se ocultan: se retiraron (2026-11-12)."""
        self.assertEqual(
            set(PESTANAS_MUDADAS_AL_KIOSKO),
            {"Presupuestos", "Catálogo"},
        )

    def test_todas_existen_todavia_en_el_orden_real(self) -> None:
        """Si alguna se renombra, el ocultado dejaría de aplicar en silencio."""
        for nombre in PESTANAS_MUDADAS_AL_KIOSKO:
            self.assertIn(nombre, _ORDEN)

    def test_las_que_se_quedan_no_se_tocan(self) -> None:
        quedan = [n for n in _ORDEN if n not in PESTANAS_MUDADAS_AL_KIOSKO]
        self.assertEqual(
            quedan,
            ["Resumen", "Inventario", "Bodega", "Historial inventarios",
             "Panel Uniformes", "Analítica", "Configuración"],
        )


class CaidaSegura(unittest.TestCase):
    """A dónde va el POS cuando la pestaña actual quedó oculta."""

    def test_el_dueno_cae_en_resumen(self) -> None:
        visibles = {0: True, 1: False, 2: False, 3: False, 4: False, 5: True}
        self.assertEqual(MainWindow._primera_pestana_visible(visibles, True), 0)

    def test_sin_resumen_cae_en_la_primera_visible_de_verdad(self) -> None:
        """Antes caía fijo en la 1 (Caja) — ahora oculta: habría quedado en blanco."""
        visibles = {0: False, 1: False, 2: False, 3: False, 4: False, 5: True, 6: True}
        self.assertEqual(MainWindow._primera_pestana_visible(visibles, False), 5)

    def test_si_nada_es_visible_no_truena(self) -> None:
        self.assertEqual(MainWindow._primera_pestana_visible({0: False}, True), 0)
        self.assertEqual(MainWindow._primera_pestana_visible({}, False), 0)


class CajaFueraDelPosTests(unittest.TestCase):
    """2026-11-12, Daniel: «no lo necesito, retira también movimientos y el
    corte».

    Antes la sesión y el corte de caja seguían en el POS, apagados con
    caja_en_el_pos() = False. Ahora se retiraron: ni botón Movimientos, ni
    sesión de caja al abrir o al cambiar de usuario, ni recordatorio de
    corte de las 5. El corte vive en el kiosko (ver KioskoConservaSuCorteTests).
    """

    def setUp(self) -> None:
        self.ventana = MainWindow(user_id=1)

    def tearDown(self) -> None:
        _cerrar(self.ventana)

    def test_ya_no_existe_el_interruptor_caja_en_el_pos(self) -> None:
        import pos_uniformes.ui.main_window as mw

        self.assertFalse(hasattr(mw, "caja_en_el_pos"))

    def test_no_hay_boton_movimientos_ni_corte(self) -> None:
        from PyQt6.QtWidgets import QAbstractButton

        textos = {b.text() for b in self.ventana.findChildren(QAbstractButton)}
        for texto in ("Movimientos", "Corte de caja", "Corte", "Abrir caja"):
            self.assertNotIn(texto, textos, texto)
        for atributo in (
            "cash_movement_button",
            "cash_movement_menu",
            "cash_cut_button",
            "cash_session_label",
            "cash_admin_cut_action",
            "cash_reactivo_action",
            "cash_ingreso_action",
            "cash_retiro_action",
            "cash_opening_correction_action",
            "_handle_cash_movement",
            "_handle_admin_cash_cut",
            "_handle_correct_cash_opening",
            "_handle_cash_cut",
            "_prompt_admin_cash_authorization",
        ):
            self.assertFalse(hasattr(self.ventana, atributo), atributo)

    def test_no_arranca_ni_revisa_sesion_de_caja(self) -> None:
        for atributo in (
            "ensure_cash_session",
            "refresh_after_cash_session",
            "_refresh_cash_session",
            "_is_stale_cash_session",
            "_ensure_cash_session_current_day_for_operation",
            "active_cash_session_id",
            "cash_session_requires_cut",
        ):
            self.assertFalse(hasattr(self.ventana, atributo), atributo)

    def test_el_arranque_no_pide_abrir_caja(self) -> None:
        import inspect

        import pos_uniformes.main as main_module

        fuente = inspect.getsource(main_module.main)
        self.assertNotIn("ensure_cash_session", fuente)
        self.assertNotIn("refresh_after_cash_session", fuente)

    def test_no_hay_recordatorio_de_corte(self) -> None:
        self.assertFalse(hasattr(self.ventana, "_run_operational_checks"))
        self.assertFalse(hasattr(self.ventana, "operational_check_timer"))
        self.assertFalse(hasattr(self.ventana, "cash_session_cut_reminder_key"))

    def test_los_modulos_que_solo_servian_al_corte_del_pos_ya_no_estan(self) -> None:
        import importlib

        for modulo in (
            "pos_uniformes.services.cash_session_action_service",
            "pos_uniformes.services.sale_discount_context_service",
            "pos_uniformes.ui.dialogs.cash_session_prompt_dialogs",
            "pos_uniformes.ui.helpers.cash_session_feedback_helper",
        ):
            with self.assertRaises(ModuleNotFoundError, msg=modulo):
                importlib.import_module(modulo)


class HistorialCajaAntiguaRetiradoTests(unittest.TestCase):
    """2026-11-12, Daniel: «Sí, retíralo».

    Configuración tenía un «Historial de cortes» que leía las sesiones de la
    Caja antigua (tabla sesion_caja). Desde que el POS ya no abre sesiones
    esa tabla quedó congelada, así que el historial se retiró. Los datos y
    las tablas siguen; los cortes reales se consultan en el kiosko (ver
    KioskoConservaSuCorteTests).
    """

    def setUp(self) -> None:
        self.ventana = MainWindow(user_id=1)

    def tearDown(self) -> None:
        _cerrar(self.ventana)

    def test_configuracion_ya_no_tiene_historial_de_caja(self) -> None:
        for atributo in (
            "settings_cash_history_button",
            "settings_cash_history_dialog",
            "settings_cash_history_table",
            "settings_cash_history_movements_table",
            "settings_cash_history_state_combo",
            "settings_cash_history_from_input",
            "settings_cash_history_to_input",
            "settings_cash_history_refresh_button",
            "settings_cash_history_detail_button",
            "settings_cash_history_rows",
            "_open_cash_history_settings_dialog",
            "_refresh_settings_cash_history",
            "_refresh_selected_cash_history_movements",
            "_selected_cash_history_id",
            "_handle_view_cash_history_detail",
            "_extract_opening_corrections",
        ):
            self.assertFalse(hasattr(self.ventana, atributo), atributo)

    def test_no_queda_boton_historial_de_cortes_en_el_pos(self) -> None:
        from PyQt6.QtWidgets import QAbstractButton

        textos = {b.text() for b in self.ventana.findChildren(QAbstractButton)}
        self.assertNotIn("Historial de cortes", textos)

    def test_el_dialogo_de_configuracion_ya_no_existe(self) -> None:
        from pos_uniformes.ui.dialogs import settings_dialogs

        self.assertFalse(hasattr(settings_dialogs, "build_cash_history_settings_dialog"))

    def test_los_modulos_que_solo_servian_al_historial_ya_no_estan(self) -> None:
        import importlib

        for modulo in (
            "pos_uniformes.services.caja_service",
            "pos_uniformes.services.cash_session_history_service",
            "pos_uniformes.ui.helpers.settings_cash_history_helper",
            "pos_uniformes.ui.helpers.settings_cash_history_detail_helper",
            "pos_uniformes.ui.helpers.settings_cash_history_movements_helper",
            "pos_uniformes.ui.helpers.settings_cash_history_summary_helper",
        ):
            with self.assertRaises(ModuleNotFoundError, msg=modulo):
                importlib.import_module(modulo)

    def test_la_exportacion_de_analitica_ya_no_lee_sesion_caja(self) -> None:
        import inspect

        fuente = inspect.getsource(MainWindow._handle_export_analytics)
        self.assertNotIn("11_cortes_caja", fuente)
        self.assertNotIn("SesionCaja", fuente)
        # Las demás hojas conservan su nombre y número.
        for hoja in ("00_resumen_general", "09_compras", "10_detalle_compras"):
            self.assertIn(hoja, fuente)

    def test_los_datos_de_la_caja_antigua_no_se_borran(self) -> None:
        from pos_uniformes.database.models import MovimientoCaja, SesionCaja

        self.assertEqual(SesionCaja.__tablename__, "sesion_caja")
        self.assertEqual(MovimientoCaja.__tablename__, "movimiento_caja")


class KioskoConservaSuCorteTests(unittest.TestCase):
    """El corte se hace en el kiosko y debe seguir igual.

    Aquí solo se revisa que el kiosko conserve sus puntos de entrada; la
    lógica del corte la ejercitan tests/test_corte_*.py,
    test_historial_cortes*.py y test_telegram_cortes.py.
    """

    def test_el_kiosko_conserva_corte_retiro_e_historial(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        for metodo in (
            "_imprimir_corte_libreta",
            "_apuntar_retiro_libreta",
            "_abrir_historial_cortes",
        ):
            self.assertTrue(callable(getattr(QuoteSatelliteWindow, metodo, None)), metodo)

    def test_los_dialogos_y_servicios_del_corte_siguen(self) -> None:
        from pos_uniformes.ui.dialogs import corte_caja_dialog

        for nombre in ("hacer_corte_caja", "apuntar_retiro", "editar_parametros_caja"):
            self.assertTrue(callable(getattr(corte_caja_dialog, nombre, None)), nombre)
        # 2026-11-12: CajaService (Caja antigua del POS) se retiró; el corte
        # del kiosko nunca dependió de él.
        import pos_uniformes.services.corte_caja_service  # noqa: F401
        import pos_uniformes.services.retiros_service  # noqa: F401

    def test_el_dialogo_de_corte_nombra_el_servicio_que_usa(self) -> None:
        """El docstring no debe mandar a buscar el CajaService retirado."""
        import re

        from pos_uniformes.ui.dialogs import corte_caja_dialog

        doc = corte_caja_dialog.__doc__ or ""
        self.assertIn("corte_caja_service.cerrar_corte", doc)
        self.assertIsNone(re.search(r"(?<!corte_)caja_service", doc))

    def test_el_historial_de_cortes_del_kiosko_sigue(self) -> None:
        """El historial de cortes que importa vive en el kiosko (LibretaCorte)."""
        from pathlib import Path

        from pos_uniformes.services import historial_cortes_service
        from pos_uniformes.ui.dialogs.historial_cortes_dialog import HistorialCortesDialog
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        self.assertTrue(callable(getattr(QuoteSatelliteWindow, "_abrir_historial_cortes", None)))
        self.assertTrue(callable(HistorialCortesDialog))
        for nombre in ("listar_cortes_mes", "totales_cortes", "periodo_del_corte", "borrar_corte"):
            self.assertTrue(callable(getattr(historial_cortes_service, nombre, None)), nombre)
        pruebas = sorted(p.name for p in Path(__file__).parent.glob("test_historial_cortes*.py"))
        self.assertIn("test_historial_cortes.py", pruebas)
        self.assertIn("test_historial_cortes_totales.py", pruebas)


class CajaAntiguaRetiradaTests(unittest.TestCase):
    """2026-11-12, Daniel: «la caja antigua ya no es de utilidad, todo lo demás
    corre en libreta y kioskos y es lo único que importa, es donde vive
    nuestra operación».

    La pestaña Caja ya no se construye y ningún atajo puede cobrar ni abrir
    lo que quedaba de ella.
    """

    def setUp(self) -> None:
        from pos_uniformes.ui.main_window import MainWindow

        self.ventana = MainWindow(user_id=1)

    def tearDown(self) -> None:
        _cerrar(self.ventana)

    def test_la_pestana_caja_no_se_construye(self) -> None:
        nombres = [
            self.ventana.tabs.tabText(i).strip() for i in range(self.ventana.tabs.count())
        ]
        self.assertNotIn("Caja", nombres)
        self.assertEqual(nombres, _ORDEN)

    def test_no_queda_carrito_ni_cobro_de_la_caja(self) -> None:
        for atributo in (
            "sale_cart",
            "sale_sku_input",
            "sale_button",
            "recent_sales_table",
            "_handle_sale",
            "_handle_cancel_sale",
            "_open_recent_sales_dialog",
            "_open_quick_product_search",
            "_handle_convert_sale_cart_to_layaway",
            "_handle_convert_quote_to_sale",
        ):
            self.assertFalse(hasattr(self.ventana, atributo), atributo)

    def test_f2_y_los_atajos_de_la_caja_ya_no_existen(self) -> None:
        from PyQt6.QtGui import QKeySequence, QShortcut

        atajos = {
            sc.key().toString(QKeySequence.SequenceFormat.PortableText)
            for sc in self.ventana.findChildren(QShortcut)
        }
        for tecla in ("F2", "F6", "F8", "Del"):
            self.assertNotIn(tecla, atajos, tecla)
        # Ctrl+S / Cmd+S se quedan, pero solo para consultar (sin carrito).
        self.assertIn("Ctrl+S", atajos)
        self.assertIn("Meta+S", atajos)
        # Escape sigue: limpia Presupuestos y Catálogo.
        self.assertIn("Esc", atajos)

    def test_ctrl_s_abre_la_busqueda_solo_para_consultar(self) -> None:
        from unittest.mock import patch

        from PyQt6.QtGui import QKeySequence

        atajo = next(
            sc for sc in self.ventana._atajos_busqueda
            if sc.key().toString(QKeySequence.SequenceFormat.PortableText) == "Ctrl+S"
        )
        with patch(
            "pos_uniformes.ui.dialogs.quick_product_search_dialog.QuickProductSearchDialog"
        ) as dialogo:
            atajo.activated.emit()
        dialogo.assert_called_once_with(self.ventana, solo_consulta=True)

    def test_escape_ya_no_toca_la_caja(self) -> None:
        # Sin pestaña Caja, Escape en cualquier pestaña no debe tronar.
        for i in range(self.ventana.tabs.count()):
            self.ventana.tabs.setCurrentIndex(i)
            self.ventana._handle_escape()

    def test_cobrar_presupuesto_ya_no_existe(self) -> None:
        self.assertFalse(hasattr(self.ventana, "quote_convert_button"))


class ApartadosRetiradosDelPosTests(unittest.TestCase):
    """2026-11-12, Daniel: «retira también apartados».

    La pestaña Apartados del POS principal ya estaba oculta y con sus botones
    apagados; ahora ya no se construye. Los apartados se hacen en Venta Rápida
    del kiosko y quedan en la Libreta (ver KioskoConservaSusApartadosTests).
    """

    def setUp(self) -> None:
        self.ventana = MainWindow(user_id=1)

    def tearDown(self) -> None:
        _cerrar(self.ventana)

    def _nombres(self) -> list[str]:
        return [
            self.ventana.tabs.tabText(i).strip() for i in range(self.ventana.tabs.count())
        ]

    def test_la_pestana_apartados_no_se_construye(self) -> None:
        self.assertNotIn("Apartados", self._nombres())

    def test_el_orden_real_de_pestanas_es_el_esperado(self) -> None:
        self.assertEqual(
            self._nombres(),
            [
                "Resumen", "Presupuestos", "Catálogo", "Inventario", "Bodega",
                "Historial inventarios", "Panel Uniformes", "Analítica", "Configuración",
            ],
        )

    def test_las_mudadas_siguen_existiendo_y_ocultas(self) -> None:
        from pos_uniformes.database.models import RolUsuario

        self.ventana.current_role = RolUsuario.ADMIN
        self.ventana._apply_role_navigation()
        nombres = self._nombres()
        for nombre in PESTANAS_MUDADAS_AL_KIOSKO:
            self.assertIn(nombre, nombres)
            self.assertFalse(self.ventana.tabs.isTabVisible(nombres.index(nombre)), nombre)
        for nombre in ("Resumen", "Inventario", "Panel Uniformes", "Configuración"):
            self.assertTrue(self.ventana.tabs.isTabVisible(nombres.index(nombre)), nombre)

    def test_el_boton_panel_uniformes_cae_en_su_pestana(self) -> None:
        self.ventana._handle_open_uniforms_panel()
        self.assertEqual(
            self.ventana.tabs.tabText(self.ventana.tabs.currentIndex()), "Panel Uniformes"
        )

    def test_no_quedan_widgets_ni_metodos_de_la_pestana(self) -> None:
        for atributo in (
            "layaway_rows",
            "layaway_table",
            "layaway_detail_table",
            "layaway_payments_table",
            "layaway_search_input",
            "layaway_state_combo",
            "layaway_due_combo",
            "layaway_create_button",
            "layaway_payment_button",
            "layaway_void_payment_button",
            "layaway_edit_button",
            "layaway_deliver_button",
            "layaway_cancel_button",
            "layaway_receipt_button",
            "layaway_sale_ticket_button",
            "layaway_whatsapp_button",
            "layaway_status_label",
            "layaway_quick_alerts_label",
            "_build_layaway_tab",
            "_refresh_layaways",
            "_refresh_layaway_detail",
            "_selected_layaway_id",
            "_select_layaway",
            "_handle_create_layaway",
            "_handle_register_layaway_payment",
            "_handle_void_layaway_payment",
            "_handle_edit_layaway",
            "_handle_deliver_layaway",
            "_handle_cancel_layaway",
            "_handle_view_layaway_receipt",
            "_handle_view_layaway_sale_ticket",
            "_handle_open_layaway_whatsapp",
            "_handle_layaway_filters_changed",
            "_registrar_abono_en_libreta",
        ):
            self.assertFalse(hasattr(self.ventana, atributo), atributo)

    def test_no_hay_botones_de_apartado(self) -> None:
        from PyQt6.QtWidgets import QAbstractButton

        textos = {b.text() for b in self.ventana.findChildren(QAbstractButton)}
        for texto in ("Nuevo apartado", "Registrar abono", "Editar apartado", "Anular abono"):
            self.assertNotIn(texto, textos, texto)

    def test_lo_que_no_era_de_la_pestana_se_queda(self) -> None:
        """Alertas del Resumen, Analítica, filtro del Catálogo y plantillas
        de WhatsApp leen apartados, pero no eran parte de la pestaña."""
        for atributo in (
            "layaway_alerts_label",
            "analytics_layaway_active_label",
            "catalog_layaway_filter_combo",
            "settings_whatsapp_layaway_reminder_input",
            "settings_whatsapp_layaway_liquidated_input",
        ):
            self.assertTrue(hasattr(self.ventana, atributo), atributo)

    def test_los_modulos_que_solo_servian_a_la_pestana_ya_no_estan(self) -> None:
        import importlib

        for modulo in (
            "pos_uniformes.ui.views.layaway_view",
            "pos_uniformes.ui.dialogs.create_layaway_dialog",
            "pos_uniformes.ui.dialogs.layaway_payment_dialog",
            "pos_uniformes.ui.helpers.layaway_action_helper",
            "pos_uniformes.ui.helpers.layaway_delivery_feedback_helper",
            "pos_uniformes.ui.helpers.layaway_detail_helper",
            "pos_uniformes.ui.helpers.layaway_history_helper",
            "pos_uniformes.ui.helpers.layaway_summary_helper",
            "pos_uniformes.ui.helpers.layaway_table_row_helper",
            "pos_uniformes.ui.helpers.printable_document_flow_helper",
            "pos_uniformes.services.layaway_snapshot_service",
        ):
            with self.assertRaises(ModuleNotFoundError, msg=modulo):
                importlib.import_module(modulo)


class KioskoConservaSusApartadosTests(unittest.TestCase):
    """Los apartados viven en Venta Rápida del kiosko y deben seguir igual.

    Aquí solo se revisan los puntos de entrada; el flujo real lo ejercitan
    test_quick_sale_print_tickets.py (ticket de apartado, anticipo y abono),
    test_libreta*.py y test_api_movil.py.
    """

    def test_el_kiosko_monta_venta_rapida(self) -> None:
        import inspect

        import pos_uniformes.ui.quote_satellite_window as satelite
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        self.assertIs(satelite.QuickSaleWidget, QuickSaleWidget)
        self.assertIn("QuickSaleWidget(self)", inspect.getsource(satelite.QuoteSatelliteWindow))

    def test_venta_rapida_conserva_apartado_y_abono(self) -> None:
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        for metodo in (
            "_on_ticket_apartado",
            "_on_abono",
            "_registrar_en_libreta",
            "_build_apartado_text",
        ):
            self.assertTrue(callable(getattr(QuickSaleWidget, metodo, None)), metodo)

    def test_los_servicios_de_dominio_de_apartados_siguen(self) -> None:
        from pos_uniformes.database.models import Apartado
        from pos_uniformes.services.apartado_service import ApartadoService
        import pos_uniformes.services.layaway_alerts_service  # noqa: F401
        import pos_uniformes.services.layaway_closure_service  # noqa: F401
        import pos_uniformes.services.layaway_creation_service  # noqa: F401
        import pos_uniformes.services.layaway_payment_service  # noqa: F401
        import pos_uniformes.services.layaway_pricing_service  # noqa: F401

        self.assertEqual(Apartado.__tablename__, "apartado")
        self.assertTrue(callable(getattr(ApartadoService, "obtener_apartado", None)))


class SinCargarDatosInicialesTests(unittest.TestCase):
    """2026-11-12, Daniel: «la caja antigua ya no es de utilidad, todo lo
    demás corre en libreta y kioskos» → «Pantallas con datos viejos».

    «Cargar datos iniciales» del menú «Más» metía en la base real (el POS se
    conecta solo a producción) un proveedor demo, marcas y productos de
    prueba sin preguntar. Se retiró la acción, el botón y su handler, y
    `bootstrap_service`, que solo usaba esto.
    """

    def setUp(self) -> None:
        self.ventana = MainWindow(user_id=1)

    def tearDown(self) -> None:
        _cerrar(self.ventana)

    def test_el_menu_mas_ya_no_carga_datos_iniciales(self) -> None:
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QAbstractButton

        acciones = {a.text() for a in self.ventana.findChildren(QAction)}
        if self.ventana.header_more_button is not None and self.ventana.header_more_button.menu() is not None:
            acciones |= {a.text() for a in self.ventana.header_more_button.menu().actions()}
        self.assertNotIn("Cargar datos iniciales", acciones)
        botones = {b.text() for b in self.ventana.findChildren(QAbstractButton)}
        self.assertNotIn("Cargar datos iniciales", botones)
        for atributo in ("seed_action", "seed_button", "_handle_seed_data"):
            self.assertFalse(hasattr(self.ventana, atributo), atributo)

    def test_bootstrap_service_ya_no_existe(self) -> None:
        import importlib

        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("pos_uniformes.services.bootstrap_service")



class ResumenDesdeLaLibretaTests(unittest.TestCase):
    """2026-11-12, «Pantallas con datos viejos»: la pestaña Resumen ya no lee
    la tabla `venta` de la Caja antigua. Ventas y cobrado de hoy y del mes
    salen de la Libreta (`resumen_pos_service`, probado en
    test_resumen_pos_service.py) y el bloque «Promos manuales» (leía una
    tabla en la que nadie escribe) se quitó."""

    def setUp(self) -> None:
        self.ventana = MainWindow(user_id=1)

    def tearDown(self) -> None:
        _cerrar(self.ventana)

    def test_ya_no_hay_bloque_de_promos_manuales(self) -> None:
        from PyQt6.QtWidgets import QGroupBox

        titulos = {g.title() for g in self.ventana.findChildren(QGroupBox)}
        self.assertNotIn("Promos manuales", titulos)
        for atributo in ("dashboard_manual_promo_box", "dashboard_manual_promo_label"):
            self.assertFalse(hasattr(self.ventana, atributo), atributo)

    def test_el_resumen_lee_la_libreta_y_no_la_caja_antigua(self) -> None:
        import inspect

        fuente = inspect.getsource(MainWindow._refresh_summary)
        self.assertIn("resumen_pos_service.cargar", fuente)
        self.assertNotIn("Venta.", fuente)
        self.assertNotIn("ManualPromoService", fuente)

    def test_el_resumen_se_pinta_sin_tronar(self) -> None:
        from pos_uniformes.database.connection import get_session

        with get_session() as session:
            self.ventana._refresh_summary(session)
        self.assertTrue(self.ventana.kpi_sales_value.text().isdigit())
        self.assertIn("Ventas hoy:", self.ventana.metrics_label.text())
        self.assertIn("ventas en el mes", self.ventana.dashboard_sales_context_label.text())


if __name__ == "__main__":
    unittest.main()
