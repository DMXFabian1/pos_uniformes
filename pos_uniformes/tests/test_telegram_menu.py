"""El menú del bot: tocar en vez de recordar.

Son 19 comandos y Daniel pidió la chuleta justamente porque se le olvidan
(2026-09-25). Lo que se cuida aquí: que el menú no deje el dinero a un toque,
y que se navegue sin llenar el chat.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from pos_uniformes.services import telegram_menu_service as menu


def _textos(botones: str) -> list[str]:
    return [b["text"] for fila in json.loads(botones)["inline_keyboard"] for b in fila]


def _datos(botones: str) -> list[str]:
    return [b["callback_data"] for fila in json.loads(botones)["inline_keyboard"] for b in fila]


class _Sesion:
    def __call__(self): return self
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def commit(self): pass


class RaizTest(unittest.TestCase):
    def test_el_menu_trae_lo_de_todos_los_dias(self):
        texto, botones = menu.menu_raiz()
        self.assertIn("¿Qué", texto)
        juntos = " ".join(_textos(botones))
        for esperado in ("Caja", "Pagos", "Quién vino", "Qué contar", "Resumen"):
            self.assertIn(esperado, juntos)

    def test_el_dinero_no_se_mueve_desde_el_tablero(self):
        """Ver los cortes sí; hacer uno no. Hacer corte y retirar llevan
        cantidad y motivo, y eso se escribe."""
        acciones = {d[len(menu.PREFIJO):] for d in _datos(menu.menu_raiz()[1])}
        self.assertIn("cortes", acciones, "verlos sí está")
        for mueve in ("corte", "retiro", "pagarok"):
            self.assertNotIn(mueve, acciones, f"{mueve} no puede estar a un toque")

    def test_los_botones_caben_en_lo_que_telegram_deja(self):
        for dato in _datos(menu.menu_raiz()[1]):
            self.assertLessEqual(len(dato.encode()), 64, dato)


class ReconocerTest(unittest.TestCase):
    def test_distingue_sus_botones_de_los_de_asistencia(self):
        self.assertTrue(menu.es_del_menu("m:pagos"))
        self.assertFalse(menu.es_del_menu("asis:VEND-4:vino"))
        self.assertFalse(menu.es_del_menu(""))


class NavegarTest(unittest.TestCase):
    def _atender(self, dato, **parches):
        from pos_uniformes.services import telegram_bot_service as bot

        with patch.object(bot, "atender_texto", return_value="lo que sea") as texto_mock:
            with patch.multiple("pos_uniformes.services.telegram_pagos_service", **parches) if parches \
                    else _Nada():
                salida = menu.atender(dato, session_factory=_Sesion())
        self.texto_mock = texto_mock
        return salida

    def test_de_una_vista_siempre_se_puede_volver(self):
        _aviso, _texto, botones = self._atender("m:contar")
        self.assertIn("‹ Menú", _textos(botones))

    def test_volver_regresa_al_menu(self):
        _aviso, texto, botones = menu.atender("m:raiz", session_factory=_Sesion())
        self.assertEqual(texto, menu.menu_raiz()[0])

    def test_un_boton_que_no_existe_no_truena(self):
        aviso, texto, botones = menu.atender("m:loquesea", session_factory=_Sesion())
        self.assertIn("No conozco", aviso)
        self.assertEqual((texto, botones), ("", ""))

    def test_las_vistas_de_mirar_usan_el_comando_de_siempre(self):
        # Si el menú tuviera su propia versión, podría decir otra cosa que /contar.
        self._atender("m:contar")
        self.texto_mock.assert_called_once()
        self.assertEqual(self.texto_mock.call_args[0][0], "/contar")


class _Nada:
    def __enter__(self): return None
    def __exit__(self, *a): return False


class PagarConDosToquesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pagados = []

    def _parches(self, *, pendiente=True):
        from pos_uniformes.services import telegram_pagos_service as pg

        return patch.multiple(
            pg,
            desglose_por_code=lambda *a, **k: "Evelyn Ortiz\nTOTAL: $1,412.00",
            tiene_pendiente=lambda *a, **k: pendiente,
            pagar_por_code=lambda *a, **k: self.pagados.append(a) or "✅ Pagado a Evelyn Ortiz",
        )

    def test_el_primer_toque_solo_enseña_el_desglose(self):
        with self._parches():
            _aviso, texto, botones = menu.atender("m:pagar:VEND-6", session_factory=_Sesion())
        self.assertIn("TOTAL", texto)
        self.assertIn("✅ Sí, pagar", _textos(botones))
        self.assertEqual(self.pagados, [], "el dinero no se mueve con el primer toque")

    def test_el_segundo_toque_si_paga(self):
        with self._parches():
            aviso, texto, botones = menu.atender("m:pagarok:VEND-6", session_factory=_Sesion())
        self.assertEqual(len(self.pagados), 1)
        self.assertIn("Pagado", texto)
        self.assertEqual(aviso, "Pagado")

    def test_a_quien_no_debe_nada_no_le_sale_el_boton(self):
        with self._parches(pendiente=False):
            _aviso, _texto, botones = menu.atender("m:pagar:VEND-9", session_factory=_Sesion())
        self.assertNotIn("✅ Sí, pagar", _textos(botones))


class ElBotLoConoceTest(unittest.TestCase):
    def test_el_despachador_manda_los_toques_del_menu_al_menu(self):
        from pathlib import Path

        fuente = (
            Path(__file__).resolve().parent.parent / "services" / "telegram_bot_service.py"
        ).read_text(encoding="utf-8")
        self.assertIn("menu.es_del_menu(dato)", fuente)
        self.assertIn('cmd.nombre in ("menu", "menú")', fuente)

    def test_esta_en_la_ayuda(self):
        from pos_uniformes.services.telegram_bot_service import AYUDA

        self.assertIn("/menu", AYUDA)


class TableroTest(unittest.TestCase):
    """El menú llega con el día puesto: abrirlo y saber cómo va es el mismo gesto."""

    def test_sin_sesion_sigue_siendo_la_pregunta_de_siempre(self):
        texto, botones = menu.menu_raiz()
        self.assertEqual(texto, "¿Qué quieres ver?")
        self.assertTrue(_textos(botones))

    def test_con_sesion_encabeza_con_el_dia(self):
        with patch.object(menu, "cabecera", return_value="📅 Hoy · …\n\n¿Qué quieres ver?"):
            texto, _b = menu.menu_raiz(object())
        self.assertIn("📅 Hoy", texto)

    def test_si_el_dia_no_se_puede_leer_el_menu_no_se_queda_sin_botones(self):
        # Los botones son lo que no puede faltar: sin cifras se navega igual.
        from pos_uniformes.services import resumen_diario_service as rd

        with patch.object(rd, "recolectar", side_effect=RuntimeError("sin base")):
            texto = menu.cabecera(object())
        self.assertEqual(texto, "¿Qué quieres ver?")

    def test_cortes_esta_en_el_tablero(self):
        self.assertIn("🧾 Cortes", _textos(menu.menu_raiz()[1]))



if __name__ == "__main__":
    unittest.main()
