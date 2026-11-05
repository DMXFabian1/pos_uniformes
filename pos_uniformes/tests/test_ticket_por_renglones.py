"""El ticket dibujado «por renglones», como lo manda el driver del fabricante.

La JM Thermal del Kiosko Principal quema sin avanzar el papel cuando el dibujo
llega en bloques `GS v 0` (2026-11-05). Con tiras `ESC * 33` + `ESC J` sale
completo. Aquí se prueba que lo que mandamos se puede volver a armar punto por
punto: si el decodificador de la prueba reconstruye la imagen, la impresora
también.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw

from pos_uniformes.services import escpos_settings_cache_service as cache
from pos_uniformes.services.escpos_settings_cache_service import EscPosSettings
from pos_uniformes.ui.helpers import escpos_ticket_print_helper as esc


def _png(img: Image.Image) -> io.BytesIO:
    salida = io.BytesIO()
    img.save(salida, format="PNG")
    salida.seek(0)
    return salida


def _imagen_de_prueba(ancho=576, alto=200) -> Image.Image:
    """Tinta arriba, un hueco en blanco de más de dos tiras, y tinta abajo a la izquierda."""
    img = Image.new("L", (ancho, alto), 255)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, ancho - 1, 3), fill=0)          # raya de lado a lado
    d.rectangle((10, 10, 40, 30), fill=0)               # un bloque que cruza dos tiras
    d.line((100, 5, 300, 45), fill=0, width=3)          # diagonal
    d.rectangle((20, 150, 90, 170), fill=0)             # abajo, solo a la izquierda
    return img


def decodificar(datos: bytes, ancho: int) -> list[list[int]]:
    """Vuelve a armar las filas de puntos a partir de `ESC * 33` y `ESC J`."""
    filas: list[list[int]] = []
    tira: list[list[int]] | None = None
    i = 0
    while i < len(datos):
        b = datos[i]
        if b == 0x1B and datos[i + 1] == ord("*"):
            assert datos[i + 2] == 33, "solo se usa el modo de 24 puntos"
            columnas = datos[i + 3] + 256 * datos[i + 4]
            cuerpo = datos[i + 5:i + 5 + 3 * columnas]
            tira = [[0] * ancho for _ in range(24)]
            for x in range(columnas):
                for k in range(3):
                    byte = cuerpo[3 * x + k]
                    for bit in range(8):
                        if byte & (0x80 >> bit):
                            tira[k * 8 + bit][x] = 1
            i += 5 + 3 * columnas
        elif b == 0x1B and datos[i + 1] == ord("J"):
            n = datos[i + 2]
            if tira is not None:
                filas.extend(tira[:n])
                filas.extend([[0] * ancho for _ in range(max(0, n - 24))])
                tira = None
            else:
                filas.extend([[0] * ancho for _ in range(n)])
            i += 3
        elif b == 0x00:
            i += 1
        else:
            raise AssertionError(f"byte inesperado {b:#x} en la posición {i}")
    return filas


class RenglonesTests(unittest.TestCase):
    def test_se_puede_volver_a_armar_punto_por_punto(self) -> None:
        img = _imagen_de_prueba()
        datos = esc.renglones_de_imagen(_png(img))
        filas = decodificar(datos, 576)
        original = img.point(lambda v: 0 if v < 128 else 255, mode="1")
        px = original.load()
        self.assertGreaterEqual(len(filas), img.height)           # lo que sobra es blanco de la última tira
        for y in range(img.height):
            self.assertEqual(filas[y], [0 if px[x, y] else 1 for x in range(576)], f"fila {y}")
        self.assertFalse(any(any(f) for f in filas[img.height:]))

    def test_no_usa_gs_v_0_ni_centrado(self) -> None:
        datos = esc.renglones_de_imagen(_png(_imagen_de_prueba()))
        self.assertNotIn(bytes([0x1D, ord("v"), ord("0")]), datos)
        self.assertNotIn(bytes([0x1B, ord("a"), 1]), datos)

    def test_las_tiras_en_blanco_son_solo_avance(self) -> None:
        datos = esc.renglones_de_imagen(_png(_imagen_de_prueba()))
        tiras = datos.count(bytes([0x1B, ord("*"), 33]))
        # 200 filas son 9 tiras; con tinta solo hay 3 arriba (0-47 la diagonal) y 1-2 abajo.
        self.assertLess(tiras, 6)
        self.assertEqual(len(decodificar(datos, 576)) % 24, 0)

    def test_no_manda_las_columnas_en_blanco_de_la_derecha(self) -> None:
        img = Image.new("L", (576, 24), 255)
        ImageDraw.Draw(img).rectangle((0, 0, 9, 23), fill=0)       # 10 columnas de tinta
        datos = esc.renglones_de_imagen(_png(img))
        self.assertEqual(datos[:5], bytes([0x1B, ord("*"), 33, 10, 0]))
        self.assertEqual(len(datos), 5 + 30 + 1 + 3)

    def test_una_imagen_angosta_se_centra_con_columnas_en_blanco(self) -> None:
        img = Image.new("L", (240, 24), 0)                          # toda negra, 240 de ancho
        datos = esc.renglones_de_imagen(_png(img))
        fila = decodificar(datos, 576)[0]
        margen = (576 - 240) // 2
        self.assertEqual(sum(fila), 240)
        self.assertEqual(fila.index(1), margen)

    def test_una_imagen_toda_en_blanco_solo_avanza(self) -> None:
        datos = esc.renglones_de_imagen(_png(Image.new("L", (576, 600), 255)))
        self.assertNotIn(bytes([0x1B, ord("*")]), datos)
        self.assertEqual(len(decodificar(datos, 576)), 600)          # 25 tiras de 24: 255 + 255 + 90


class TicketCompletoTests(unittest.TestCase):
    def _ticket(self, **ajustes) -> bytes:
        s = replace(EscPosSettings(), **ajustes)
        with patch("pos_uniformes.services.ticket_imagen_service.render_ticket_png",
                   return_value=_png(_imagen_de_prueba()).getvalue()):
            return esc.build_escpos_imagen("lo que sea", s)

    def test_con_el_ajuste_va_como_el_driver_del_fabricante(self) -> None:
        datos = self._ticket(imagen_por_renglones=True)
        # La cabecera copiada del driver JM, byte por byte.
        self.assertEqual(
            datos[:21].hex(" ").upper(),
            "1B 40 1B 3D 01 1B 52 00 1B 74 00 1D 50 00 00 1B 32 00 1B 4A 08",
        )
        self.assertNotIn(bytes([0x1D, ord("v"), ord("0")]), datos)
        # Al final: ESC J 0, el corte de ESTA impresora y un reset.
        self.assertEqual(datos[-9:], bytes([0x1B, ord("J"), 0, 0x1D, ord("V"), 65, 0, 0x1B, ord("@")]))

    def test_respeta_el_corte_parcial(self) -> None:
        datos = self._ticket(imagen_por_renglones=True, full_cut=False)
        self.assertEqual(datos[-6:-2], bytes([0x1D, ord("V"), 66, 0]))

    def test_sin_el_ajuste_nada_cambia(self) -> None:
        datos = self._ticket()
        self.assertIn(bytes([0x1D, ord("v"), ord("0")]), datos)
        self.assertNotIn(bytes([0x1B, ord("*"), 33]), datos)


class AjusteTests(unittest.TestCase):
    def test_apagado_de_fabrica_y_se_guarda(self) -> None:
        self.assertFalse(EscPosSettings().imagen_por_renglones)
        with tempfile.TemporaryDirectory() as tmp, patch.object(cache, "satellite_data_dir", return_value=Path(tmp)):
            self.assertFalse(cache.load_escpos_settings().imagen_por_renglones)
            cache.save_escpos_settings(replace(EscPosSettings(), imagen_por_renglones=True, ticket_como_imagen=True))
            leido = cache.load_escpos_settings()
        self.assertTrue(leido.imagen_por_renglones)
        self.assertTrue(leido.ticket_como_imagen)

    def test_un_archivo_viejo_sin_la_clave_se_lee_igual(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(cache, "satellite_data_dir", return_value=Path(tmp)):
            (Path(tmp) / "data").mkdir()
            (Path(tmp) / "data" / "escpos_settings.json").write_text('{"enabled": true, "ticket_como_imagen": true}')
            leido = cache.load_escpos_settings()
        self.assertTrue(leido.ticket_como_imagen)
        self.assertFalse(leido.imagen_por_renglones)


if __name__ == "__main__":
    unittest.main()
