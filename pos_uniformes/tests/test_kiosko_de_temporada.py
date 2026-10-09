"""El hueco del producto se adorna en temporada.

Daniel (2026-10-09): «mejoremos esta vista para que vaya adhoc con el tema de
halloween». Esa pantalla se usa todo el día, así que el adorno va donde NO
estorba: el hueco que enseña una «M» genérica mientras nadie escanea nada. Al
escanear vuelve el producto — el adorno se quita solo cuando hay trabajo.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

from pos_uniformes.services import temporada_service as temp


class ElHuecoDelProductoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _icono(self, size=124):
        from pos_uniformes.ui.quote_satellite_window import _icono_de_temporada

        return _icono_de_temporada(size)

    def _como_imagen(self, px):
        return px.toImage().convertToFormat(QImage.Format.Format_ARGB32)

    def test_fuera_de_temporada_no_hay_adorno(self) -> None:
        """Casi todo el año se queda la «M» de siempre."""
        temp.guardar_ajuste(temp.APAGADA)
        self.assertTrue(self._icono().isNull())

    def test_en_temporada_sale_el_dibujo(self) -> None:
        temp.guardar_ajuste(temp.FIJA, "halloween")
        px = self._icono()
        self.assertFalse(px.isNull())
        self.assertLessEqual(max(px.width(), px.height()), 124)

    def test_el_papel_queda_transparente(self) -> None:
        """El PNG es tinta negra sobre papel BLANCO, sin transparencia.

        Teñirlo tal cual daba un rectángulo de color macizo — pasó al
        escribir esto, y así se veía en la tarjeta.
        """
        temp.guardar_ajuste(temp.FIJA, "halloween")
        img = self._como_imagen(self._icono())
        for x, y in ((0, 0), (img.width() - 1, 0), (0, img.height() - 1)):
            with self.subTest(esquina=(x, y)):
                self.assertEqual(img.pixelColor(x, y).alpha(), 0)

    def test_la_tinta_toma_el_color_de_la_temporada(self) -> None:
        from PyQt6.QtGui import QColor

        for archivo in ("halloween", "navidad"):
            with self.subTest(temporada=archivo):
                temp.guardar_ajuste(temp.FIJA, archivo)
                esperado = QColor(temp.temporada_de_archivo(archivo).color)
                img = self._como_imagen(self._icono())
                opacos = [
                    img.pixelColor(x, y)
                    for y in range(0, img.height(), 3)
                    for x in range(0, img.width(), 3)
                    if img.pixelColor(x, y).alpha() > 200
                ]
                self.assertTrue(opacos, "no quedó nada de tinta")
                c = opacos[len(opacos) // 2]
                # Con margen: al escalar suavizado, el borde de un trazo se
                # mezcla con el fondo y un canal puede moverse un punto. Lo
                # que se prueba es que sea ESE color, no otro.
                for canal, (a, b) in enumerate(
                    zip((c.red(), c.green(), c.blue()),
                        (esperado.red(), esperado.green(), esperado.blue()))
                ):
                    self.assertLessEqual(abs(a - b), 4, f"canal {canal}: {a} vs {b}")

    def test_no_sale_un_rectangulo_macizo(self) -> None:
        """Lo que se vio en pantalla cuando el teñido estaba mal.

        El que de verdad caza el error es el de las esquinas transparentes;
        éste cuida el caso de un dibujo que llene las esquinas."""
        temp.guardar_ajuste(temp.FIJA, "halloween")
        img = self._como_imagen(self._icono())
        total = sum(1 for y in range(img.height()) for x in range(img.width()))
        pintados = sum(
            1 for y in range(img.height()) for x in range(img.width())
            if img.pixelColor(x, y).alpha() > 128
        )
        # Un rectángulo macizo es TODO opaco. El margen deja pasar una
        # silueta rellena —la calabaza de Daniel ocupa el 59% de su caja—
        # sin dejar pasar el error, que da 100%.
        self.assertLess(pintados / total, 0.9)

    def test_una_temporada_sin_dibujo_no_truena(self) -> None:
        from unittest.mock import patch

        temp.guardar_ajuste(temp.FIJA, "halloween")
        with patch.object(temp, "imagen_para_marcador", return_value=None):
            self.assertTrue(self._icono().isNull())


class LaPantallaLoUsaTests(unittest.TestCase):
    def test_el_hueco_prefiere_el_producto_sobre_el_adorno(self) -> None:
        """Con un producto escaneado manda el producto: el adorno es relleno."""
        from pathlib import Path

        codigo = Path(__file__).resolve().parents[1].joinpath(
            "ui/quote_satellite_window.py"
        ).read_text(encoding="utf-8")
        trozo = codigo[codigo.index("def _apply_lookup_view"):][:900]
        self.assertIn("_catalog_row_icon(lookup_row)", trozo)
        self.assertIn("_icono_de_temporada", trozo)
        # Y si no hay temporada, la «M» de siempre.
        self.assertIn('_scaled_asset_pixmap("qr_icons/default.png"', trozo)


if __name__ == "__main__":
    unittest.main()


class ElDibujoVaCentradoEnSuCajaTests(unittest.TestCase):
    """«esa M se ve fuera de lugar, siento que no está centrada» (09/10).

    No era la «M»: dentro de su archivo está centrada (3 puntos de margen a
    cada lado). Era la etiqueta, que sin `setAlignment` pega el dibujo a la
    IZQUIERDA — 112 en una caja de 148 deja 36 puntos de aire a la derecha.
    """

    def test_la_etiqueta_centra_lo_que_le_pongan(self) -> None:
        from pathlib import Path

        codigo = Path(__file__).resolve().parents[1].joinpath(
            "ui/quote_satellite_window.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "self.kiosk_visual_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)",
            codigo,
        )

    def test_el_adorno_y_la_M_miden_lo_mismo(self) -> None:
        """Con tamaños distintos, la tarjeta da un brinco al escanear."""
        from pos_uniformes.ui import quote_satellite_window as q

        temp.guardar_ajuste(temp.APAGADA)
        m = q._scaled_asset_pixmap("qr_icons/default.png", q._DIBUJO_VISUAL)
        temp.guardar_ajuste(temp.FIJA, "halloween")
        adorno = q._icono_de_temporada(q._DIBUJO_VISUAL)
        self.assertEqual(max(m.width(), m.height()), q._DIBUJO_VISUAL)
        self.assertEqual(max(adorno.width(), adorno.height()), q._DIBUJO_VISUAL)

    def test_el_dibujo_cabe_en_su_caja(self) -> None:
        from pos_uniformes.ui import quote_satellite_window as q

        self.assertLess(q._DIBUJO_VISUAL, q._HUECO_VISUAL)


class ElDibujoDeDanielListoParaElPapelTests(unittest.TestCase):
    """Daniel manda los dibujos grandes y con transparencia; la térmica quiere
    blanco y negro puro y del tamaño exacto con que va a imprimir.

    Se prepara UNA vez (`scripts/preparar_dibujo_temporada.py`) y no al
    imprimir: encoger un dibujo de un bit en el último momento es lo que
    apolilló el logo el 07/10.
    """

    def _carpeta(self):
        from pathlib import Path

        return Path(__file__).resolve().parents[1] / "assets" / "temporadas"

    def test_el_original_se_queda_guardado(self) -> None:
        """Sin él no se puede volver a preparar si cambia el tamaño."""
        self.assertTrue((self._carpeta() / "originales" / "halloween.png").exists())

    def test_el_que_se_imprime_sale_del_original(self) -> None:
        from PIL import Image

        from pos_uniformes.scripts.preparar_dibujo_temporada import preparar

        carpeta = self._carpeta()
        esperado = preparar(carpeta / "originales" / "halloween.png")
        actual = Image.open(carpeta / "halloween.png")
        self.assertEqual(actual.size, esperado.size)
        self.assertEqual(actual.convert("L").tobytes(),
                         esperado.convert("L").tobytes())

    def test_queda_en_dos_tonos(self) -> None:
        """La térmica no tiene medios tonos: un gris sale como suciedad."""
        from PIL import Image

        im = Image.open(self._carpeta() / "halloween.png")
        self.assertEqual(im.mode, "1")

    def test_cabe_en_el_papel_sin_que_nadie_lo_encoja(self) -> None:
        from PIL import Image

        from pos_uniformes.scripts.preparar_dibujo_temporada import ANCHO_MAXIMO

        for p in self._carpeta().glob("*.png"):
            with self.subTest(dibujo=p.name):
                self.assertLessEqual(Image.open(p).width, ANCHO_MAXIMO)

    def test_no_se_come_media_cuenta(self) -> None:
        """Un dibujo alto es papel que se paga en cada venta."""
        from PIL import Image

        for p in self._carpeta().glob("*.png"):
            with self.subTest(dibujo=p.name):
                self.assertLessEqual(Image.open(p).height, 260)

    def test_la_transparencia_se_aplana_sobre_blanco(self) -> None:
        """Los manda negros sobre transparente: sin aplanar, el papel sale
        todo negro (o todo blanco, según quién lo lea)."""
        from PIL import Image

        from pos_uniformes.scripts.preparar_dibujo_temporada import preparar

        im = preparar(self._carpeta() / "originales" / "halloween.png")
        datos = im.convert("L").tobytes()
        tinta = sum(1 for v in datos if v < 128)
        self.assertGreater(tinta, 0, "no quedó nada de dibujo")
        self.assertLess(tinta / len(datos), 0.9, "salió un bloque negro")

    def test_se_le_quita_el_aire_de_los_bordes(self) -> None:
        """Los márgenes del archivo son renglones en blanco que nadie pidió."""
        from PIL import Image

        im = Image.open(self._carpeta() / "halloween.png").convert("L")
        caja = im.point(lambda v: 255 if v < 128 else 0).getbbox()
        self.assertEqual(caja, (0, 0, im.width, im.height))
