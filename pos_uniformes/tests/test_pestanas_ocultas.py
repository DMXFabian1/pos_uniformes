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

_ORDEN = [
    "Resumen", "Caja", "Presupuestos", "Apartados", "Catalogo", "Inventario",
    "Bodega", "Historial inventarios", "Panel Uniformes", "Analitica", "Configuracion",
]


def _tabs() -> QTabWidget:
    t = QTabWidget()
    for nombre in _ORDEN:
        t.addTab(QWidget(), nombre)
    return t


class PestanasOcultasTests(unittest.TestCase):
    def test_son_las_cuatro_que_se_mudaron(self) -> None:
        self.assertEqual(
            set(PESTANAS_MUDADAS_AL_KIOSKO),
            {"Caja", "Presupuestos", "Apartados", "Catalogo"},
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
             "Panel Uniformes", "Analitica", "Configuracion"],
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

    def test_el_criterio_sale_de_la_pestana(self) -> None:
        from pos_uniformes.ui.main_window import caja_en_el_pos

        self.assertFalse(caja_en_el_pos())
        self.assertIn("Caja", PESTANAS_MUDADAS_AL_KIOSKO)

    def test_el_aviso_de_caja_pendiente_ya_no_aparece(self) -> None:
        from pos_uniformes.ui.main_window import MainWindow

        ventana = MainWindow(user_id=1)
        # Si el gate corriera, abriría un diálogo modal y colgaría la prueba.
        self.assertTrue(ventana.ensure_cash_session())

    def test_no_bloquea_operaciones_por_un_corte_de_junio(self) -> None:
        from pos_uniformes.ui.main_window import MainWindow

        ventana = MainWindow(user_id=1)
        ventana.cash_session_requires_cut = True
        self.assertTrue(
            ventana._ensure_cash_session_current_day_for_operation("registrar ventas")
        )

    def test_el_encabezado_no_muestra_estado_de_caja(self) -> None:
        from pos_uniformes.ui.main_window import MainWindow

        ventana = MainWindow(user_id=1)
        self.assertFalse(ventana.cash_session_label.isVisible())
        self.assertFalse(ventana.cash_cut_button.isVisible())
