"""El ticket dibujado como imagen de 576 puntos.

Existe porque el camino de texto destruía el logo: Qt dibuja el ticket en una
página de 302 puntos (96 dpi) cuando la impresora tiene 576, y encima las
imágenes se encogían a la mitad con suavizado. Un logo de 500 puntos acababa
achicado 3.3 veces y re-estirado 3.8 por el driver (2026-10-07, medido en
papel).
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.services import ticket_imagen_service as ti

TICKET = "\n".join([
    "              MAXIMODA                ",
    "┌────────────────────────────────────┐",
    "│ Folio:                      V-1042 │",
    "├────────────────────────────────────┤",
    "│ Playera                    $370.00 │",
    "├════════════════════════════════════┤",
    "│ TOTAL A PAGAR:             $635.00 │",
    "└────────────────────────────────────┘",
    "        Gracias por tu compra.        ",
])


class _ConApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class ElAnchoEsElDelPapelTests(_ConApp):
    def test_mide_exactamente_576_puntos(self) -> None:
        """Un punto dibujado = un punto quemado. Si esto cambia, vuelve el
        reescalado que apolillaba el logo."""
        self.assertEqual(ti.render_ticket(TICKET).width(), 576)

    def test_el_alto_se_ajusta_al_contenido(self) -> None:
        corto = ti.render_ticket("una linea")
        largo = ti.render_ticket("\n".join(["una linea"] * 20))
        self.assertGreater(largo.height(), corto.height())
        self.assertLess(corto.height(), 200)


class LaRejillaDeColumnasTests(_ConApp):
    def test_reconoce_las_reglas_del_marco(self) -> None:
        self.assertTrue(ti._es_regla("┌────────────────────────────────────┐"))
        self.assertTrue(ti._es_regla("├════════════════════════════════════┤"))
        self.assertFalse(ti._es_regla("│ Folio:                      V-1042 │"))
        self.assertFalse(ti._es_regla("Gracias por tu compra."))

    def test_reconoce_el_total_venga_de_donde_venga(self) -> None:
        """El ticket de venta, el de apartado y el del corte lo ponen en
        lugares distintos, así que se reconoce por el texto."""
        self.assertTrue(ti._es_total("│ TOTAL A PAGAR:             $635.00 │"))
        self.assertTrue(ti._es_total("TOTAL: $100.00"))
        self.assertFalse(ti._es_total("│ Subtotal:                  $635.00 │"))
        self.assertFalse(ti._es_total("TOTAL A PAGAR:"))   # sin cifra no es la línea

    def test_una_fuente_proporcional_no_rompe_la_rejilla(self) -> None:
        """En la Mac `systemFont(FixedFont)` devuelve una proporcional: el
        dibujo por casillas es lo que mantiene cuadrados los importes."""
        import inspect

        self.assertIn("_escribir_en_rejilla", inspect.getsource(ti.render_ticket))


class ElDibujoNoSeTragaNadaTests(_ConApp):
    def test_un_dibujo_que_falta_se_dice_en_el_papel(self) -> None:
        from pos_uniformes.services.temporada_service import MARCADOR_FIN, MARCADOR_INICIO

        texto = f"ANTES\n{MARCADOR_INICIO}no_existe{MARCADOR_FIN}\nDESPUES"
        # No se puede leer el texto de una imagen, pero sí comprobar que ocupó
        # alto: si el marcador se tragara el renglón, mediría menos.
        con = ti.render_ticket(texto).height()
        sin = ti.render_ticket("ANTES\nDESPUES").height()
        self.assertGreater(con, sin)

    def test_el_logo_entra_a_su_tamaño(self) -> None:
        from pos_uniformes.services.temporada_service import marcador_de

        alto_con = ti.render_ticket(marcador_de("logo") + "\nhola").height()
        alto_sin = ti.render_ticket("hola").height()
        self.assertGreater(alto_con - alto_sin, 40)


class ElEnvioTests(_ConApp):
    def test_el_png_sale_en_bytes(self) -> None:
        png = ti.render_ticket_png(TICKET)
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_el_stream_lleva_corte_y_nada_de_texto(self) -> None:
        """Una imagen no tiene codificación: ese era medio problema del ticket."""
        from pos_uniformes.ui.helpers.escpos_ticket_print_helper import build_escpos_imagen

        datos = build_escpos_imagen(TICKET)
        self.assertIn(b"\x1dv0", datos)        # GS v 0: imagen de puntos
        self.assertNotIn(b"MAXIMODA", datos)   # el nombre va dibujado, no escrito
        self.assertIn(b"\x1dV", datos)         # corte


class ApagadoPorDefectoTests(unittest.TestCase):
    def test_no_se_enciende_solo_al_actualizar(self) -> None:
        """Cambia cómo se ve el ticket: eso se enciende a propósito."""
        from pos_uniformes.services.escpos_settings_cache_service import EscPosSettings

        self.assertFalse(EscPosSettings().ticket_como_imagen)

    def test_el_camino_de_siempre_se_usa_si_esta_apagado(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services.escpos_settings_cache_service import EscPosSettings
        from pos_uniformes.ui.dialogs import printable_text_dialog as ptd

        with patch(
            "pos_uniformes.services.escpos_settings_cache_service.load_escpos_settings",
            return_value=EscPosSettings(enabled=True, ticket_como_imagen=False),
        ):
            self.assertFalse(ptd._ticket_como_imagen_activo())


if __name__ == "__main__":
    unittest.main()


class LaPreviaEnseñaLoQueSaleTests(_ConApp):
    """Una previa que no se parece al papel no sirve para lo que sirve una
    previa. Con el ticket dibujado encendido seguía enseñando el texto viejo
    (Daniel, 2026-10-07: "las vistas previas se siguen viendo con el código de
    antes")."""

    def _editor(self, dibujado: bool):
        from unittest.mock import patch

        from pos_uniformes.services.escpos_settings_cache_service import EscPosSettings
        from pos_uniformes.ui.dialogs import printable_text_dialog as ptd

        with patch(
            "pos_uniformes.services.escpos_settings_cache_service.load_escpos_settings",
            return_value=EscPosSettings(enabled=True, ticket_como_imagen=dibujado),
        ):
            return ptd._build_ticket_editor(TICKET)

    def test_encendido_la_previa_es_la_misma_imagen(self) -> None:
        self.assertIn("<img", self._editor(True).toHtml())

    def test_apagado_la_previa_sigue_siendo_el_texto_de_siempre(self) -> None:
        editor = self._editor(False)
        self.assertNotIn("<img", editor.toHtml())
        self.assertIn("MAXIMODA", editor.toPlainText())

    def test_si_el_dibujo_truena_la_previa_no_se_queda_en_blanco(self) -> None:
        """Un adorno no puede dejar sin previa a quien va a cobrar."""
        from unittest.mock import patch

        from pos_uniformes.services.escpos_settings_cache_service import EscPosSettings
        from pos_uniformes.ui.dialogs import printable_text_dialog as ptd

        with patch(
            "pos_uniformes.services.escpos_settings_cache_service.load_escpos_settings",
            return_value=EscPosSettings(enabled=True, ticket_como_imagen=True),
        ), patch(
            "pos_uniformes.services.ticket_imagen_service.render_ticket",
            side_effect=RuntimeError("sin fuente"),
        ):
            editor = ptd._build_ticket_editor(TICKET)
        self.assertIn("MAXIMODA", editor.toPlainText())


class ElCorteDelTicketDibujadoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_corta_como_el_de_texto(self) -> None:
        """Dibujado o escrito, el papel se corta igual: lo decide la impresora.

        Si cada camino cortara a su manera, el saludo saldría partido en uno y
        entero en el otro, y nadie sabría cuál de los dos mirar.
        """
        from pos_uniformes.services.escpos_settings_cache_service import EscPosSettings
        from pos_uniformes.ui.helpers.escpos_ticket_print_helper import (
            build_escpos_imagen,
        )

        datos = build_escpos_imagen(TICKET, EscPosSettings())
        self.assertTrue(datos.endswith(b"\x1dVA\x00"))   # GS V 65 n
        self.assertNotIn(b"\n\n", datos[-16:])           # sin empujón a ciegas
