"""La hoja de conteo en papel carta: rejilla producto × talla, numerada como la pantalla."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt6.QtPrintSupport")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from pos_uniformes.services import conteo_hoja_carta_service as hoja  # noqa: E402

# La QApplication nace al importar, como en los demás archivos de Qt: si nace
# dentro de un test, al salir del proceso Qt destruye las cosas en mal orden
# y aborta ("Fatal Python error: Aborted") aunque todo haya pasado.
_APP = QApplication.instance() or QApplication([])


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
        self.assertIn("2 prendas &nbsp;·&nbsp; 16 tallas", self.html)

    def test_la_regla_de_oro_va_impresa(self) -> None:
        self.assertIn("vacío NO es cero", self.html)

    def test_es_el_formato_de_la_tira_talla_exist_pedido(self) -> None:
        """El formato que Daniel diseñó y usa: una tabla por prenda con esas tres columnas."""
        self.assertEqual(self.html.count("<b>Talla</b>"), 2)
        self.assertEqual(self.html.count("<b>Exist.</b>"), 2)
        self.assertEqual(self.html.count("<b>Pedido</b>"), 2)

    def test_prendas_numeradas_n_de_total_y_con_nombre_limpio(self) -> None:
        """Sin la escuela ni el "| Deportivo | Pants 2pz" del catálogo (como en la tira)."""
        self.assertIn("<b>1/2</b>", self.html)
        self.assertIn("<b>Pants 2pz Deportivo</b>", self.html)
        self.assertIn("<b>2/2</b>", self.html)
        self.assertIn("<b>Suéter Cuello V H Verde Secundaria</b>", self.html)
        self.assertNotIn("| Deportivo", self.html)
        # La escuela va UNA vez, en la banda de arriba; no se repite en cada tarjeta.
        self.assertEqual(self.html.count("Práxedis Guerrero"), 1)

    def test_una_fila_por_talla_con_dos_casillas(self) -> None:
        for t in ("4", "46"):
            self.assertIn(f"<b>{t}</b>", self.html)
        # 16 tallas × 2 casillas vacías (Exist. y Pedido)
        self.assertEqual(self.html.count("&nbsp;</td><td height="), 16)

    def test_los_bordes_van_como_atributo_porque_qt_ignora_el_css(self) -> None:
        self.assertIn('border="1" cellspacing="0"', self.html)

    def test_con_quien_va_el_nombre_y_sin_quien_una_caja_para_escribir(self) -> None:
        con = hoja.construir_hoja_html(GRUPOS, titulo="X", quien="Stayce Chavarria")
        self.assertIn("<b>Stayce Chavarria</b>", con)
        self.assertIn("CUENTA</font><br><b>Stayce", con)
        # Sin nombre: una caja blanca con borde, no una raya de guiones.
        self.assertIn('CUENTA</font><br><table border="1"', self.html)
        self.assertNotIn("____", self.html)

    def test_lleva_la_paleta_del_kiosko_y_zebra_en_las_tallas(self) -> None:
        self.assertIn(f'bgcolor="{hoja.CAFE}"', self.html)     # banda café del título
        self.assertIn(f'bgcolor="{hoja.CREMA}"', self.html)    # encabezados crema
        # 16 tallas: 8 filas con fondo suave (las impares) → zebra.
        self.assertEqual(self.html.count(f'bgcolor="{hoja.CREMA_SUAVE}"><b>'), 8)

    def test_sin_grupos_no_truena(self) -> None:
        vacia = hoja.construir_hoja_html([], titulo="Nada")
        self.assertIn("0 prendas &nbsp;·&nbsp; 0 tallas", vacia)


class NombreTests(unittest.TestCase):
    def test_limpia_como_la_tira(self) -> None:
        f = hoja.nombre_para_hoja
        self.assertEqual(f("Playera Deportiva Ad Hoc Práxedis Guerrero | Deportivo", "Práxedis Guerrero"), "Playera Deportiva")
        self.assertEqual(f("Chaleco Verde Práxedis Guerrero Secundaria", "Práxedis Guerrero"), "Chaleco Verde Secundaria")
        self.assertEqual(f("", "X", tipo_pieza="Suéter"), "Suéter")


class PaginacionTests(unittest.TestCase):
    """Nunca se parte una tarjeta: las páginas se cortan entre filas."""

    def test_tres_por_fila_y_corta_cuando_no_cabe(self) -> None:
        # 6 tarjetas de 300 pt: dos filas de 310 → 620 cabe en 640; la tercera fila no.
        alturas = [300] * 9
        paginas = hoja.paginar(alturas, tope=640)
        self.assertEqual(paginas, [[0, 1, 2, 3, 4, 5], [6, 7, 8]])

    def test_la_fila_mide_lo_que_su_tarjeta_mas_alta(self) -> None:
        paginas = hoja.paginar([100, 400, 100, 100, 100, 100], tope=500)
        self.assertEqual(paginas, [[0, 1, 2], [3, 4, 5]])   # 410 + 110 > 500

    def test_las_paginas_siguientes_caben_mas(self) -> None:
        paginas = hoja.paginar([300] * 12, tope=640, tope_siguientes=1000)
        self.assertEqual(len(paginas[0]), 6)
        self.assertEqual(len(paginas[1]), 6)   # 3 filas × 310 = 930 < 1000

    def test_una_tarjeta_gigante_va_sola_sin_reventar(self) -> None:
        self.assertEqual(hoja.paginar([900], tope=640), [[0]])
        self.assertEqual(hoja.paginar([], tope=640), [])

    def test_el_html_marca_el_salto_de_pagina(self) -> None:
        muchos = [_grupo(f"Prenda {i}", [str(t) for t in range(12)]) for i in range(9)]
        html = hoja.construir_hoja_html(muchos, titulo="X")
        self.assertIn("page-break-before: always", html)

    def test_la_altura_estimada_crece_con_las_tallas(self) -> None:
        chica = hoja.altura_tarjeta_pt(_grupo("A", ["4"]), "X")
        grande = hoja.altura_tarjeta_pt(_grupo("A", [str(t) for t in range(12)]), "X")
        self.assertEqual(grande - chica, 11 * hoja._PT_FILA)


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
        from pos_uniformes.ui.helpers.conteo_hoja_carta_print_helper import elegir_impresora_por_defecto as f

        self.assertEqual(f(["Brother QL-800", "HP Smart Tank 750", "PDF"]), "HP Smart Tank 750")
        self.assertEqual(f(["hp_smart_tank_750_series"]), "hp_smart_tank_750_series")
        self.assertIsNone(f(["Brother QL-800", "Microsoft Print to PDF"]))
        self.assertIsNone(f([]))

    def test_la_hoja_se_vuelve_pdf_de_verdad(self) -> None:
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
