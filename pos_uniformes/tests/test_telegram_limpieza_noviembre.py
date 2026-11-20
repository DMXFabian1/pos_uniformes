"""El chat del bot se limpia solo de verdad (Daniel, 2026-11-20: «todavía no
se limpia solo y se siguen acumulando mensajes antiguos»).

Cada prueba es una de las causas que se encontraron:
- lo conservado que salía antes de abrir pasaba del tope de 48 h sin borrarse;
- el aviso «V.I.K.Y fijó…» de cada mañana nunca se apuntaba;
- un timeout al reescribir el menú dejaba el viejo fijado para siempre;
- un barrido sin red daba el día por limpio;
- un archivo que no se pudo leer se pisaba con una lista vacía;
- lo que mandaba un kiosko se apuntaba en otra PC.
Ninguna prueba habla con Telegram.
"""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from pos_uniformes.services import telegram_limpieza_service as limpieza


class _ConArchivo(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        parche = patch.object(
            limpieza, "ruta_estado", return_value=Path(self._dir.name) / "bot_mensajes.json"
        )
        parche.start()
        self.addCleanup(parche.stop)

    def _ids(self) -> list[int]:
        return [int(m["id"]) for m in limpieza._leer()["mensajes"]]

    def _barrer(self, ahora: datetime, resultado="ok") -> list[int]:
        llamados: list[int] = []

        def borrar(mid):
            llamados.append(mid)
            return resultado(mid) if callable(resultado) else resultado

        limpieza.barrer(borrar=borrar, ahora=ahora)
        return llamados


class LoConservadoViveTreintaYSeisHorasTests(_ConArchivo):
    LUNES_8 = datetime(2026, 11, 16, 8, 0)     # antes de abrir (9:00)

    def test_una_alerta_de_antes_de_abrir_se_borra_antes_del_tope(self) -> None:
        """Antes: llegaba a la limpieza del miércoles con 49 h y se olvidaba."""
        limpieza.anotar(1, conservar=True, ts=self.LUNES_8.timestamp())
        self.assertEqual(self._barrer(self.LUNES_8 + timedelta(hours=35)), [])
        self.assertEqual(self._barrer(self.LUNES_8 + timedelta(hours=36, minutes=1)), [1])
        self.assertEqual(self._ids(), [])

    def test_se_ve_hoy_y_manana(self) -> None:
        tarde = datetime(2026, 11, 16, 18, 0)
        limpieza.anotar(1, conservar=True, ts=tarde.timestamp())
        self.assertEqual(self._barrer(datetime(2026, 11, 17, 21, 0)), [])   # martes en la noche
        self.assertEqual(self._barrer(datetime(2026, 11, 18, 6, 1)), [1])   # miércoles temprano


class ElBarridoEsEnCadaVueltaTests(_ConArchivo):
    def test_lo_de_ayer_se_va_al_abrir_sin_esperar_a_nada_mas(self) -> None:
        limpieza.anotar(5, ts=datetime(2026, 11, 19, 20, 0).timestamp())
        self.assertEqual(self._barrer(datetime(2026, 11, 20, 8, 59)), [])
        self.assertEqual(self._barrer(datetime(2026, 11, 20, 9, 0)), [5])

    def test_lo_de_hoy_despues_de_abrir_se_queda_hasta_manana(self) -> None:
        limpieza.anotar(5, ts=datetime(2026, 11, 20, 10, 0).timestamp())
        self.assertEqual(self._barrer(datetime(2026, 11, 20, 23, 0)), [])
        self.assertEqual(self._barrer(datetime(2026, 11, 21, 9, 0)), [5])

    def test_el_menu_fijado_nunca_se_barre(self) -> None:
        limpieza.anotar(5, ts=datetime(2026, 11, 18, 10, 0).timestamp())
        limpieza.recordar_menu(5)
        self.assertEqual(self._barrer(datetime(2026, 11, 20, 9, 0)), [])


class SinRedNoSePierdeNadaTests(_ConArchivo):
    AHORA = datetime(2026, 11, 20, 9, 30)

    def test_sin_red_todo_se_queda_y_se_espera_unos_minutos(self) -> None:
        for mid in (1, 2, 3):
            limpieza.anotar(mid, ts=datetime(2026, 11, 19, 12, 0).timestamp())
        self.assertEqual(self._barrer(self.AHORA, "red"), [1])        # se para al primero
        self.assertEqual(self._ids(), [1, 2, 3])
        self.assertEqual(self._barrer(self.AHORA + timedelta(minutes=2)), [])
        self.assertEqual(self._barrer(self.AHORA + timedelta(minutes=6)), [1, 2, 3])
        self.assertEqual(self._ids(), [])

    def test_una_excepcion_cuenta_como_sin_red(self) -> None:
        limpieza.anotar(1, ts=datetime(2026, 11, 19, 12, 0).timestamp())

        def truena(_):
            raise OSError("sin red")

        limpieza.barrer(borrar=truena, ahora=self.AHORA)
        self.assertEqual(self._ids(), [1])

    def test_si_telegram_dice_que_no_se_reintenta_en_una_hora(self) -> None:
        limpieza.anotar(1, ts=datetime(2026, 11, 19, 12, 0).timestamp())
        self.assertEqual(self._barrer(self.AHORA, "no"), [1])
        self.assertEqual(self._barrer(self.AHORA + timedelta(minutes=30)), [])
        self.assertEqual(self._barrer(self.AHORA + timedelta(minutes=61)), [1])


class LaListaNoSePierdeTests(_ConArchivo):
    def test_si_no_se_pudo_leer_no_se_pisa(self) -> None:
        limpieza.anotar(1)
        limpieza.anotar(2)
        with patch.object(Path, "read_text", side_effect=PermissionError("antivirus")), \
                patch.object(limpieza.time, "sleep"):
            limpieza.anotar(3)                    # no se pudo: no escribe nada
        self.assertEqual(self._ids(), [1, 2])

    def test_un_archivo_roto_se_guarda_aparte(self) -> None:
        ruta = limpieza.ruta_estado()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("{roto", encoding="utf-8")
        limpieza.anotar(7)
        self.assertEqual(self._ids(), [7])
        self.assertTrue(ruta.with_suffix(".roto.json").exists())

    def test_lo_que_se_anota_mientras_se_barre_no_se_pierde(self) -> None:
        limpieza.anotar(1, ts=datetime(2026, 11, 19, 12, 0).timestamp())

        def borrar(mid):
            limpieza.anotar(99)                   # otro aviso sale a media barrida
            return "ok"

        limpieza.barrer(borrar=borrar, ahora=datetime(2026, 11, 20, 9, 30))
        self.assertEqual(self._ids(), [99])

    def test_un_candado_abandonado_no_traba(self) -> None:
        import os

        candado = limpieza.ruta_estado().with_suffix(".lock")
        candado.parent.mkdir(parents=True, exist_ok=True)
        candado.write_text("", encoding="utf-8")
        viejo = time.time() - 120
        os.utime(candado, (viejo, viejo))
        inicio = time.monotonic()
        limpieza.anotar(1)
        self.assertLess(time.monotonic() - inicio, 1.0)
        self.assertEqual(self._ids(), [1])
        self.assertFalse(candado.exists())


class ElAvisoDeFijadoSeBorraTests(_ConArchivo):
    def _aviso(self) -> dict:
        return {"message_id": 77, "date": int(time.time()), "pinned_message": {"message_id": 76}}

    def test_se_borra_en_cuanto_llega(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        with patch.object(telegram_service, "borrar_con_motivo", return_value="ok") as borrar:
            bot._quitar_aviso_de_servicio(self._aviso(), token="t", chat_id="c")
        borrar.assert_called_once_with(77, token="t", chat_id="c")
        self.assertEqual(self._ids(), [])

    def test_sin_red_se_apunta_para_el_barrido(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        with patch.object(telegram_service, "borrar_con_motivo", return_value="red"):
            bot._quitar_aviso_de_servicio(self._aviso(), token="t", chat_id="c")
        self.assertEqual(self._ids(), [77])

    def test_otros_mensajes_de_servicio_no_se_tocan(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        with patch.object(telegram_service, "borrar_con_motivo") as borrar:
            bot._quitar_aviso_de_servicio({"message_id": 5, "new_chat_title": "x"}, token="t", chat_id="c")
        borrar.assert_not_called()


class ElMenuDeLaMananaTests(_ConArchivo):
    HOY = datetime(2026, 11, 20, 9, 5)

    def test_sin_red_no_se_da_el_dia_por_hecho(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        limpieza.recordar_menu(50)
        with patch.object(bot, "asegurar_menu_fijado", return_value=0), \
                patch.object(telegram_service, "borrar_con_motivo", return_value="red"):
            bot.limpiar_si_toca(session_factory=None, token="t", chat_id="c", ahora=self.HOY)
        self.assertTrue(limpieza.toca_limpiar(self.HOY + timedelta(minutes=1)))
        self.assertEqual(limpieza.menu_fijado(), 50)

    def test_el_menu_viejo_sin_red_se_desfija_y_se_apunta(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        limpieza.recordar_menu(50)
        with patch.object(bot, "asegurar_menu_fijado", return_value=60), \
                patch.object(telegram_service, "borrar_con_motivo", return_value="red"), \
                patch.object(telegram_service, "desfijar_mensaje") as desfijar:
            bot.limpiar_si_toca(session_factory=None, token="t", chat_id="c", ahora=self.HOY)
        desfijar.assert_called_once_with(50, token="t", chat_id="c")
        self.assertIn(50, self._ids())
        self.assertFalse(limpieza.toca_limpiar(self.HOY + timedelta(minutes=1)))


class BorrarConMotivoTests(unittest.TestCase):
    def _motivo(self, efecto) -> str:
        from pos_uniformes.services import telegram_service

        with patch.object(telegram_service, "_llamar", side_effect=efecto):
            return telegram_service.borrar_con_motivo(1, token="t", chat_id="c")

    def test_telegram_dice_que_no(self) -> None:
        self.assertEqual(
            # «message to delete not found» ya cuenta como borrado (2026-11-20).
            self._motivo(RuntimeError("Telegram respondió: Bad Request: message can't be deleted")), "no"
        )

    def test_sin_red(self) -> None:
        self.assertEqual(self._motivo(OSError("timed out")), "red")

    def test_se_borro(self) -> None:
        self.assertEqual(self._motivo(lambda *a, **k: {"ok": True}), "ok")


class ElKioskoMandaPorLaColaTests(unittest.TestCase):
    """El kiosko apuntaba sus mensajes en su propia PC y el bot nunca los barría."""

    def test_en_el_kiosko_va_a_la_cola_y_no_a_telegram(self) -> None:
        import sys

        from pos_uniformes.services import alertas_service, telegram_service

        sesion = MagicMock()
        fabrica = MagicMock()
        fabrica.return_value.__enter__.return_value = sesion
        with patch.object(sys, "frozen", True, create=True), \
                patch("pos_uniformes.database.connection.get_session", fabrica), \
                patch.object(alertas_service, "encolar", return_value=True) as encolar, \
                patch.object(telegram_service, "_llamar") as llamar:
            n = telegram_service.enviar_mensaje("Préstamo de Fanny", botones="{}")
        self.assertEqual(n, 1)
        encolar.assert_called_once_with(sesion, "Préstamo de Fanny", "{}")
        llamar.assert_not_called()

    def test_si_la_cola_no_responde_quien_llama_sigue_su_plan_b(self) -> None:
        import sys

        from pos_uniformes.services import alertas_service, telegram_service

        fabrica = MagicMock()
        with patch.object(sys, "frozen", True, create=True), \
                patch("pos_uniformes.database.connection.get_session", fabrica), \
                patch.object(alertas_service, "encolar", return_value=False):
            with self.assertRaises(RuntimeError):
                telegram_service.enviar_mensaje("Acuse")

    def test_en_la_pc_principal_sigue_directo(self) -> None:
        from pos_uniformes.services import telegram_service

        with patch.object(telegram_service, "_es_kiosko", return_value=False), \
                patch.object(telegram_service, "_llamar", return_value={"result": {"message_id": 0}}) as llamar:
            telegram_service.enviar_mensaje("Hola", token="t", chat_id="c")
        llamar.assert_called_once()




class UnaSolaPantallaTests(_ConArchivo):
    """Daniel (2026-11-20): «una sola pantalla». Las consultas reescriben la
    misma pantalla de trabajo y el comando se borra al contestar."""

    def _mostrar(self, texto="Caja", *, nuevo_id=90, editar=None, nueva=False):
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        with patch.object(telegram_service, "editar_mensaje", side_effect=editar) as ed, \
                patch.object(telegram_service, "enviar_y_dar_id", return_value=nuevo_id) as env, \
                patch.object(telegram_service, "enviar_mensaje") as largo, \
                patch.object(telegram_service, "borrar_con_motivo", return_value="ok") as borrar:
            mid = bot.mostrar_en_pantalla(texto, "", token="t", chat_id="c", nueva=nueva)
        return mid, ed, env, largo, borrar

    def test_la_primera_consulta_manda_y_la_segunda_reescribe(self) -> None:
        mid, _, env, _, _ = self._mostrar("Caja")
        self.assertEqual(mid, 90)
        env.assert_called_once()
        mid, ed, env, _, _ = self._mostrar("Pagos")
        self.assertEqual(mid, 90)
        env.assert_not_called()
        self.assertEqual(ed.call_args.args[:2], (90, "Pagos"))

    def test_si_salio_otro_mensaje_abajo_manda_una_nueva_y_quita_la_vieja(self) -> None:
        self._mostrar("Caja")
        limpieza.tapar_pantalla(95)                # llegó una alerta
        mid, ed, env, _, borrar = self._mostrar("Pagos", nuevo_id=96)
        self.assertEqual(mid, 96)
        ed.assert_not_called()
        borrar.assert_called_once_with(90, token="t", chat_id="c")
        self.assertEqual(limpieza.pantalla(), (96, limpieza.pantalla()[1], False))

    def test_la_pantalla_de_ayer_no_se_reescribe(self) -> None:
        limpieza.recordar_pantalla(80, "2026-01-01")
        mid, ed, env, _, _ = self._mostrar("Caja")
        ed.assert_not_called()
        self.assertEqual(mid, 90)

    def test_si_la_borraron_a_mano_manda_otra(self) -> None:
        self._mostrar("Caja")
        no_existe = RuntimeError("Telegram respondió: Bad Request: message to edit not found")
        mid, _, env, _, _ = self._mostrar("Pagos", nuevo_id=91, editar=no_existe)
        self.assertEqual(mid, 91)

    def test_sin_red_no_manda_otra(self) -> None:
        self._mostrar("Caja")
        with self.assertRaises(OSError):
            self._mostrar("Pagos", editar=OSError("timeout"))
        self.assertEqual(limpieza.pantalla()[0], 90)

    def test_lo_que_no_cabe_sale_partido_como_siempre(self) -> None:
        mid, ed, env, largo, _ = self._mostrar("x" * 5000)
        largo.assert_called_once()
        env.assert_not_called()
        self.assertEqual(mid, 0)

    def test_un_boton_de_dinero_de_ayer_nace_en_un_mensaje_nuevo(self) -> None:
        self._mostrar("Caja")
        mid, ed, env, _, _ = self._mostrar("¿Registro este pago?", nuevo_id=92, nueva=True)
        ed.assert_not_called()
        self.assertEqual(mid, 92)

    def test_el_comando_de_daniel_se_borra_y_sale_de_la_lista(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        limpieza.anotar(55)
        with patch.object(telegram_service, "borrar_con_motivo", return_value="ok") as borrar:
            bot._quitar_comando({"message_id": 55}, token="t", chat_id="c")
        borrar.assert_called_once_with(55, token="t", chat_id="c")
        self.assertEqual(self._ids(), [])

    def test_si_no_se_pudo_borrar_el_comando_se_queda_para_el_barrido(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot
        from pos_uniformes.services import telegram_service

        limpieza.anotar(55)
        with patch.object(telegram_service, "borrar_con_motivo", return_value="red"):
            bot._quitar_comando({"message_id": 55}, token="t", chat_id="c")
        self.assertEqual(self._ids(), [55])

    def test_mandar_cualquier_aviso_tapa_la_pantalla(self) -> None:
        from pos_uniformes.services import telegram_service

        limpieza.recordar_pantalla(90, "2026-11-20")
        telegram_service._anotar_para_barrer(respuesta={"result": {"message_id": 91}})
        self.assertTrue(limpieza.pantalla()[2])


if __name__ == "__main__":
    unittest.main()
