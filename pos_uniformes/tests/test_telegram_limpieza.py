"""El chat se limpia solo: un menú fijado arriba y lo demás se va a las 24 h.

Daniel (2026-10-08): «me gustaría que quede un menú fijado, y lo demás lo borre
24 horas después».

Dos límites de Telegram mandan sobre el diseño, y los dos están probados aquí:
el bot solo borra lo suyo, y pasadas 48 horas ya no borra nada.
"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pos_uniformes.services import telegram_limpieza_service as limpieza

HORA = 3600.0


class LaListaDeMensajesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        parche = patch.object(
            limpieza, "ruta_estado",
            return_value=Path(self._dir.name) / "bot_mensajes.json",
        )
        parche.start()
        self.addCleanup(parche.stop)

    def _anotar(self, mid: int, horas: float) -> None:
        with patch.object(time, "time", return_value=time.time() - horas * HORA):
            limpieza.anotar(mid)

    def test_un_mensaje_de_hoy_no_se_toca(self) -> None:
        self._anotar(10, horas=3)
        borrados = []
        self.assertEqual(limpieza.barrer(borrar=lambda m: borrados.append(m) or True), 0)
        self.assertEqual(borrados, [])

    def test_a_las_24_horas_se_borra(self) -> None:
        self._anotar(10, horas=25)
        borrados = []
        self.assertEqual(limpieza.barrer(borrar=lambda m: borrados.append(m) or True), 1)
        self.assertEqual(borrados, [10])

    def test_lo_borrado_no_se_vuelve_a_pedir(self) -> None:
        self._anotar(10, horas=25)
        limpieza.barrer(borrar=lambda m: True)
        borrados = []
        limpieza.barrer(borrar=lambda m: borrados.append(m) or True)
        self.assertEqual(borrados, [])

    def test_pasadas_48_horas_se_olvida_en_vez_de_insistir(self) -> None:
        """Telegram ya no deja borrarlo. Reintentar cada 15 minutos hasta el
        fin de los tiempos sería gastar una llamada para que diga que no."""
        self._anotar(10, horas=50)
        borrados = []
        limpieza.barrer(borrar=lambda m: borrados.append(m) or True)
        self.assertEqual(borrados, [])
        self.assertEqual(limpieza._leer()["mensajes"], [])

    def test_si_el_borrado_falla_se_reintenta_luego(self) -> None:
        self._anotar(10, horas=25)
        limpieza.barrer(borrar=lambda m: False)
        self.assertEqual([m["id"] for m in limpieza._leer()["mensajes"]], [10])

    def test_un_error_de_red_tampoco_pierde_el_mensaje(self) -> None:
        self._anotar(10, horas=25)

        def truena(_):
            raise OSError("sin red")

        limpieza.barrer(borrar=truena)
        self.assertEqual([m["id"] for m in limpieza._leer()["mensajes"]], [10])

    def test_el_menu_fijado_no_se_barre_nunca(self) -> None:
        """Es lo único que debe seguir ahí mañana.

        Se arma el archivo a mano con el menú TAMBIÉN en la lista de mensajes.
        Es el caso que de verdad puede pasar —un archivo escrito antes de que
        existiera el menú fijado, o editado a mano— y es el único que ejercita
        el guardia del barrido: por el camino normal, `recordar_menu` ya lo
        saca de la lista, así que probarlo por ahí no probaba nada.
        """
        import json

        limpieza.ruta_estado().parent.mkdir(parents=True, exist_ok=True)
        limpieza.ruta_estado().write_text(json.dumps({
            "menu_id": 10,
            "mensajes": [{"id": 10, "ts": time.time() - 30 * HORA},
                         {"id": 11, "ts": time.time() - 30 * HORA}],
            "ultimo_barrido": 0.0,
        }), encoding="utf-8")

        borrados = []
        limpieza.barrer(borrar=lambda m: borrados.append(m) or True)
        self.assertEqual(borrados, [11])          # el otro sí, el menú no
        self.assertEqual(limpieza.menu_fijado(), 10)

    def test_el_menu_no_se_apunta_aunque_pase_por_el_mismo_camino(self) -> None:
        limpieza.recordar_menu(10)
        limpieza.anotar(10)
        self.assertEqual(limpieza._leer()["mensajes"], [])

    def test_no_se_barre_en_cada_vuelta_del_bot(self) -> None:
        """La vuelta es de 25 s y borrar es una llamada por mensaje."""
        self.assertTrue(limpieza.toca_barrer())
        limpieza.barrer(borrar=lambda m: True)
        self.assertFalse(limpieza.toca_barrer())
        self.assertTrue(limpieza.toca_barrer(ahora=time.time() + 16 * 60))

    def test_un_archivo_roto_no_deja_mudo_al_bot(self) -> None:
        limpieza.ruta_estado().parent.mkdir(parents=True, exist_ok=True)
        limpieza.ruta_estado().write_text("{no es json", encoding="utf-8")
        self.assertEqual(limpieza.menu_fijado(), 0)
        limpieza.anotar(7)
        self.assertEqual([m["id"] for m in limpieza._leer()["mensajes"]], [7])


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
