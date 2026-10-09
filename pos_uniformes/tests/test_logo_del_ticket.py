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
    def test_el_texto_lleva_el_logo_y_dice_que_mirar(self) -> None:
        """Ya no son dos anchos: la comparación resolvió lo que tenía que
        resolver (era el reescalado) y el logo ahora viene al ancho exacto.
        Lo que queda por mirar son las serifas (2026-10-09)."""
        from pos_uniformes.scripts.probar_logo_ticket import texto_de_prueba

        texto = texto_de_prueba()
        self.assertIn(temp.marcador_de("logo"), texto)
        self.assertIn("serifas", texto)

    def test_ya_no_hay_un_logo_que_el_papel_tenga_que_encoger(self) -> None:
        """`logo_ancho` medía 576 y el útil son 552: lo encogía el propio
        renderizador, que es exactamente lo que lo apolillaba."""
        self.assertIsNone(temp.imagen_para_marcador("logo_ancho"))

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


class ElLogoNoDependeDeLaMaquinaQueArmaTests(unittest.TestCase):
    """El 07/10 Daniel mandó una reimpresión desde la Mac y salió sin logo.

    El texto preguntaba «¿esta PC dibuja tickets?» para meter el marcador. La
    Mac no dibuja, así que escribió el nombre; la principal —que sí dibuja—
    imprimió lo que le llegó. La pregunta estaba en la máquina equivocada: el
    ticket se arma donde se vende y se imprime donde está la impresora.
    """

    def test_el_marcador_lleva_el_nombre_como_respaldo(self) -> None:
        m = temp.marcador_de("logo", "MAXIMODA")
        self.assertEqual(m, f"{temp.MARCADOR_INICIO}logo|MAXIMODA{temp.MARCADOR_FIN}")

    def test_partir_marcador_separa_nombre_y_respaldo(self) -> None:
        self.assertEqual(temp.partir_marcador("logo|MAXIMODA"), ("logo", "MAXIMODA"))
        self.assertEqual(temp.partir_marcador("halloween"), ("halloween", ""))

    def test_el_respaldo_no_estorba_para_encontrar_el_png(self) -> None:
        self.assertIsNotNone(temp.imagen_para_marcador("logo|MAXIMODA"))

    def test_un_respaldo_no_puede_partir_el_marcador(self) -> None:
        """Un nombre con «]]» dentro dejaría el resto crudo en el papel."""
        m = temp.marcador_de("logo", "MAXI]]MODA|S.A.")
        self.assertEqual(m.count(temp.MARCADOR_FIN), 1)
        self.assertTrue(m.endswith(temp.MARCADOR_FIN))

    def test_sin_puntos_el_respaldo_se_escribe_centrado(self) -> None:
        salida = temp.sin_marcadores(temp.marcador_de("logo", "MAXIMODA") + "\nabajo")
        self.assertIn("MAXIMODA", salida)
        self.assertNotIn(temp.MARCADOR_INICIO, salida)
        self.assertNotIn("falta el dibujo", salida)
        self.assertEqual(salida.split("\n")[0].strip(), "MAXIMODA")

    def _ticket(self, **ajustes):
        """El texto del ticket de una venta mínima."""
        from decimal import Decimal
        from types import SimpleNamespace

        from pos_uniformes.services.sale_ticket_text_service import (
            build_sale_ticket_text,
        )

        cero = Decimal("0.00")
        venta = SimpleNamespace(
            detalles=[], cliente=None, observacion="", created_at=None,
            subtotal=cero, total=cero,
            descuento_porcentaje=cero, descuento_monto=cero,
        )
        return build_sale_ticket_text(
            sale=venta, business_name="MAXIMODA", **ajustes
        )

    def test_el_marcador_va_aunque_esta_maquina_no_dibuje(self) -> None:
        """El caso de la Mac: no dibuja, y aun así el ticket pide el logo."""
        from unittest.mock import patch

        from pos_uniformes.services.escpos_settings_cache_service import EscPosSettings

        apagado = EscPosSettings(enabled=False, ticket_como_imagen=False)
        with patch(
            "pos_uniformes.services.escpos_settings_cache_service.load_escpos_settings",
            return_value=apagado,
        ):
            texto = self._ticket()
        self.assertIn(temp.marcador_de("logo", "MAXIMODA"), texto)

    def test_el_nombre_no_se_dice_dos_veces(self) -> None:
        texto = self._ticket()
        encabezado = texto.split("\n")[0]
        self.assertIn(temp.MARCADOR_INICIO, encabezado)
        # El nombre aparece UNA vez: dentro del marcador, como respaldo.
        self.assertEqual(texto.count("MAXIMODA"), 1)

    def test_por_qt_el_logo_sale_escrito_y_no_apolillado(self) -> None:
        """Qt arma a 302 puntos y el driver estira a 576: el dibujo se deshace."""
        from pos_uniformes.ui.dialogs.printable_text_dialog import (
            _bloques_con_imagen,
        )

        texto = temp.marcador_de("logo", "MAXIMODA") + "\nTicket"
        self.assertIsNone(_bloques_con_imagen(texto))

    def test_por_escpos_en_texto_el_logo_sale_en_puntos(self) -> None:
        from pos_uniformes.ui.helpers.escpos_ticket_print_helper import (
            build_escpos_bytes,
        )

        datos = build_escpos_bytes(temp.marcador_de("logo", "MAXIMODA") + "\n")
        self.assertIn(b"\x1dv0", datos)        # raster: el logo son puntos
        self.assertNotIn(b"MAXIMODA", datos)   # y entonces no se escribe

    def test_si_el_png_no_se_puede_cargar_queda_el_nombre_escrito(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.ui.helpers import escpos_ticket_print_helper as esc

        texto = f"{temp.MARCADOR_INICIO}logo|MAXIMODA{temp.MARCADOR_FIN}\n"
        with patch.object(esc, "raster_de_imagen", side_effect=OSError("boom")):
            datos = esc.build_escpos_bytes(texto)
        self.assertIn(b"MAXIMODA", datos)

    def test_un_marcador_que_abre_el_ticket_no_sale_crudo(self) -> None:
        """El guardia era «¿ya escribí algo?» y daba falso en el primer trozo.

        Mientras el dibujo iba al pie nadie lo notó; el logo va en el PRIMER
        renglón, y el papel habría salido con «logo|MAXIMODA]]» escrito.
        """
        from pos_uniformes.ui.helpers.escpos_ticket_print_helper import (
            build_escpos_bytes,
        )

        datos = build_escpos_bytes(temp.marcador_de("logo", "MAXIMODA") + "\nTicket\n")
        self.assertNotIn(b"]]", datos)
        self.assertNotIn(b"logo", datos)


class ElCorteNoParteElUltimoRenglonTests(unittest.TestCase):
    """«feliz halloween sale cortado y hay mucho espacio desperdiciado arriba».

    Eran lo mismo: `GS V 0` corta donde está el papel, y se le adelantaba a
    mano con 3 renglones. La cuchilla está ~1.5 cm por encima del cabezal, así
    que tres no alcanzaban: el último renglón —el saludo— se partía, y el
    sobrante encabezaba el ticket siguiente con su hueco delante.
    """

    def _s(self, **kw):
        from pos_uniformes.services.escpos_settings_cache_service import EscPosSettings

        return EscPosSettings(**kw)

    def test_la_impresora_calcula_el_avance_y_corta(self) -> None:
        from pos_uniformes.ui.helpers.escpos_ticket_print_helper import (
            build_escpos_bytes,
        )

        datos = build_escpos_bytes("Hola\n", self._s())
        self.assertTrue(datos.endswith(b"\x1dVA\x00"))   # GS V 65 n

    def test_el_corte_parcial_usa_su_propio_comando(self) -> None:
        from pos_uniformes.ui.helpers.escpos_ticket_print_helper import (
            build_escpos_bytes,
        )

        datos = build_escpos_bytes("Hola\n", self._s(full_cut=False))
        self.assertTrue(datos.endswith(b"\x1dVB\x00"))   # GS V 66 n

    def test_ya_no_se_empujan_renglones_en_blanco(self) -> None:
        """Ese empujón a ciegas era el hueco de arriba del ticket siguiente."""
        from pos_uniformes.ui.helpers.escpos_ticket_print_helper import (
            build_escpos_bytes,
        )

        datos = build_escpos_bytes("Hola\n", self._s(feed_lines=3))
        self.assertNotIn(b"\n\n", datos)

    def test_el_saludo_es_lo_ultimo_y_no_queda_bajo_la_cuchilla(self) -> None:
        from pos_uniformes.ui.helpers.escpos_ticket_print_helper import (
            build_escpos_bytes,
        )

        datos = build_escpos_bytes("Gracias\n¡Feliz Halloween!\n", self._s())
        cuerpo, _, cola = datos.rpartition(b"\x1dVA")
        self.assertIn("¡Feliz Halloween!".encode("cp850"), cuerpo)
        self.assertEqual(cola, b"\x00")   # nada entre el saludo y el corte

    def test_una_impresora_que_no_lo_entienda_vuelve_al_avance_a_mano(self) -> None:
        from pos_uniformes.ui.helpers.escpos_ticket_print_helper import (
            build_escpos_bytes,
        )

        datos = build_escpos_bytes("Hola\n", self._s(corte_calculado=False, feed_lines=3))
        self.assertTrue(datos.endswith(b"\n\n\n\x1dV\x00"))


class ElLogoDeLaTiendaEnElPapelTests(unittest.TestCase):
    """El logo que mandó Daniel, preparado para la térmica (2026-10-09)."""

    def _carpeta(self):
        from pathlib import Path

        return Path(__file__).resolve().parents[1] / "assets" / "ticket"

    def test_el_original_se_queda_guardado(self) -> None:
        self.assertTrue((self._carpeta() / "originales" / "logo.png").exists())

    def test_sale_de_su_original(self) -> None:
        from PIL import Image

        from pos_uniformes.scripts.preparar_dibujo_temporada import preparar_a_lo_ancho

        carpeta = self._carpeta()
        esperado = preparar_a_lo_ancho(carpeta / "originales" / "logo.png")
        actual = Image.open(carpeta / "logo.png")
        self.assertEqual(actual.size, esperado.size)
        self.assertEqual(actual.convert("L").tobytes(), esperado.convert("L").tobytes())

    def test_mide_el_ancho_util_exacto(self) -> None:
        """Ni un punto más, y por eso nadie lo encoge.

        El renderizador solo reescala lo que pasa del ancho útil; cumpliendo
        esto, el logo llega al papel tal cual. Encogerlo es lo que lo
        apolillaba (07/10, medido en papel)."""
        from PIL import Image

        from pos_uniformes.services.ticket_imagen_service import ANCHO_PAPEL, MARGEN

        self.assertEqual(
            Image.open(self._carpeta() / "logo.png").width, ANCHO_PAPEL - MARGEN * 2
        )

    def test_queda_en_dos_tonos(self) -> None:
        from PIL import Image

        self.assertEqual(Image.open(self._carpeta() / "logo.png").mode, "1")
