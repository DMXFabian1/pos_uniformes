"""El logo del negocio impreso en el ticket.

Lo delicado no es dibujarlo: es que un archivo que falta no deje un `[[IMG:…]]`
impreso en el papel del cliente, y que el logo no se confunda con los dibujos
de temporada.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pos_uniformes.services import temporada_service as temp


class BuscarLaImagenTests(unittest.TestCase):
    def test_encuentra_el_logo(self) -> None:
        ruta = temp.imagen_para_marcador("logo")
        self.assertIsNotNone(ruta)
        self.assertEqual(Path(ruta).name, "logo.png")

    def test_sigue_encontrando_los_dibujos_de_temporada(self) -> None:
        """Meter el logo no podía romper lo que ya funcionaba."""
        self.assertIsNotNone(temp.imagen_para_marcador("halloween"))

    def test_lo_que_no_existe_devuelve_None(self) -> None:
        self.assertIsNone(temp.imagen_para_marcador("no_existe_este"))

    def test_un_nombre_con_rutas_no_se_sale_de_la_carpeta(self) -> None:
        """El nombre viene dentro del texto del ticket: no puede ser una ruta."""
        self.assertIsNone(temp.imagen_para_marcador("../../etc/passwd"))
        self.assertIsNone(temp.imagen_para_marcador("/etc/passwd"))


class MarcadorTests(unittest.TestCase):
    def test_el_marcador_del_logo_se_arma(self) -> None:
        self.assertEqual(
            temp.marcador_de("logo"), f"{temp.MARCADOR_INICIO}logo{temp.MARCADOR_FIN}"
        )

    def test_sin_archivo_el_marcador_es_vacio(self) -> None:
        """Así quien arma el ticket no comprueba nada y nunca se imprime un
        `[[IMG:...]]` en el papel del cliente."""
        self.assertEqual(temp.marcador_de("no_existe_este"), "")
        self.assertEqual(temp.marcador_de(""), "")


class ElPngEsImprimibleTests(unittest.TestCase):
    def test_blanco_y_negro_puro_y_del_ancho_pensado(self) -> None:
        """Un gris tramado en un logo se lee como suciedad, no como gris."""
        from PIL import Image

        img = Image.open(temp.imagen_para_marcador("logo"))
        self.assertLessEqual(img.width, 576)        # cabe en el papel
        self.assertGreaterEqual(img.width, 400)     # y no sale perdido
        colores = {c for _, c in Image.open(temp.imagen_para_marcador("logo")).convert("L").getcolors()}
        self.assertEqual(colores, {0, 255})


class LaPruebaDeImpresionTests(unittest.TestCase):
    def test_el_texto_lleva_el_marcador_y_dice_que_mirar(self) -> None:
        from pos_uniformes.scripts.probar_logo_ticket import texto_de_prueba

        texto = texto_de_prueba()
        self.assertIn(temp.marcador_de("logo"), texto)
        self.assertIn("deshilachado", texto)

    def test_ninguna_linea_se_sale_del_papel(self) -> None:
        from pos_uniformes.scripts.probar_logo_ticket import texto_de_prueba
        from pos_uniformes.ui.helpers.ticket_print_layout_helper import TICKET_CHAR_WIDTH

        largas = [
            l for l in texto_de_prueba().split("\n")
            if len(l) > TICKET_CHAR_WIDTH and not l.startswith(temp.MARCADOR_INICIO)
        ]
        self.assertEqual(largas, [])


if __name__ == "__main__":
    unittest.main()
