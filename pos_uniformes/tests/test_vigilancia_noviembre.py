"""Auditoría del bot 2026-11-07, sección 6: lo que nadie vigilaba."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pos_uniformes.services import alertas_service as al
from pos_uniformes.services import latido_externo_service as lat
from pos_uniformes.services import telegram_pulso_service as pul

#: La de verdad: conftest la apaga para las demás pruebas del vigilante.
_RESUMEN_QUE_NO_SALIO = al.Vigilante._resumen_que_no_salio


def _trabajo(id_, minuto, tipo="TICKET"):
    return SimpleNamespace(id=id_, tipo=SimpleNamespace(value=tipo),
                           created_at=datetime(2026, 11, 7, 12, minuto, tzinfo=timezone.utc).astimezone())


class ImpresionAtoradaTests(unittest.TestCase):
    """Los tickets se quedaban en la cola y la empleada creía que salieron;
    solo se veía abriendo /pulso."""

    def _revisar(self, v, atorados, hora=13):
        with patch("pos_uniformes.services.trabajos_service.esperando_impresion", return_value=atorados):
            return v._impresion_atorada(MagicMock(), datetime(2026, 11, 7, hora, 0))

    def test_avisa_una_vez_y_dice_cuando_se_destapa(self):
        v = al.Vigilante()
        primero = self._revisar(v, [_trabajo(5, 10), _trabajo(6, 20, "ETIQUETA")])
        self.assertEqual(len(primero), 1)
        self.assertIn("No está saliendo el papel", primero[0])
        self.assertIn("1 etiqueta, 1 ticket", primero[0])
        self.assertEqual(self._revisar(v, [_trabajo(5, 10), _trabajo(7, 30)]), [])     # mismo atorón
        self.assertEqual(self._revisar(v, []), ["✅ Ya salió lo que estaba atorado en la cola de impresión."])
        self.assertEqual(self._revisar(v, []), [])

    def test_lo_avisado_sobrevive_al_reinicio(self):
        self._revisar(al.Vigilante(), [_trabajo(5, 10)])
        self.assertEqual(self._revisar(al.Vigilante(), [_trabajo(5, 10)]), [])

    def test_base_sin_tabla_de_trabajos_no_es_error(self):
        sesion = MagicMock()
        with patch("pos_uniformes.services.trabajos_service.esperando_impresion",
                   side_effect=Exception("(sqlite3.OperationalError) no such table: trabajo")):
            self.assertEqual(al.Vigilante()._impresion_atorada(sesion, datetime(2026, 11, 7, 13, 0)), [])


class ResumenQueNoSalioTests(unittest.TestCase):
    def _revisar(self, v, hora, minuto, enviado):
        with patch("pos_uniformes.scripts.resumen_diario_telegram.resumen_ya_enviado", return_value=enviado), \
                patch("pos_uniformes.scripts.resumen_diario_telegram.anotar_resumen_enviado") as anotar, \
                patch("pos_uniformes.services.resumen_diario_service.recolectar"), \
                patch("pos_uniformes.services.resumen_diario_service.formatear", return_value="📒 RESUMEN"), \
                patch.object(pul, "texto_salud", return_value="🩺 SALUD"):
            # sábado 07/11: cierre 18:00, resumen 17:45 → se revisa desde las 19:25
            r = _RESUMEN_QUE_NO_SALIO(v, MagicMock(), datetime(2026, 11, 7, hora, minuto))
        return r, anotar

    def test_antes_de_la_hora_no_hace_nada(self):
        r, anotar = self._revisar(al.Vigilante(), 19, 0, enviado=False)
        self.assertEqual(r, [])
        anotar.assert_not_called()

    def test_si_no_salio_lo_manda_el_bot_una_vez(self):
        v = al.Vigilante()
        r, anotar = self._revisar(v, 19, 30, enviado=False)
        self.assertEqual(len(r), 1)
        self.assertIn("no salió", r[0])
        self.assertIn("📒 RESUMEN", r[0])
        self.assertIn("🩺 SALUD", r[0])
        anotar.assert_called_once()
        self.assertEqual(self._revisar(v, 20, 0, enviado=False)[0], [])

    def test_si_salio_calla(self):
        r, anotar = self._revisar(al.Vigilante(), 19, 30, enviado=True)
        self.assertEqual(r, [])
        anotar.assert_not_called()


class SaludTests(unittest.TestCase):
    def _salud(self, pantallas, impresion, respaldo):
        with patch.object(pul, "_pantallas", return_value=pantallas), \
                patch.object(pul, "_impresion", return_value=impresion), \
                patch.object(pul, "_respaldo", return_value=respaldo):
            return pul.texto_salud(MagicMock(), ahora=datetime(2026, 11, 7, 17, 45))

    def test_todo_bien_una_linea(self):
        t = self._salud(["✅ Pantallas: 3 prendidas"], ["✅ Impresión al día"], ["✅ Respaldo de anoche"])
        self.assertEqual(t, "🩺 SALUD\n✅ Todo en pie: pantallas, impresión y respaldo.")

    def test_solo_lo_que_esta_mal_con_su_explicacion(self):
        t = self._salud(["⚠️ Pantallas: 2 de 3 · apagada: Caja 2"],
                        ["⚠️ Sin imprimir: 2 ticket", "   Prende el Servidor de impresión"],
                        ["✅ Respaldo de anoche"])
        self.assertIn("Caja 2", t)
        self.assertIn("Prende el Servidor", t)
        self.assertNotIn("Respaldo", t)

    def test_lo_que_no_se_pudo_leer_cuenta(self):
        with patch.object(pul, "_pantallas", side_effect=RuntimeError("x")), \
                patch.object(pul, "_impresion", return_value=["✅ ok"]), \
                patch.object(pul, "_respaldo", return_value=["✅ ok"]):
            t = pul.texto_salud(MagicMock())
        self.assertIn("no se pudo leer", t)


class LatidoExternoTests(unittest.TestCase):
    """Si la PC servidor se apaga, quien avisa tiene que estar afuera."""

    def setUp(self):
        lat._estado.update(ultimo_intento=0.0, ultimo_ok=0.0, ultimo_error="")

    def test_sin_direccion_no_hace_nada_y_pulso_lo_dice(self):
        with patch.object(lat, "url_configurada", return_value=""):
            self.assertFalse(lat.latir(1000.0, en_hilo=False, enviar=MagicMock()))
            self.assertIn("Nadie vigila desde fuera", lat.texto_estado())

    def test_late_cada_cinco_minutos(self):
        enviar = MagicMock()
        with patch.object(lat, "url_configurada", return_value="https://hc-ping.com/abcd-1234-efgh"):
            self.assertTrue(lat.latir(1000.0, en_hilo=False, enviar=enviar))
            self.assertFalse(lat.latir(1100.0, en_hilo=False, enviar=enviar))
            self.assertTrue(lat.latir(1000.0 + 301, en_hilo=False, enviar=enviar))
        self.assertEqual(enviar.call_count, 2)

    def test_sin_internet_no_truena_y_se_ve_en_pulso(self):
        with patch.object(lat, "url_configurada", return_value="https://hc-ping.com/abcd-1234-efgh"):
            lat.latir(1000.0, en_hilo=False, enviar=MagicMock(side_effect=OSError("sin red")))
            self.assertIn("no está saliendo", lat.texto_estado())

    def test_solo_direcciones_de_healthchecks(self):
        self.assertTrue(lat.es_url_valida("https://hc-ping.com/1234abcd-5678"))
        self.assertFalse(lat.es_url_valida("http://hc-ping.com/1234abcd-5678"))
        self.assertFalse(lat.es_url_valida("https://evil.com/hc-ping.com/1234abcd"))
        self.assertFalse(lat.es_url_valida("https://hc-ping.com/"))

    def test_guardar_y_quitar(self):
        with patch.object(lat, "_escribir") as escribir, patch.object(lat, "_mandar") as mandar:
            r = lat.guardar_url("https://hc-ping.com/1234abcd-5678")
            self.assertIn("activa", r)
            escribir.assert_called_with("https://hc-ping.com/1234abcd-5678")
            mandar.assert_called_once()
            self.assertIn("no es de healthchecks", lat.guardar_url("https://otra.com/x"))
            self.assertIn("ya no mando", lat.guardar_url("quitar"))
            escribir.assert_called_with("")

    def test_el_bot_late_en_cada_vuelta(self):
        from pos_uniformes.services import telegram_bot_service as bot

        with patch("pos_uniformes.services.telegram_service._llamar", return_value={"result": []}), \
                patch.object(bot, "asegurar_menu_fijado"), patch.object(bot, "registrar_comandos"), \
                patch.object(bot, "limpiar_si_toca"), patch.object(bot, "refrescar_menu_si_toca"), \
                patch("pos_uniformes.services.alertas_service.procesar"), \
                patch.object(lat, "latir") as latir:
            bot.escuchar(session_factory=MagicMock(), token="t", chat_id="1", una_vez=True)
        latir.assert_called_once()

    def test_comando_latido(self):
        from pos_uniformes.services import telegram_bot_service as bot

        with patch.object(lat, "url_configurada", return_value=""):
            r = bot.atender_texto("/latido", session_factory=MagicMock())
        self.assertIn("healthchecks.io", r)
        with patch.object(lat, "guardar_url", return_value="ok") as guardar:
            bot.atender_texto("/latido https://hc-ping.com/abc", session_factory=MagicMock())
        guardar.assert_called_once_with("https://hc-ping.com/abc")


if __name__ == "__main__":
    unittest.main()
