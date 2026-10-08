"""Los botones de la propuesta del corte.

Daniel (2026-10-04): *"¿cómo harías más sencilla esta interacción?"*. El bot
tiene 31 comandos y ese mismo día se le agregó uno con cuatro palabras que hay
que recordar. Esta propuesta llega todas las tardes y contestarla es lo que más
se hace con el bot: que traiga sus botones es lo que más veces al día ahorra
escribir.
"""

from __future__ import annotations

import json
import unittest
from decimal import Decimal
from unittest.mock import patch

from pos_uniformes.services import telegram_corte_botones_service as cb


def _datos(botones: str) -> list[str]:
    return [b["callback_data"] for fila in json.loads(botones)["inline_keyboard"] for b in fila]


def _etiquetas(botones: str) -> list[str]:
    return [b["text"] for fila in json.loads(botones)["inline_keyboard"] for b in fila]


class LaPropuestaTests(unittest.TestCase):
    def test_lo_normal_es_un_solo_toque(self) -> None:
        datos = _datos(cb.botones_de_propuesta(Decimal("2820"), Decimal("1000")))
        self.assertIn("cc:ok", datos)

    def test_estan_las_cuatro_salidas(self) -> None:
        datos = _datos(cb.botones_de_propuesta(Decimal("2820"), Decimal("1000")))
        for esperado in ("cc:ok", "cc:retirar", "cc:fondo", "cc:cajon", "cc:no"):
            self.assertIn(esperado, datos, esperado)

    def test_el_texto_ya_no_dicta_comandos(self) -> None:
        # Antes la propuesta terminaba con cuatro renglones de instrucciones.
        from pos_uniformes.services import corte_remoto_service as crs
        from pathlib import Path

        codigo = Path(crs.__file__).read_text(encoding="utf-8")
        trozo = codigo[codigo.index("def texto_propuesta_corte"):codigo.index("def propuesta_de_corte")]
        self.assertNotIn("Toca /corte para hacerlo", trozo)


class LasCantidadesTests(unittest.TestCase):
    def test_la_calculada_va_primero(self) -> None:
        # Casi siempre es la que se usa.
        _, botones = cb.pantalla_cantidades("retirar", Decimal("2820"), Decimal("2820"))
        self.assertEqual(
            _etiquetas(botones)[0], "✅ Hacer el corte sacando $2,820  (lo calculado)"
        )

    def test_solo_se_ofrecen_las_que_caben(self) -> None:
        # Ofrecer $5,000 cuando hay $2,820 es ofrecer un error.
        _, botones = cb.pantalla_cantidades("retirar", Decimal("2820"), Decimal("2820"))
        etiquetas = " ".join(_etiquetas(botones))
        self.assertIn("$2,000", etiquetas)
        self.assertNotIn("$5,000", etiquetas)
        self.assertNotIn("$3,000", etiquetas)

    def test_cada_cantidad_hace_el_corte_con_ella(self) -> None:
        _, botones = cb.pantalla_cantidades("retirar", Decimal("2820"), Decimal("2820"))
        self.assertIn("cc:ret:2820", _datos(botones))

    def test_el_fondo_usa_su_propio_prefijo(self) -> None:
        _, botones = cb.pantalla_cantidades("fondo", Decimal("1000"), Decimal("3000"))
        self.assertIn("cc:fnd:1000", _datos(botones))

    def test_se_puede_volver(self) -> None:
        _, botones = cb.pantalla_cantidades("retirar", Decimal("2820"), Decimal("2820"))
        self.assertIn("cc:volver", _datos(botones))

    def test_dice_como_juntar_las_dos_cosas(self) -> None:
        # Sin estado entre toques, el caso raro sigue siendo por texto.
        texto, _ = cb.pantalla_cantidades("retirar", Decimal("2820"), Decimal("2820"))
        self.assertIn("/corte 5000 fondo 2000", texto)


class TocarLosBotonesTests(unittest.TestCase):
    def setUp(self) -> None:
        from contextlib import contextmanager
        from unittest.mock import MagicMock

        @contextmanager
        def _sesion():
            yield MagicMock()

        self.factory = _sesion

    def test_hacer_el_corte(self) -> None:
        from pos_uniformes.services import corte_remoto_service as crs

        with patch.object(crs, "hacer_corte_y_avisar") as hacer:
            hacer.return_value = MagicMockResultado("listo")
            aviso, texto, _ = cb.atender("cc:ok", session_factory=self.factory, quien="VEND-1")
        self.assertEqual(aviso, "Corte hecho")
        self.assertIsNone(hacer.call_args.kwargs["retirar"])
        self.assertIsNone(hacer.call_args.kwargs["fondo"])

    def test_retirar_una_cantidad(self) -> None:
        from pos_uniformes.services import corte_remoto_service as crs

        with patch.object(crs, "hacer_corte_y_avisar") as hacer:
            hacer.return_value = MagicMockResultado("listo")
            cb.atender("cc:ret:5000", session_factory=self.factory, quien="VEND-1")
        self.assertEqual(hacer.call_args.kwargs["retirar"], Decimal("5000.00"))

    def test_dejar_otro_fondo(self) -> None:
        from pos_uniformes.services import corte_remoto_service as crs

        with patch.object(crs, "hacer_corte_y_avisar") as hacer:
            hacer.return_value = MagicMockResultado("listo")
            cb.atender("cc:fnd:2000", session_factory=self.factory, quien="VEND-1")
        self.assertEqual(hacer.call_args.kwargs["fondo"], Decimal("2000.00"))

    def test_hoy_no(self) -> None:
        from pos_uniformes.services import corte_propuesta_service as prop

        with patch.object(prop, "cancelar", return_value=True):
            aviso, texto, _ = cb.atender("cc:no", session_factory=self.factory, quien="VEND-1")
        self.assertEqual(aviso, "Hoy no")
        self.assertIn("no se hace el corte", texto)

    def test_un_boton_mal_formado_no_revienta(self) -> None:
        aviso, _, _ = cb.atender("cc:ret:muchos", session_factory=self.factory, quien="VEND-1")
        self.assertEqual(aviso, "No conozco ese botón")

    def test_es_de_corte(self) -> None:
        self.assertTrue(cb.es_de_corte("cc:ok"))
        self.assertFalse(cb.es_de_corte("co:ver:1"))
        self.assertFalse(cb.es_de_corte("cj:pago:1"))

    def test_el_bot_enruta_estos_botones(self) -> None:
        from pathlib import Path

        from pos_uniformes.services import telegram_bot_service as bot

        codigo = Path(bot.__file__).read_text(encoding="utf-8")
        self.assertIn("cb.es_de_corte(dato)", codigo)


class MagicMockResultado:
    def __init__(self, mensaje: str) -> None:
        self.mensaje = mensaje
        self.hecho = True


if __name__ == "__main__":
    unittest.main()


class CadaBotonDiceLoQueVaAPasarTests(unittest.TestCase):
    """«esas opciones son poco claras» (Daniel, 07/10).

    «Retirar otra cantidad» y «Cambiar el fondo» suenan a ajustar un dato y
    volver, y en realidad llevan a una pantalla donde cualquier cifra cierra
    el corte de una. La advertencia existía, pero escrita `**hace el corte**`
    — y como el bot manda sin formato, salía con los asteriscos a la vista.
    """

    def test_el_boton_principal_dice_cuanto_saca(self) -> None:
        """Es la cifra de la decisión; tenerla en el botón evita releer."""
        etiquetas = _etiquetas(cb.botones_de_propuesta(Decimal("7098"), Decimal("500")))
        self.assertIn("✅ Hacer el corte y sacar $7,098", etiquetas)

    def test_los_que_abren_otra_pantalla_terminan_en_puntos(self) -> None:
        etiquetas = _etiquetas(cb.botones_de_propuesta(Decimal("7098"), Decimal("500")))
        self.assertIn("💵 Sacar otra cantidad…", etiquetas)
        self.assertIn("🪙 Dejar otro fondo…", etiquetas)

    def test_el_del_cajon_dice_que_se_va_a_hacer(self) -> None:
        """Era «Algo no salió del cajón»: una negación, sin decir qué pasa."""
        etiquetas = _etiquetas(cb.botones_de_propuesta(Decimal("7098"), Decimal("500")))
        self.assertIn("➖ Apuntar algo que ya salió del cajón", etiquetas)

    def test_cada_cantidad_avisa_que_hace_el_corte(self) -> None:
        for que, verbo in (("retirar", "sacando"), ("fondo", "dejando")):
            with self.subTest(pantalla=que):
                _, botones = cb.pantalla_cantidades(que, Decimal("2000"), Decimal("5000"))
                etiquetas = [e for e in _etiquetas(botones) if "Volver" not in e]
                self.assertTrue(etiquetas)
                for e in etiquetas:
                    self.assertIn("Hacer el corte", e)
                    self.assertIn(verbo, e)

    def test_ningun_mensaje_lleva_formato_que_el_bot_no_manda(self) -> None:
        """El bot manda sin parse_mode: los asteriscos salen tal cual.

        Pasó con la única advertencia del flujo, que se leía como basura."""
        textos = [
            cb.pantalla_cantidades("retirar", Decimal("2000"), Decimal("5000"))[0],
            cb.pantalla_cantidades("fondo", Decimal("500"), Decimal("5000"))[0],
        ]
        for t in textos:
            self.assertNotIn("**", t)
            self.assertNotIn("__", t)


class LaPropuestaDiceQueVaAPasarTests(unittest.TestCase):
    """El mensaje enumeraba lo que HAY y escondía lo que PASARÍA.

    «Se retiraría: $7,098.00 · queda de fondo $500.00» iba como un renglón
    más de la lista, con las dos cifras pegadas por un punto. Y que el corte
    IMPRIME el ticket en la tienda no se decía en ninguna parte, siendo lo que
    lo vuelve un hecho y no un número (Daniel, 07/10).
    """

    def _texto(self):
        from types import SimpleNamespace

        from pos_uniformes.services import corte_remoto_service as crs

        resumen = SimpleNamespace(
            efectivo=Decimal("8420.00"), operaciones=31, tarjeta=Decimal("1368.00")
        )
        estado = SimpleNamespace(
            resumen=resumen, pagos=Decimal("0.00"), total_retiros=Decimal("0.00"),
            reactivo=Decimal("500.00"), esperado=Decimal("8920.00"), desde=None,
        )
        with patch(
            "pos_uniformes.services.corte_caja_service.estado_caja", return_value=estado
        ), patch(
            "pos_uniformes.services.corte_caja_service.pagos_que_tocan_hoy", return_value=[]
        ):
            return crs.texto_propuesta_corte(object())

    def test_separa_lo_que_hay_de_lo_que_pasaria(self) -> None:
        self.assertIn("Si lo hago ahora:", self._texto())

    def test_dice_cuanto_sacas_y_cuanto_queda(self) -> None:
        self.assertIn("sacas $8,420.00 y se quedan $500.00 para mañana", self._texto())

    def test_avisa_que_se_imprime_en_la_tienda(self) -> None:
        """Es lo que no se puede deshacer desde el celular."""
        self.assertIn("se imprime el ticket en la tienda", self._texto())

    def test_la_tarjeta_se_explica(self) -> None:
        self.assertIn("no entra al cajón", self._texto())
