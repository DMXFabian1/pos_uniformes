"""La hoja de conteo en papel carta: rejilla producto × talla, numerada como la pantalla."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from types import SimpleNamespace

import pytest

from pos_uniformes.services import conteo_hoja_carta_service as hoja


def _grupo(nombre, tallas):
    return {"producto_nombre": nombre, "variantes": [SimpleNamespace(talla=t, variante_id=i) for i, t in enumerate(tallas)]}


GRUPOS = [
    _grupo("Pants 2pz Deportivo Práxedis Guerrero | Deportivo | Pants 2pz", ["4", "6", "8", "10"]),
    _grupo("Suéter Cuello V H Verde Práxedis Guerrero Secundaria", ["12", "14", "16", "30", "32", "34", "36", "38", "40", "42", "44", "46"]),
]


class HojaHtmlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = hoja.construir_hoja_html(GRUPOS, titulo="Práxedis Guerrero", fecha=date(2026, 9, 11))

    def test_encabezado_con_escuela_fecha_y_totales(self) -> None:
        self.assertIn("Práxedis Guerrero", self.html)
        self.assertIn("11/09/2026", self.html)
        self.assertIn("2 prendas · 16 tallas", self.html)

    def test_la_regla_de_oro_va_impresa(self) -> None:
        self.assertIn("vacío NO es cero", self.html)

    def test_prendas_numeradas_y_con_nombre_corto(self) -> None:
        """El "| Deportivo | Pants 2pz" del catálogo no va a la hoja."""
        self.assertIn("1.&nbsp; Pants 2pz Deportivo Práxedis Guerrero</p>", self.html)
        self.assertIn("2.&nbsp; Suéter Cuello V H Verde Práxedis Guerrero Secundaria</p>", self.html)
        self.assertNotIn("| Deportivo", self.html)

    def test_una_casilla_por_talla(self) -> None:
        self.assertEqual(self.html.count('<td class="c">'), 16)
        for t in ("4", "46"):
            self.assertIn(f'<td class="t">{t}</td>', self.html)

    def test_las_rejillas_largas_se_parten_para_que_quepan(self) -> None:
        """12 tallas > CASILLAS_POR_FILA (11): dos filas de casillas, no una que se salga."""
        self.assertEqual(hoja.CASILLAS_POR_FILA, 11)
        sueter = self.html.split("2.&nbsp;")[1]
        self.assertEqual(sueter.count('<table class="tallas">'), 2)

    def test_con_quien_va_el_nombre_en_vez_de_la_raya(self) -> None:
        con = hoja.construir_hoja_html(GRUPOS, titulo="X", quien="Stayce Chavarria")
        self.assertIn("Cuenta: Stayce Chavarria", con)
        self.assertNotIn("Cuenta: ____", con)
        self.assertIn("Cuenta: ____", self.html)

    def test_sin_grupos_no_truena(self) -> None:
        vacia = hoja.construir_hoja_html([], titulo="Nada")
        self.assertIn("0 prendas · 0 tallas", vacia)


class HojaYPantallaTests(unittest.TestCase):
    """Hoja y captura leen el MISMO alcance: mismo orden, mismos números."""

    def test_comparten_la_fuente(self) -> None:
        import inspect

        from pos_uniformes.services import conteo_jornada_service as jn
        from pos_uniformes.ui.dialogs import conteo_subir_dialog

        self.assertIn("alcance(", inspect.getsource(hoja.grupos_para_hoja))
        # La captura numera sus encabezados con enumerate(…, 1), igual que la hoja.
        fuente = inspect.getsource(conteo_subir_dialog.ConteoSubirDialog._cargar_piezas)
        self.assertIn("enumerate(grupos, 1)", fuente)
        self.assertTrue(callable(jn.alcance))


class ImpresionTests(unittest.TestCase):
    def test_elige_la_hp_si_la_hay(self) -> None:
        pytest.importorskip("PyQt6.QtPrintSupport")
        from pos_uniformes.ui.helpers.conteo_hoja_carta_print_helper import elegir_impresora_por_defecto as f

        self.assertEqual(f(["Brother QL-800", "HP Smart Tank 750", "PDF"]), "HP Smart Tank 750")
        self.assertEqual(f(["hp_smart_tank_750_series"]), "hp_smart_tank_750_series")
        self.assertIsNone(f(["Brother QL-800", "Microsoft Print to PDF"]))
        self.assertIsNone(f([]))

    def test_la_hoja_se_vuelve_pdf_de_verdad(self) -> None:
        pytest.importorskip("PyQt6.QtPrintSupport")
        from PyQt6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])
        from pos_uniformes.ui.helpers.conteo_hoja_carta_print_helper import guardar_pdf

        html = hoja.construir_hoja_html(GRUPOS, titulo="Práxedis Guerrero")
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "hoja.pdf")
            guardar_pdf(html, ruta)
            self.assertTrue(os.path.exists(ruta))
            with open(ruta, "rb") as f:
                cabecera = f.read(5)
            self.assertEqual(cabecera, b"%PDF-")
            self.assertGreater(os.path.getsize(ruta), 2000)


if __name__ == "__main__":
    unittest.main()
