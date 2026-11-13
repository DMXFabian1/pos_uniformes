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


if __name__ == "__main__":
    unittest.main()


class CajaFueraDelPosTests(unittest.TestCase):
    """Con la pestaña Caja oculta, sobra todo lo que la acompañaba.

    En producción quedó una sesión abierta el 1 de junio que nunca se cerró:
    eso hacía salir "Caja pendiente de corte" cada vez que abría el POS.
    """


    def test_la_caja_ya_no_vive_en_el_pos(self) -> None:
        from pos_uniformes.ui.main_window import caja_en_el_pos

        self.assertFalse(caja_en_el_pos())

    def test_el_aviso_de_caja_pendiente_ya_no_aparece(self) -> None:
        from pos_uniformes.ui.main_window import MainWindow

        ventana = MainWindow(user_id=1)
        self.addCleanup(_cerrar, ventana)
        # Si el gate corriera, abriría un diálogo modal y colgaría la prueba.
        self.assertTrue(ventana.ensure_cash_session())

    def test_no_bloquea_operaciones_por_un_corte_de_junio(self) -> None:
        from pos_uniformes.ui.main_window import MainWindow

        ventana = MainWindow(user_id=1)
        self.addCleanup(_cerrar, ventana)
        ventana.cash_session_requires_cut = True
        self.assertTrue(
            ventana._ensure_cash_session_current_day_for_operation("registrar ventas")
        )

    def test_el_encabezado_no_muestra_estado_de_caja(self) -> None:
        from pos_uniformes.ui.main_window import MainWindow

        ventana = MainWindow(user_id=1)
        self.addCleanup(_cerrar, ventana)
        self.assertFalse(ventana.cash_session_label.isVisible())
        self.assertFalse(ventana.cash_cut_button.isVisible())


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

    def test_el_pin_del_corte_administrativo_sigue_validando(self) -> None:
        """Usa el código de la promo manual; no debe irse con la Caja."""
        from unittest.mock import patch

        with patch(
            "pos_uniformes.ui.main_window.QInputDialog.getText", return_value=("0000", True)
        ), patch(
            "pos_uniformes.ui.main_window.verify_sale_manual_promo_code",
            side_effect=ValueError("Codigo invalido."),
        ) as verificar, patch("pos_uniformes.ui.main_window.QMessageBox.warning"):
            self.assertFalse(self.ventana._prompt_admin_cash_authorization())
        verificar.assert_called_once()
