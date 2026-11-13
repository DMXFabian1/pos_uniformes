"""Las pestañas cuyo trabajo se mudó al kiosko ya no se muestran.

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

# 2026-11-12: "Caja" ya no está: la Caja antigua se retiró del POS.
_ORDEN = [
    "Resumen", "Presupuestos", "Apartados", "Catálogo", "Inventario",
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
    def test_son_las_tres_que_se_mudaron(self) -> None:
        """La Caja ya no se oculta: se retiró (2026-11-12)."""
        self.assertEqual(
            set(PESTANAS_MUDADAS_AL_KIOSKO),
            {"Presupuestos", "Apartados", "Catálogo"},
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

    def test_el_historial_de_cortes_de_configuracion_sigue(self) -> None:
        """Solo lectura: muestra también los cortes hechos en el kiosko."""
        self.assertTrue(hasattr(self.ventana, "settings_cash_history_button"))


class KioskoConservaSuCorteTests(unittest.TestCase):
    """El corte se hace en el kiosko y debe seguir igual."""

    def test_el_kiosko_conserva_corte_retiro_e_historial(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        for metodo in (
            "_imprimir_corte_libreta",
            "_apuntar_retiro_libreta",
            "_abrir_historial_cortes",
        ):
            self.assertTrue(callable(getattr(QuoteSatelliteWindow, metodo, None)), metodo)

    def test_los_dialogos_y_servicios_del_corte_siguen(self) -> None:
        from pos_uniformes.services.caja_service import CajaService
        from pos_uniformes.ui.dialogs import corte_caja_dialog

        for nombre in ("hacer_corte_caja", "apuntar_retiro", "editar_parametros_caja"):
            self.assertTrue(callable(getattr(corte_caja_dialog, nombre, None)), nombre)
        for metodo in ("obtener_sesion_activa", "registrar_movimiento", "cerrar_sesion"):
            self.assertTrue(callable(getattr(CajaService, metodo, None)), metodo)
        import pos_uniformes.services.corte_caja_service  # noqa: F401
        import pos_uniformes.services.retiros_service  # noqa: F401


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


if __name__ == "__main__":
    unittest.main()
