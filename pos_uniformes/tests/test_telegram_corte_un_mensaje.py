"""El corte de la tarde vive en UN mensaje (Daniel, 2026-11-20: «Un mensaje
que se actualiza»).

Antes la propuesta, el «⏰ sigue pendiente», el corte hecho y la alerta del
corte (que llegaba dos veces) quedaban como mensajes sueltos con botones
vivos. Ahora: la propuesta guarda su id; el recordatorio la reemplaza; el
corte hecho la reescribe o la quita; y el corte del celular no se avisa dos
veces. Nada de esto manda mensajes de verdad.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from pos_uniformes.services import corte_propuesta_service as prop
from pos_uniformes.services import telegram_bot_service as bot
from pos_uniformes.services import telegram_limpieza_service as limpieza
from pos_uniformes.services import telegram_service

HOY = date(2026, 11, 20)


class _Hoy(date):
    """Reloj fijo: las pruebas no dependen de la hora real (revisión 2026-11-20)."""

    @classmethod
    def today(cls):
        return HOY


class _Ahora(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 11, 20, 18, 0, tzinfo=tz)


class _ConPropuesta(unittest.TestCase):
    def setUp(self) -> None:
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        for p in (
            patch.object(prop, "ruta_estado", return_value=Path(d.name) / "corte_propuesto.json"),
            patch.object(limpieza, "ruta_estado", return_value=Path(d.name) / "bot_mensajes.json"),
            patch.object(prop, "date", _Hoy),
        ):
            p.start()
            self.addCleanup(p.stop)


class PropuestaRecuerdaSuMensajeTests(_ConPropuesta):
    def test_guarda_y_lee_el_id(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        self.assertEqual(prop.leer().message_id, 501)
        self.assertEqual(prop.mensaje_de_hoy(HOY), 501)
        self.assertEqual(prop.mensaje_de_hoy(date(2026, 11, 21)), 0)

    def test_el_recordatorio_reemplaza_el_id(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        prop.anotar_recordatorio(777)
        p = prop.leer()
        self.assertTrue(p.recordado)
        self.assertEqual(p.message_id, 777)
        prop.anotar_recordatorio(0)   # sin id (se fue a la cola): se queda el anterior
        self.assertEqual(prop.leer().message_id, 777)

    def test_nocorte_no_pierde_el_id(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        prop.cancelar(HOY)
        self.assertEqual(prop.leer().message_id, 501)

    def test_archivo_viejo_sin_id(self) -> None:
        prop.ruta_estado().write_text(
            '{"fecha": "2026-11-20", "momento": "2026-11-20T17:30:00", "recordado": false, "cancelado": false}',
            encoding="utf-8",
        )
        self.assertEqual(prop.leer().message_id, 0)

    def test_retirar_borra_y_olvida(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        with patch.object(telegram_service, "borrar_con_motivo", return_value="ok") as borrar:
            self.assertTrue(prop.retirar_mensaje(HOY))
        borrar.assert_called_once_with(501)
        self.assertEqual(prop.leer().message_id, 0)

    def test_retirar_sin_red_lo_deja_para_otra_vez(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        with patch.object(telegram_service, "borrar_con_motivo", return_value="red"):
            self.assertFalse(prop.retirar_mensaje(HOY))
        self.assertEqual(prop.leer().message_id, 501)

    def test_no_retira_el_que_se_esta_reescribiendo(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        with patch.object(telegram_service, "borrar_con_motivo") as borrar:
            self.assertFalse(prop.retirar_mensaje(HOY, salvo=501))
        borrar.assert_not_called()

    def test_la_de_ayer_no_se_toca(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 19, 17, 30), message_id=400)
        with patch.object(telegram_service, "borrar_con_motivo") as borrar:
            self.assertFalse(prop.retirar_mensaje(HOY))
        borrar.assert_not_called()


class RecordatorioReemplazaTests(_ConPropuesta):
    def test_sale_nuevo_y_quita_la_propuesta(self) -> None:
        from contextlib import contextmanager

        from pos_uniformes.scripts import corte_automatico as script
        from pos_uniformes.services import corte_caja_service, corte_remoto_service

        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)

        @contextmanager
        def _sesion():
            yield MagicMock()

        with patch("pos_uniformes.database.connection.get_session", _sesion), \
             patch.object(corte_caja_service, "ultimo_corte", return_value=None), \
             patch.object(prop, "toca_recordar", return_value=True), \
             patch.object(corte_remoto_service, "propuesta_de_corte", return_value=("¿Corte?", "{}")), \
             patch.object(script, "datetime", _Ahora), \
             patch.object(script, "_mandar_y_dar_id", return_value=777) as mandar, \
             patch.object(telegram_service, "borrar_con_motivo", return_value="ok") as borrar:
            self.assertEqual(script._recordar(), 0)
        self.assertIn("⏰ SIGUE PENDIENTE", mandar.call_args.args[0])   # encabezado (2026-11-20)
        borrar.assert_called_once_with(501)
        self.assertEqual(prop.leer().message_id, 777)
        self.assertTrue(prop.leer().recordado)


class SinAlertaDuplicadaTests(unittest.TestCase):
    def test_el_corte_del_celular_no_encola_otra_alerta(self) -> None:
        import inspect

        from pos_uniformes.services import corte_remoto_service

        fuente = inspect.getsource(corte_remoto_service.hacer_corte_y_avisar)
        self.assertIn("avisar=False", fuente)

    def test_cerrar_corte_con_avisar_false_no_llama_al_aviso(self) -> None:
        import inspect

        from pos_uniformes.services import corte_caja_service

        fuente = inspect.getsource(corte_caja_service.cerrar_corte)
        self.assertIn("if avisar:", fuente)
        self.assertIn("avisar", inspect.signature(corte_caja_service.cerrar_corte_automatico).parameters)


class CorteHechoDesdeUnBotonTests(_ConPropuesta):
    def _toque(self, tocado: int, *, es_el_menu: bool = False):
        with patch.object(telegram_service, "editar_mensaje") as editar, \
             patch.object(telegram_service, "enviar_mensaje") as enviar, \
             patch.object(telegram_service, "borrar_con_motivo", return_value="ok") as borrar:
            bot._corte_hecho_en_un_mensaje(
                tocado, "✅ Corte hecho", es_el_menu=es_el_menu, token="t", chat_id="1"
            )
        return editar, enviar, borrar

    def test_en_la_propuesta_se_reescribe_ahi_mismo(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        editar, enviar, borrar = self._toque(501)
        editar.assert_called_once()
        self.assertEqual(editar.call_args.args[0], 501)
        self.assertFalse(editar.call_args.kwargs.get("botones"))
        enviar.assert_not_called()
        borrar.assert_not_called()

    def test_desde_la_pantalla_sale_uno_que_se_conserva(self) -> None:
        prop.anotar_propuesta(datetime(2026, 11, 20, 17, 30), message_id=501)
        limpieza.recordar_pantalla(900, HOY.isoformat())
        editar, enviar, borrar = self._toque(900)
        enviar.assert_called_once()
        self.assertTrue(enviar.call_args.kwargs.get("conservar"))
        borrados = sorted(c.args[0] for c in borrar.call_args_list)
        self.assertEqual(borrados, [501, 900])     # la propuesta y la pantalla vieja
        self.assertEqual(limpieza.pantalla()[0], 0)
        self.assertEqual(prop.leer().message_id, 0)

    def test_desde_el_menu_el_menu_no_se_borra(self) -> None:
        editar, enviar, borrar = self._toque(10, es_el_menu=True)
        enviar.assert_called_once()
        borrar.assert_not_called()
        editar.assert_not_called()

    def test_sin_red_el_tocado_dice_el_resultado(self) -> None:
        with patch.object(telegram_service, "editar_mensaje") as editar, \
             patch.object(telegram_service, "enviar_mensaje", side_effect=OSError("sin red")), \
             patch.object(telegram_service, "borrar_con_motivo") as borrar:
            bot._corte_hecho_en_un_mensaje(900, "✅ Corte hecho", es_el_menu=False, token="t", chat_id="1")
        editar.assert_called_once()
        borrar.assert_not_called()

    def test_el_toque_cc_hecho_pasa_por_aqui(self) -> None:
        toque = {"id": "q", "data": "cc:si", "message": {"message_id": 900, "chat": {"id": 1},
                                                          "date": int(datetime.now().timestamp())}}
        with patch.object(bot, "atender_toque", return_value=("Corte hecho", "✅ Corte hecho", "")), \
             patch.object(telegram_service, "responder_toque"), \
             patch.object(bot, "_corte_hecho_en_un_mensaje") as un_mensaje, \
             patch.object(telegram_service, "editar_mensaje") as editar:
            bot._atender_toque(toque, session_factory=MagicMock(), token="t", chat_id="1")
        un_mensaje.assert_called_once()
        editar.assert_not_called()


class CorteEscritoTests(_ConPropuesta):
    def test_es_comando_de_corte(self) -> None:
        self.assertTrue(bot._es_comando_de_corte("/corte"))
        self.assertTrue(bot._es_comando_de_corte("/corte retiro 500"))
        self.assertFalse(bot._es_comando_de_corte("/caja"))
        self.assertFalse(bot._es_comando_de_corte("hola"))

    def _corte(self, hecho: bool):
        from contextlib import contextmanager

        from pos_uniformes.services import corte_remoto_service
        from pos_uniformes.services.corte_remoto_service import ResultadoCorte

        @contextmanager
        def _sesion():
            yield MagicMock()

        with patch.object(corte_remoto_service, "hacer_corte_y_avisar",
                          return_value=ResultadoCorte(hecho, "🧾 corte")), \
             patch.object(bot, "_retirar_propuesta_del_corte") as retirar:
            bot.atender_texto("/corte", session_factory=_sesion)
        return retirar

    def test_hecho_quita_la_propuesta(self) -> None:
        self._corte(True).assert_called_once()

    def test_no_hecho_la_deja(self) -> None:
        self._corte(False).assert_not_called()


if __name__ == "__main__":
    unittest.main()
