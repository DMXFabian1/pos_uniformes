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
        self.assertEqual(_etiquetas(botones)[0], "$2,820  (lo calculado)")

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
