"""El cierre automático y el resumen no se callan (auditoría 2026-11-07, #19 y #20)."""

from __future__ import annotations

import unittest
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

from pos_uniformes.scripts import corte_automatico as script
from pos_uniformes.scripts import resumen_diario_telegram as rd
from pos_uniformes.services import (
    corte_caja_service,
    corte_propuesta_service,
    corte_remoto_service,
    telegram_service,
)
from pos_uniformes.services.corte_remoto_service import ResultadoCorte


@contextmanager
def _sesion():
    yield MagicMock()


class CierreAutomaticoTests(unittest.TestCase):
    def _cerrar(self, *, resultado=None, falla=None, toca=True, propuesta=None):
        estado = MagicMock()
        estado.resumen.operaciones = 4
        hacer = MagicMock(return_value=resultado, side_effect=falla)
        propuesta = propuesta or corte_propuesta_service.Propuesta()
        with patch("pos_uniformes.database.connection.get_session", _sesion), \
             patch.object(corte_caja_service, "estado_caja", return_value=estado), \
             patch.object(corte_caja_service, "ultimo_corte", return_value=None), \
             patch.object(corte_propuesta_service, "leer", return_value=propuesta), \
             patch.object(corte_propuesta_service, "toca_cerrar_solo", return_value=toca), \
             patch.object(corte_remoto_service, "hacer_corte_y_avisar", hacer), \
             patch.object(script, "_mandar") as mandar:
            codigo = script._cerrar_si_nadie_contesto()
        return codigo, [c.args[0] for c in mandar.call_args_list]

    def test_si_truena_se_avisa(self) -> None:
        codigo, mensajes = self._cerrar(falla=RuntimeError("connection refused"))
        self.assertEqual(codigo, 1)
        self.assertEqual(len(mensajes), 1)
        self.assertIn("Quise cerrar el día por ti y no pude", mensajes[0])
        self.assertIn("connection refused", mensajes[0])

    def test_un_corte_no_hecho_no_dice_cerre(self) -> None:
        codigo, mensajes = self._cerrar(resultado=ResultadoCorte(False, "Ya hay un corte de este periodo."))
        self.assertEqual(codigo, 1)
        self.assertNotIn("🌙 Cerré el día", mensajes[0])
        self.assertIn("Ya hay un corte de este periodo.", mensajes[0])

    def test_hecho_si_lo_dice(self) -> None:
        _, mensajes = self._cerrar(resultado=ResultadoCorte(True, "🧾 Corte hecho"))
        self.assertIn("🌙 Cerré el día por ti", mensajes[0])

    def test_el_jueves_dice_su_hora(self) -> None:
        """El texto decía «la tarea de las 17:30» también en jueves y domingo."""
        jueves = datetime(2026, 11, 5, 18, 0).astimezone()
        with patch.object(script, "datetime") as dt:
            dt.now.return_value = jueves
            dt.combine = datetime.combine
            _, mensajes = self._cerrar(toca=False)
        self.assertIn("la tarea de las 16:30", mensajes[0])


class SinLineaSeEncolaTests(unittest.TestCase):
    def test_el_corte_automatico_encola_si_no_sale(self) -> None:
        with patch.object(telegram_service, "token_configurado", return_value=True), \
             patch.object(telegram_service, "chat_id_configurado", return_value=True), \
             patch.object(telegram_service, "enviar_mensaje", side_effect=OSError("sin red")), \
             patch.object(script, "_encolar", return_value=True) as encolar:
            self.assertTrue(script._mandar("¿Hacemos el corte?", "{botones}"))
        encolar.assert_called_once_with("¿Hacemos el corte?", "{botones}")

    def test_con_linea_no_encola(self) -> None:
        with patch.object(telegram_service, "token_configurado", return_value=True), \
             patch.object(telegram_service, "chat_id_configurado", return_value=True), \
             patch.object(telegram_service, "enviar_mensaje", return_value=1) as enviar, \
             patch.object(script, "_encolar") as encolar:
            self.assertTrue(script._mandar("hola"))
        encolar.assert_not_called()
        self.assertTrue(enviar.call_args.kwargs["conservar"])

    def test_el_resumen_encola_si_no_sale(self) -> None:
        with patch("pos_uniformes.database.connection.get_session", _sesion), \
             patch("pos_uniformes.services.resumen_diario_service.recolectar"), \
             patch("pos_uniformes.services.resumen_diario_service.formatear", return_value="📊 Resumen"), \
             patch.object(telegram_service, "enviar_mensaje", side_effect=OSError("sin red")), \
             patch.object(rd, "_encolar", return_value=True) as encolar, \
             patch.object(rd, "anotar_resumen_enviado") as anotar, \
             patch.object(rd, "resumen_ya_enviado", return_value=False), \
             patch("pos_uniformes.services.horario_tienda_service.es_momento_de_resumen", return_value=True), \
             patch("pos_uniformes.services.telegram_pulso_service.texto_salud", return_value="🩺 SALUD"):
            codigo = rd.main(["--si-toca"])
        self.assertEqual(codigo, 0)
        encolar.assert_called_once_with("📊 Resumen\n\n🩺 SALUD", None)
        anotar.assert_called_once()       # que la tarea de las 17:45 no lo duplique

    def test_si_tampoco_se_encola_falla(self) -> None:
        with patch("pos_uniformes.database.connection.get_session", _sesion), \
             patch("pos_uniformes.services.resumen_diario_service.recolectar"), \
             patch("pos_uniformes.services.resumen_diario_service.formatear", return_value="📊 Resumen"), \
             patch.object(telegram_service, "enviar_mensaje", side_effect=OSError("sin red")), \
             patch.object(rd, "_encolar", return_value=False):
            self.assertEqual(rd.main([]), 1)


if __name__ == "__main__":
    unittest.main()
