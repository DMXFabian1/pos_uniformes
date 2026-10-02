"""El dibujo de temporada, impreso como puntos y no como caracteres.

Daniel (02/10) pidió el dibujito y preguntó si se podía con PNG. Sí: la térmica
sabe imprimir mapas de bits (`GS v 0`). Lo que complica no es el comando, es que
el ticket viaja como una **cadena** por toda la cola de impresión — así que la
imagen no puede ir dentro. Va un marcador, y cada camino lo resuelve: ESC/POS lo
cambia por los puntos; la vista previa y QPrinter, por el dibujo de ASCII.
"""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from pos_uniformes.services import temporada_service as temp
from pos_uniformes.ui.helpers import escpos_ticket_print_helper as esc

_HALLOWEEN = date(2026, 10, 31)


class ElMarcadorTests(unittest.TestCase):
    def test_hay_un_png_por_cada_temporada(self) -> None:
        for t in temp.TEMPORADAS:
            archivo = temp.ARCHIVOS.get(t.nombre)
            self.assertIsNotNone(archivo, t.nombre)
            self.assertIsNotNone(temp.imagen_para_marcador(archivo), t.nombre)

    def test_un_dia_cualquiera_no_trae_marcador(self) -> None:
        self.assertEqual(temp.marcador_de_ticket(date(2026, 3, 18)), "")

    def test_si_falta_el_png_se_cae_al_ascii(self) -> None:
        # El dibujo de caracteres no se tiró: es la red por si el archivo no está.
        with patch.object(temp, "imagen_para_marcador", return_value=None):
            self.assertEqual(temp.marcador_de_ticket(_HALLOWEEN), "")
        self.assertTrue(temp.renglones_de_ticket(_HALLOWEEN))

    def test_no_se_sale_de_la_carpeta_de_dibujos(self) -> None:
        # El nombre llega dentro del ticket: no puede servir para leer otra cosa.
        for malo in ("../../etc/passwd", "..", "/etc/hosts", ""):
            self.assertIsNone(temp.imagen_para_marcador(malo), malo)


class ElRasterTests(unittest.TestCase):
    """Los puntos que se le mandan a la impresora."""

    def _imagen(self, pixeles: list[str]):
        """Dibuja una imagen chiquita desde texto: '#' negro, '.' blanco."""
        import tempfile
        from pathlib import Path

        from PIL import Image

        alto, ancho = len(pixeles), len(pixeles[0])
        img = Image.new("1", (ancho, alto), 1)
        for y, fila in enumerate(pixeles):
            for x, c in enumerate(fila):
                if c == "#":
                    img.putpixel((x, y), 0)
        ruta = Path(tempfile.mkdtemp()) / "x.png"
        img.save(ruta)
        return ruta

    def test_la_cabecera_dice_el_tamaño(self) -> None:
        ruta = self._imagen(["#" * 16, "." * 16])
        datos = esc.raster_de_imagen(ruta)
        self.assertEqual(datos[:4], bytes([0x1D, ord("v"), ord("0"), 0]))
        self.assertEqual(datos[4] + (datos[5] << 8), 2)   # 16 puntos = 2 bytes
        self.assertEqual(datos[6] + (datos[7] << 8), 2)   # 2 filas

    def test_un_punto_negro_prende_su_bit(self) -> None:
        # El bit más significativo es el punto de la izquierda.
        ruta = self._imagen(["#.......", ".......#"])
        datos = esc.raster_de_imagen(ruta)[8:]
        self.assertEqual(datos[0], 0b10000000)
        self.assertEqual(datos[1], 0b00000001)

    def test_el_ancho_se_redondea_a_bytes_sin_basura(self) -> None:
        # 5 puntos ocupan un byte; los 3 de sobra tienen que ir en blanco, no
        # con lo que hubiera en memoria.
        ruta = self._imagen(["#####"])
        datos = esc.raster_de_imagen(ruta)
        self.assertEqual(datos[4] + (datos[5] << 8), 1)
        self.assertEqual(datos[8], 0b11111000)

    def test_los_grises_se_deciden_a_blanco_o_negro(self) -> None:
        import tempfile
        from pathlib import Path

        from PIL import Image

        img = Image.new("L", (8, 1), 200)      # gris claro
        img.putpixel((0, 0), 20)               # gris oscuro
        ruta = Path(tempfile.mkdtemp()) / "g.png"
        img.save(ruta)
        self.assertEqual(esc.raster_de_imagen(ruta)[8], 0b10000000)

    def test_la_calabaza_de_verdad_cabe_en_el_papel(self) -> None:
        ruta = temp.imagen_para_marcador("halloween")
        datos = esc.raster_de_imagen(ruta)
        ancho_bytes = datos[4] + (datos[5] << 8)
        self.assertLessEqual(ancho_bytes * 8, esc.PUNTOS_POR_LINEA)


class EnElTicketTests(unittest.TestCase):
    def _ticket(self) -> str:
        with patch.object(temp, "actual", return_value=temp.TEMPORADAS[2]):
            return "Gracias.\n" + temp.marcador_de_ticket() + "\n¡Feliz Halloween!\n"

    def test_escpos_manda_puntos_y_no_el_texto_crudo(self) -> None:
        datos = esc.build_escpos_bytes(self._ticket())
        self.assertIn(b"\x1dv0", datos)
        self.assertNotIn(b"[[IMG", datos)

    def test_el_dibujo_va_centrado_y_se_vuelve_a_la_izquierda(self) -> None:
        # Si no se repone la alineación, todo lo que siga sale centrado.
        datos = esc.build_escpos_bytes(self._ticket())
        self.assertLess(datos.index(b"\x1ba\x01"), datos.index(b"\x1ba\x00"))

    def test_si_el_dibujo_no_se_puede_leer_el_ticket_sale_igual(self) -> None:
        with patch.object(esc, "raster_de_imagen", side_effect=OSError("archivo roto")):
            datos = esc.build_escpos_bytes(self._ticket())
        self.assertIn("Gracias.".encode("cp850"), datos)
        self.assertNotIn(b"[[IMG", datos)

    def test_un_marcador_de_un_dibujo_que_no_existe_se_omite(self) -> None:
        datos = esc.build_escpos_bytes("Hola\n[[IMG:no_existe]]\nAdios\n")
        self.assertNotIn(b"[[IMG", datos)
        self.assertIn("Adios".encode("cp850"), datos)

    def test_la_vista_previa_enseña_el_dibujo_de_ascii(self) -> None:
        # Ahí no se imprimen puntos: sin esto saldría «[[IMG:halloween]]».
        texto = temp.sin_marcadores(self._ticket(), _HALLOWEEN)
        self.assertNotIn("[[IMG", texto)
        self.assertIn('.-"""-.', texto)

    def test_sin_marcador_no_toca_nada(self) -> None:
        self.assertEqual(temp.sin_marcadores("Hola\nAdios"), "Hola\nAdios")

    def test_qprinter_dibuja_el_PNG_y_no_lo_cambia_por_texto(self) -> None:
        # Este era el hueco: los tickets NO pasan por ESC/POS —ese camino es
        # solo de las hojas de conteo— así que el raster del otro lado no les
        # servía de nada y el dibujo habría salido en caracteres.
        from pathlib import Path

        codigo = (
            Path(__file__).resolve().parents[1] / "ui" / "dialogs" / "printable_text_dialog.py"
        ).read_text(encoding="utf-8")
        self.assertIn("painter.drawImage(", codigo)
        self.assertIn("_bloques_con_imagen(content)", codigo)
        # Y la vista previa sí lo cambia por el de caracteres: ahí no hay papel.
        self.assertIn("editor.setPlainText(_sin_marcadores(content))", codigo)


if __name__ == "__main__":
    unittest.main()


class ElDibujoSaleDelMarcadorTests(unittest.TestCase):
    """Y no de la fecha de hoy, que parece lo mismo y no lo es."""

    def test_un_ticket_reimpreso_otro_dia_conserva_SU_dibujo(self) -> None:
        # Un ticket de Halloween reimpreso el 1 de noviembre llevaba el marcador
        # de la calabaza y se le ponía la calavera — o nada, si ya no había
        # temporada. Lo que manda es lo que dice el papel.
        texto = f"{temp.MARCADOR_INICIO}halloween{temp.MARCADOR_FIN}\n"
        de_muertos = date(2026, 11, 2)
        salida = temp.sin_marcadores(texto, de_muertos)
        self.assertIn("'-www-'", salida)        # la boca de la calabaza
        self.assertNotIn("'-|||-'", salida)     # NO los dientes de la calavera

    def test_sirve_aunque_hoy_no_haya_temporada(self) -> None:
        texto = f"{temp.MARCADOR_INICIO}navidad{temp.MARCADOR_FIN}\n"
        salida = temp.sin_marcadores(texto, date(2026, 3, 18))
        self.assertIn("/_\\", salida)

    def test_un_marcador_desconocido_no_deja_basura(self) -> None:
        salida = temp.sin_marcadores(f"a{temp.MARCADOR_INICIO}vete_a_saber{temp.MARCADOR_FIN}b")
        self.assertNotIn("IMG", salida)
        self.assertIn("a", salida)
        self.assertIn("b", salida)

    def test_la_vuelta_de_archivo_a_temporada(self) -> None:
        self.assertEqual(temp.temporada_de_archivo("halloween").nombre, "Halloween")
        self.assertIsNone(temp.temporada_de_archivo("no_existe"))


class ElTicketDibujaLaImagenTests(unittest.TestCase):
    """Partir el ticket en bloques para meter el PNG entre el texto."""

    def setUp(self) -> None:
        from pos_uniformes.ui.dialogs import printable_text_dialog as ptd

        self.ptd = ptd

    def test_sin_marcador_no_se_parte_nada(self) -> None:
        # None = «el camino de siempre, sin pagar ni un cálculo de más».
        self.assertIsNone(self.ptd._bloques_con_imagen("Hola\nAdios"))

    def test_con_marcador_quedan_texto_imagen_texto(self) -> None:
        texto = f"arriba\n{temp.MARCADOR_INICIO}halloween{temp.MARCADOR_FIN}\nabajo"
        bloques = self.ptd._bloques_con_imagen(texto)
        self.assertEqual([c for c, _ in bloques], ["texto", "imagen", "texto"])
        self.assertIn("arriba", bloques[0][1])
        self.assertTrue(bloques[1][1].endswith("halloween.png"))
        self.assertIn("abajo", bloques[2][1])

    def test_si_falta_el_PNG_se_deja_el_camino_viejo(self) -> None:
        texto = f"a{temp.MARCADOR_INICIO}no_existe{temp.MARCADOR_FIN}b"
        self.assertIsNone(self.ptd._bloques_con_imagen(texto))

    def test_dos_dibujos_en_el_mismo_papel(self) -> None:
        m = f"{temp.MARCADOR_INICIO}navidad{temp.MARCADOR_FIN}"
        bloques = self.ptd._bloques_con_imagen(f"a{m}b{m}c")
        self.assertEqual([c for c, _ in bloques], ["texto", "imagen", "texto", "imagen", "texto"])
