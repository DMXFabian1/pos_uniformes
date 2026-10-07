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
    def test_el_texto_lleva_los_dos_anchos_y_dice_que_mirar(self) -> None:
        from pos_uniformes.scripts.probar_logo_ticket import texto_de_prueba

        texto = texto_de_prueba()
        self.assertIn(temp.marcador_de("logo"), texto)
        self.assertIn(temp.marcador_de("logo_ancho"), texto)
        self.assertIn("reescalando", texto)

    def test_sin_argumentos_encola_y_avisa_que_no_elige_impresora(self) -> None:
        """Por la cola no se puede escoger en cuál sale: el kiosko se lleva el
        trabajo en menos de un segundo (pasó dos veces el 2026-10-07)."""
        from unittest.mock import MagicMock, patch

        from pos_uniformes.scripts import probar_logo_ticket as prueba

        with patch.object(prueba, "_imprimir_aqui") as aqui, \
             patch("pos_uniformes.database.connection.get_session") as ses, \
             patch("pos_uniformes.services.trabajos_service.enviar_ticket",
                   return_value=MagicMock(id=7)):
            ses.return_value.__enter__.return_value = MagicMock()
            self.assertEqual(prueba.main([]), 0)
        aqui.assert_not_called()

    def test_con_aqui_imprime_local_y_no_toca_la_cola(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.scripts import probar_logo_ticket as prueba

        with patch.object(prueba, "_imprimir_aqui", return_value=0) as aqui, \
             patch("pos_uniformes.services.trabajos_service.enviar_ticket") as encolar:
            self.assertEqual(prueba.main(["--aqui"]), 0)
        aqui.assert_called_once()
        encolar.assert_not_called()

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


class UnDibujoQueFaltaSeNotaTests(unittest.TestCase):
    """Si el PNG no está, el marcador desaparecía sin dejar rastro.

    Pasó con el logo el 2026-10-07: la hoja de prueba salió sin logo y sin
    pista de por qué — ni en el papel ni en la cola, que marcó el trabajo como
    HECHO. Un hueco que se ve es lo que permite preguntar."""

    def test_un_marcador_sin_dibujo_deja_aviso_en_el_papel(self) -> None:
        texto = temp.sin_marcadores(f"ANTES\n{temp.MARCADOR_INICIO}no_existe{temp.MARCADOR_FIN}\nDESPUES")
        self.assertIn("falta el dibujo: no_existe", texto)
        self.assertIn("ANTES", texto)
        self.assertIn("DESPUES", texto)

    def test_una_temporada_de_verdad_sigue_cayendo_a_su_dibujo_de_ascii(self) -> None:
        """El aviso es para lo que no tiene dibujo, no para reemplazarlo."""
        texto = temp.sin_marcadores(
            f"{temp.MARCADOR_INICIO}halloween{temp.MARCADOR_FIN}"
        )
        self.assertNotIn("falta el dibujo", texto)
        self.assertTrue(texto.strip())

    def test_sin_marcadores_no_toca_un_texto_normal(self) -> None:
        self.assertEqual(temp.sin_marcadores("Ticket de venta"), "Ticket de venta")
