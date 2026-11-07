"""Mapa de escuelas y tipos de escocés en una ventana del programa, no en el
navegador (Daniel, 2026-11-07: «como si fuera una ventana más»)."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.helpers import abrir_consultas as ac

RAIZ = Path(__file__).resolve().parents[1]
_app = QApplication.instance() or QApplication([])


class ElPdfAbreAdentroTests(unittest.TestCase):
    def tearDown(self) -> None:
        from pos_uniformes.ui.dialogs import visor_consulta_dialog as vc

        for v in list(vc._ABIERTAS.values()):
            v.close()

    def test_abre_en_su_ventana_y_no_afuera(self) -> None:
        from pos_uniformes.ui.dialogs import visor_consulta_dialog as vc

        with patch.object(ac, "_abrir") as afuera:
            ac.abrir_tipos_escoces()
        afuera.assert_not_called()
        visor = vc._ABIERTAS["pdf"]
        self.assertEqual(visor.documento.pageCount(), 2)
        self.assertEqual(visor.detalle.text(), "2 hojas")

    def test_pedirlo_otra_vez_trae_la_misma(self) -> None:
        from pos_uniformes.ui.dialogs import visor_consulta_dialog as vc

        ac.abrir_tipos_escoces()
        primera = vc._ABIERTAS["pdf"]
        ac.abrir_tipos_escoces()
        self.assertIs(vc._ABIERTAS["pdf"], primera)

    def test_si_la_ventana_falla_abre_afuera(self) -> None:
        with patch("pos_uniformes.ui.dialogs.visor_consulta_dialog.mostrar_pdf", side_effect=ImportError("sin QtPdf")), \
             patch.object(ac, "_abrir") as afuera:
            ac.abrir_tipos_escoces()
        afuera.assert_called_once()


class ElMapaAbreAdentroTests(unittest.TestCase):
    def setUp(self) -> None:
        p = patch("pos_uniformes.services.mapa_escuelas_service.preparar", return_value=Path("/tmp/mapa.html"))
        p.start()
        self.addCleanup(p.stop)

    def test_con_motor_web_usa_la_ventana(self) -> None:
        with patch.object(ac, "_hay_motor_web", return_value=True), \
             patch("pos_uniformes.ui.dialogs.visor_consulta_dialog.mostrar_mapa") as ventana, \
             patch.object(ac, "_abrir_como_ventana") as edge, patch.object(ac, "_abrir") as afuera:
            ac.abrir_mapa_escuelas()
        ventana.assert_called_once()
        edge.assert_not_called()
        afuera.assert_not_called()

    def test_el_kiosko_sin_motor_web_usa_edge_en_modo_ventana(self) -> None:
        with patch.object(ac, "_hay_motor_web", return_value=False), \
             patch.object(ac, "_abrir_como_ventana", return_value=True) as edge, \
             patch.object(ac, "_abrir") as afuera:
            ac.abrir_mapa_escuelas()
        edge.assert_called_once_with(Path("/tmp/mapa.html"))
        afuera.assert_not_called()

    def test_sin_edge_el_navegador(self) -> None:
        with patch.object(ac, "_hay_motor_web", return_value=False), \
             patch.object(ac, "_abrir_como_ventana", return_value=False), \
             patch.object(ac, "_abrir") as afuera:
            ac.abrir_mapa_escuelas()
        afuera.assert_called_once()

    def test_edge_va_sin_pestanas(self) -> None:
        with patch.object(ac, "ruta_edge", return_value=Path("C:/Edge/msedge.exe")), \
             patch.object(ac.subprocess, "Popen") as popen:
            self.assertTrue(ac._abrir_como_ventana(Path("/tmp/mapa.html")))
        self.assertTrue(popen.call_args.args[0][1].startswith("--app=file:///tmp/mapa.html"))


class LosEjecutablesLaTraenTests(unittest.TestCase):
    def test_los_specs_incluyen_el_visor_y_qtpdf(self) -> None:
        for spec in ("presupuestos_satelite_windows.spec", "pos_uniformes_windows.spec"):
            texto = (RAIZ / "packaging" / "windows" / spec).read_text(encoding="utf-8")
            for modulo in ("pos_uniformes.ui.dialogs.visor_consulta_dialog", "PyQt6.QtPdfWidgets"):
                self.assertIn(f'"{modulo}"', texto, spec)


if __name__ == "__main__":
    unittest.main()
