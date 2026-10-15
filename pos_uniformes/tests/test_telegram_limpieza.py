"""El chat se limpia solo: cada mañana, con un menú nuevo fijado.

Daniel (2026-10-08): «me gustaría que quede un menú fijado, y lo demás lo borre
24 horas después». Desde el 2026-10-15: una limpieza al día a la hora de
apertura, con menú nuevo; alertas, cortes y resúmenes se quedan dos días.

El límite de Telegram que manda sobre el diseño: pasadas 48 horas ya no se
puede borrar nada.
"""

from __future__ import annotations

import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from pos_uniformes.services import telegram_limpieza_service as limpieza

HORA = 3600.0


class LaLimpiezaDeLaMananaTests(unittest.TestCase):
    """Una vez al día, a la hora de apertura (Daniel, 2026-10-15): lo de antes
    de abrir se va; alertas, cortes y resúmenes se quedan dos días."""

    #: Miércoles 15/10/2026, 9:05 (abre a las 9:00).
    HOY = datetime(2026, 10, 15, 9, 5)

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        parche = patch.object(
            limpieza, "ruta_estado",
            return_value=Path(self._dir.name) / "bot_mensajes.json",
        )
        parche.start()
        self.addCleanup(parche.stop)

    def _anotar(self, mid: int, cuando: datetime, *, conservar: bool = False) -> None:
        limpieza.anotar(mid, conservar=conservar, ts=cuando.timestamp())

    def _limpiar(self, ahora=None, borrar=None) -> list[int]:
        borrados: list[int] = []
        limpieza.limpiar_del_dia(
            borrar=borrar or (lambda m: borrados.append(m) or True), ahora=ahora or self.HOY,
        )
        return borrados

    def test_lo_de_ayer_se_va_en_la_manana(self) -> None:
        self._anotar(10, datetime(2026, 10, 14, 17, 30))
        self.assertEqual(self._limpiar(), [10])

    def test_lo_de_hoy_despues_de_abrir_se_queda(self) -> None:
        self._anotar(10, datetime(2026, 10, 15, 9, 1))
        self.assertEqual(self._limpiar(), [])

    def test_lo_conservado_se_queda_dos_dias_y_se_va_al_tercero(self) -> None:
        # Una alerta del lunes se ve lunes y martes; se va el miércoles.
        self._anotar(1, datetime(2026, 10, 13, 18, 0), conservar=True)   # lunes
        self._anotar(2, datetime(2026, 10, 14, 11, 0), conservar=True)   # martes
        self.assertEqual(self._limpiar(), [1])
        self.assertEqual([m["id"] for m in limpieza._leer()["mensajes"]], [2])

    def test_pasadas_48_horas_se_olvida_en_vez_de_insistir(self) -> None:
        """Telegram ya no deja borrarlo: se olvida, no se reintenta cada día."""
        self._anotar(10, datetime(2026, 10, 13, 8, 0))     # 49 h antes
        self.assertEqual(self._limpiar(), [])
        self.assertEqual(limpieza._leer()["mensajes"], [])

    def test_si_el_borrado_falla_se_reintenta_luego(self) -> None:
        self._anotar(10, datetime(2026, 10, 14, 17, 30))
        self._limpiar(borrar=lambda m: False)
        self.assertEqual([m["id"] for m in limpieza._leer()["mensajes"]], [10])

    def test_un_error_de_red_tampoco_pierde_el_mensaje(self) -> None:
        self._anotar(10, datetime(2026, 10, 14, 17, 30))

        def truena(_):
            raise OSError("sin red")

        self._limpiar(borrar=truena)
        self.assertEqual([m["id"] for m in limpieza._leer()["mensajes"]], [10])

    def test_el_menu_fijado_no_se_borra_aqui(self) -> None:
        """El menú lo renueva el bot después; aquí nunca se borra.

        Se arma el archivo a mano con el menú TAMBIÉN en la lista: es el caso
        que de verdad puede pasar (un archivo viejo o editado a mano)."""
        import json

        viejo = datetime(2026, 10, 14, 17, 0).timestamp()
        limpieza.ruta_estado().parent.mkdir(parents=True, exist_ok=True)
        limpieza.ruta_estado().write_text(json.dumps({
            "menu_id": 10,
            "mensajes": [{"id": 10, "ts": viejo}, {"id": 11, "ts": viejo}],
        }), encoding="utf-8")
        self.assertEqual(self._limpiar(), [11])
        self.assertEqual(limpieza.menu_fijado(), 10)

    def test_el_menu_no_se_apunta_aunque_pase_por_el_mismo_camino(self) -> None:
        limpieza.recordar_menu(10)
        limpieza.anotar(10)
        self.assertEqual(limpieza._leer()["mensajes"], [])

    def test_el_mismo_mensaje_no_se_apunta_dos_veces(self) -> None:
        limpieza.anotar(7)
        limpieza.anotar(7)
        self.assertEqual(len(limpieza._leer()["mensajes"]), 1)

    def test_una_vez_al_dia_y_desde_la_apertura(self) -> None:
        self.assertFalse(limpieza.toca_limpiar(datetime(2026, 10, 15, 8, 59)))   # aún no abre
        self.assertTrue(limpieza.toca_limpiar(self.HOY))
        self._limpiar()
        self.assertFalse(limpieza.toca_limpiar(datetime(2026, 10, 15, 17, 0)))   # ya se hizo hoy
        self.assertTrue(limpieza.toca_limpiar(datetime(2026, 10, 16, 9, 0)))     # mañana sí

    def test_si_la_pc_prende_tarde_limpia_en_cuanto_prende(self) -> None:
        self.assertTrue(limpieza.toca_limpiar(datetime(2026, 10, 15, 13, 40)))

    def test_un_archivo_roto_no_deja_mudo_al_bot(self) -> None:
        limpieza.ruta_estado().parent.mkdir(parents=True, exist_ok=True)
        limpieza.ruta_estado().write_text("{no es json", encoding="utf-8")
        self.assertEqual(limpieza.menu_fijado(), 0)
        limpieza.anotar(7)
        self.assertEqual([m["id"] for m in limpieza._leer()["mensajes"]], [7])


class ElMenuSeRenuevaCadaMananaTests(unittest.TestCase):
    HOY = datetime(2026, 10, 15, 9, 5)

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        parche = patch.object(
            limpieza, "ruta_estado",
            return_value=Path(self._dir.name) / "bot_mensajes.json",
        )
        parche.start()
        self.addCleanup(parche.stop)

    def _limpiar(self, *, nuevo: int, borra_viejo: bool = True):
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service as ts

        with patch.object(bot, "asegurar_menu_fijado", return_value=nuevo) as asegurar, \
                patch.object(ts, "borrar_mensaje", return_value=borra_viejo) as borrar, \
                patch.object(ts, "desfijar_mensaje") as desfijar:
            bot.limpiar_si_toca(session_factory=None, token="t", chat_id="c", ahora=self.HOY)
        return asegurar, borrar, desfijar

    def test_manda_uno_nuevo_y_borra_el_de_ayer(self) -> None:
        limpieza.recordar_menu(50)
        asegurar, borrar, desfijar = self._limpiar(nuevo=60)
        asegurar.assert_called_once()
        borrar.assert_any_call(50, token="t", chat_id="c")
        desfijar.assert_not_called()

    def test_si_el_de_ayer_ya_no_se_puede_borrar_se_desfija(self) -> None:
        limpieza.recordar_menu(50)
        _, _, desfijar = self._limpiar(nuevo=60, borra_viejo=False)
        desfijar.assert_called_once_with(50, token="t", chat_id="c")

    def test_sin_red_se_queda_el_menu_de_ayer(self) -> None:
        limpieza.recordar_menu(50)
        _, borrar, _ = self._limpiar(nuevo=0)
        self.assertEqual(limpieza.menu_fijado(), 50)
        self.assertNotIn(50, [c.args[0] for c in borrar.call_args_list])

    def test_no_se_renueva_dos_veces_el_mismo_dia(self) -> None:
        limpieza.recordar_menu(50)
        self._limpiar(nuevo=60)
        asegurar, _, _ = self._limpiar(nuevo=70)
        asegurar.assert_not_called()


class ElMenuSeFijaUnaSolaVezTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        parche = patch.object(
            limpieza, "ruta_estado",
            return_value=Path(self._dir.name) / "bot_mensajes.json",
        )
        parche.start()
        self.addCleanup(parche.stop)
        self.factory = lambda: MagicMock(__enter__=lambda s: s, __exit__=lambda *a: False)

    def test_la_primera_vez_lo_manda_y_lo_fija(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        with patch.object(
            telegram_service, "_llamar",
            return_value={"result": {"message_id": 42}},
        ), patch.object(telegram_service, "fijar_mensaje", return_value=True) as fijar:
            mid = bot.asegurar_menu_fijado(
                session_factory=self.factory, token="t", chat_id="c"
            )
        self.assertEqual(mid, 42)
        fijar.assert_called_once()
        self.assertEqual(limpieza.menu_fijado(), 42)

    def test_despues_solo_lo_reescribe(self) -> None:
        """Mandar uno nuevo cada arranque llenaría el chat de menús viejos."""
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        limpieza.recordar_menu(42)
        with patch.object(telegram_service, "editar_mensaje") as editar, \
             patch.object(telegram_service, "_llamar") as llamar, \
             patch.object(telegram_service, "fijar_mensaje") as fijar:
            mid = bot.asegurar_menu_fijado(
                session_factory=self.factory, token="t", chat_id="c"
            )
        self.assertEqual(mid, 42)
        editar.assert_called_once()
        llamar.assert_not_called()
        fijar.assert_not_called()

    def test_si_lo_borraron_a_mano_se_manda_otro(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        limpieza.recordar_menu(42)
        with patch.object(telegram_service, "editar_mensaje", side_effect=OSError("no existe")), \
             patch.object(telegram_service, "_llamar",
                          return_value={"result": {"message_id": 99}}), \
             patch.object(telegram_service, "fijar_mensaje", return_value=True):
            mid = bot.asegurar_menu_fijado(
                session_factory=self.factory, token="t", chat_id="c"
            )
        self.assertEqual(mid, 99)
        self.assertEqual(limpieza.menu_fijado(), 99)


class TocarElMenuNoLoDeshaceTests(unittest.TestCase):
    """Al primer toque, el tablero de arriba se habría convertido en una lista
    de cortes y ya no habría de dónde salir."""

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        parche = patch.object(
            limpieza, "ruta_estado",
            return_value=Path(self._dir.name) / "bot_mensajes.json",
        )
        parche.start()
        self.addCleanup(parche.stop)

    def _tocar(self, message_id: int):
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        toque = {
            "id": "1", "data": "m:cortes",
            "message": {"message_id": message_id, "chat": {"id": "c"}},
        }
        with patch.object(bot, "atender_toque", return_value=("", "Cortes", "{}")), \
             patch.object(telegram_service, "responder_toque"), \
             patch.object(telegram_service, "editar_mensaje") as editar, \
             patch.object(telegram_service, "enviar_mensaje") as enviar:
            bot._atender_toque(toque, session_factory=None, token="t", chat_id="c")
        return editar, enviar

    def test_el_menu_fijado_contesta_en_un_mensaje_nuevo(self) -> None:
        limpieza.recordar_menu(42)
        editar, enviar = self._tocar(42)
        editar.assert_not_called()
        enviar.assert_called_once()

    def test_cualquier_otro_mensaje_se_sigue_reescribiendo(self) -> None:
        """La lista de cortes se actualiza en su lugar, como siempre."""
        limpieza.recordar_menu(42)
        editar, enviar = self._tocar(77)
        editar.assert_called_once()
        enviar.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class ElMenuFijadoNoSeQuedaConLaHoraDeAyerTests(unittest.TestCase):
    """El menú se escribía SOLO al arrancar el bot.

    Su cabecera lleva las cifras del día, así que a media tarde seguía
    diciendo «todavía no se registra ninguna venta». Un tablero fijado que
    miente es peor que no tenerlo (Daniel lo vio en su pantalla, 2026-10-08:
    fijado a las 09:45, leído a las 09:56).
    """

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        parche = patch.object(
            limpieza, "ruta_estado",
            return_value=Path(self._dir.name) / "bot_mensajes.json",
        )
        parche.start()
        self.addCleanup(parche.stop)
        self.factory = lambda: MagicMock(__enter__=lambda s: s, __exit__=lambda *a: False)

    def _refrescar(self, texto="MENU"):
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_menu_service as menu
        from pos_uniformes.services import telegram_service

        with patch.object(menu, "menu_raiz", return_value=(texto, "{}")), \
             patch.object(telegram_service, "editar_mensaje") as editar, \
             patch.object(telegram_service, "_llamar",
                          return_value={"result": {"message_id": 7}}) as llamar, \
             patch.object(telegram_service, "fijar_mensaje"):
            hecho = bot.refrescar_menu_si_toca(
                session_factory=self.factory, token="t", chat_id="c"
            )
        return hecho, editar, llamar

    def test_sin_menu_fijado_no_hay_nada_que_refrescar(self) -> None:
        hecho, editar, _ = self._refrescar()
        self.assertFalse(hecho)
        editar.assert_not_called()

    def test_con_el_tiempo_cumplido_se_reescribe(self) -> None:
        limpieza.recordar_menu(42)
        hecho, editar, _ = self._refrescar("MENU nuevo")
        self.assertTrue(hecho)
        editar.assert_called_once()

    def test_no_se_reescribe_antes_de_tiempo(self) -> None:
        """Cada vuelta del bot son 25 s; refrescar en cada una es gastar."""
        limpieza.recordar_menu(42)
        self._refrescar("MENU nuevo")
        hecho, editar, _ = self._refrescar("MENU más nuevo")
        self.assertFalse(hecho)
        editar.assert_not_called()

    def test_si_no_cambio_nada_no_se_toca_el_mensaje(self) -> None:
        """Telegram contesta «message is not modified» con un ERROR.

        Por ese camino el menú se daba por perdido y se mandaba uno nuevo: en
        una mañana tranquila el chat se habría llenado de tableros.
        """
        limpieza.recordar_menu(42)
        self._refrescar("IGUAL")
        limpieza.anotar_menu_refrescado(ahora=0.0)      # que vuelva a tocar
        hecho, editar, llamar = self._refrescar("IGUAL")
        self.assertTrue(hecho)
        editar.assert_not_called()                      # no se edita…
        llamar.assert_not_called()                      # …ni se manda otro
        self.assertEqual(limpieza.menu_fijado(), 42)

    def test_cambiar_el_texto_si_lo_reescribe(self) -> None:
        limpieza.recordar_menu(42)
        self._refrescar("ANTES")
        limpieza.anotar_menu_refrescado(ahora=0.0)
        hecho, editar, _ = self._refrescar("DESPUES")
        self.assertTrue(hecho)
        editar.assert_called_once()


class LoImportanteSeQuedaDosDiasTests(unittest.TestCase):
    def test_con_conservar_se_apunta_marcado(self) -> None:
        """Alertas, cortes y resúmenes: antes no se apuntaban y no se borraban
        nunca; ahora se quedan dos días (Daniel, 2026-10-15)."""
        from unittest.mock import patch

        from pos_uniformes.services import telegram_limpieza_service as limpieza
        from pos_uniformes.services import telegram_service as ts

        with patch.object(limpieza, "anotar") as anotar:
            ts._anotar_para_barrer({"result": {"message_id": 5}}, conservar=True)
            ts._anotar_para_barrer({"result": {"message_id": 6}})
        self.assertEqual(
            [c.args + tuple(sorted(c.kwargs.items())) for c in anotar.call_args_list],
            [(5, ("conservar", True)), (6, ("conservar", False))],
        )

