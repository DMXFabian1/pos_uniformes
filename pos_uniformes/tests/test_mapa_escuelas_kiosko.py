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
        self.assertIn("mapa_escuelas_service.preparar()", ventana)


if __name__ == "__main__":
    unittest.main()
