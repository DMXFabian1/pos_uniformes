"""El mapa de escuelas en el kiosko (2026-11-07): botón en Conteos que abre el
mapa con el estado de los conteos de ese momento."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pos_uniformes.services import mapa_escuelas_service as svc

RAIZ = Path(__file__).resolve().parents[1]


class _Ultimo:
    def texto(self):
        return "hoy (Fanny)"


class _Est:
    nombre = "Benito Juárez"
    titular = "al día"
    en_rojo, faltan_de_contar, tallas, pct_al_dia, agotadas = 0, 0, 10, 100, 0
    piezas_en_tienda, vendido_piezas, pedido, faltas_sentidas = 50, 2, [], []
    ultimo_conteo = _Ultimo()
    salud = "verde"


class PrepararTests(unittest.TestCase):
    def test_encuentra_el_mapa_del_repo(self) -> None:
        ruta = svc.ubicar_mapa()
        self.assertIsNotNone(ruta)
        self.assertEqual(ruta.name, "mapa_escuelas_san_felipe.html")

    def test_copia_el_mapa_con_el_estado_de_ahora(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            html = svc.preparar(Path(d), estados={1: _Est()})
            self.assertTrue(html.is_file())
            js = (Path(d) / "estados_pos.js").read_text(encoding="utf-8")
            self.assertIn("Benito Juárez", js)

    def test_sin_base_abre_igual_y_no_deja_un_estado_viejo(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "estados_pos.js").write_text("viejo", encoding="utf-8")

            def falla():
                raise OSError("No route to host")

            html = svc.preparar(Path(d), calcular=falla)
            self.assertTrue(html.is_file())
            self.assertFalse((Path(d) / "estados_pos.js").exists())

    def test_sin_mapa_no_hay_nada_que_abrir(self) -> None:
        with mock.patch.object(svc, "ubicar_mapa", return_value=None):
            self.assertIsNone(svc.preparar(Path(tempfile.gettempdir()) / "no_usar"))


class KioskoTests(unittest.TestCase):
    def test_el_satelite_trae_el_mapa_y_el_boton(self) -> None:
        spec = (RAIZ / "packaging" / "windows" / "presupuestos_satelite_windows.spec").read_text(encoding="utf-8")
        self.assertIn('"mapas_escuelas" / "mapa_escuelas_san_felipe.html"', spec)
        self.assertIn("pos_uniformes.services.mapa_escuelas_service", spec)
        ventana = (RAIZ / "ui" / "quote_satellite_window.py").read_text(encoding="utf-8")
        self.assertIn('QPushButton("🏫 Mapa de escuelas")', ventana)
        self.assertIn("abrir_mapa_escuelas(self)", ventana)
        self.assertIn("pos_uniformes.ui.helpers.abrir_consultas", spec)


class AtajosTests(unittest.TestCase):
    """Ctrl+Shift+M mapa · Ctrl+Shift+E escocés, en el kiosko y en el POS."""

    def test_los_dos_atajos_en_las_dos_ventanas(self) -> None:
        for archivo in ("quote_satellite_window.py", "main_window.py"):
            fuente = (RAIZ / "ui" / archivo).read_text(encoding="utf-8")
            self.assertIn("instalar_atajos(self)", fuente, archivo)

    def test_no_chocan_con_otros_atajos(self) -> None:
        import re

        for archivo in ("quote_satellite_window.py", "main_window.py"):
            fuente = (RAIZ / "ui" / archivo).read_text(encoding="utf-8")
            usados = re.findall(r'QKeySequence\("([^"]+)"\)', fuente)
            self.assertNotIn("Ctrl+Shift+M", usados, archivo)
            self.assertNotIn("Ctrl+Shift+E", usados, archivo)

    def test_el_catalogo_de_escoceses_viene_en_assets(self) -> None:
        from pos_uniformes.ui.helpers.abrir_consultas import ruta_tipos_escoces

        ruta = ruta_tipos_escoces()
        self.assertTrue(ruta.is_file())
        self.assertEqual(ruta.read_bytes()[:5], b"%PDF-")

    def test_los_atajos_abren_lo_suyo(self) -> None:
        import pytest

        pytest.importorskip("PyQt6.QtWidgets")
        from PyQt6.QtWidgets import QApplication, QWidget

        from pos_uniformes.ui.helpers import abrir_consultas as ac

        _app = QApplication.instance() or QApplication([])
        ventana = QWidget()
        atajos = ac.instalar_atajos(ventana)
        self.assertEqual([a.key().toString() for a in atajos], ["Ctrl+Shift+M", "Ctrl+Shift+E"])
        # Abren en una ventana del programa (2026-11-07), no en el navegador.
        with mock.patch("pos_uniformes.ui.dialogs.visor_consulta_dialog.mostrar_pdf") as pdf:
            atajos[1].activated.emit()
            pdf.assert_called_once_with(ac.ruta_tipos_escoces(), "🧵 Tipos de escocés", ventana)
        with mock.patch.object(ac, "_hay_motor_web", return_value=True), \
                mock.patch("pos_uniformes.ui.dialogs.visor_consulta_dialog.mostrar_mapa") as mapa, \
                mock.patch("pos_uniformes.services.mapa_escuelas_service.preparar", return_value=Path("/x/mapa.html")):
            atajos[0].activated.emit()
            mapa.assert_called_once_with(Path("/x/mapa.html"), ventana)

if __name__ == "__main__":
    unittest.main()
