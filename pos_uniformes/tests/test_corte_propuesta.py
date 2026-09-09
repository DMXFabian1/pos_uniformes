"""Corte con permiso: primero pregunta por Telegram, luego imprime."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services import corte_propuesta_service as prop


class EstadoTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self._patch = patch.object(prop, "ruta_estado", return_value=Path(self._dir.name) / "corte_propuesto.json")
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._dir.cleanup()

    def test_sin_archivo_no_hay_propuesta(self) -> None:
        self.assertFalse(prop.leer().hay)

    def test_anotar_y_leer(self) -> None:
        momento = datetime(2026, 9, 9, 17, 30)
        prop.anotar_propuesta(momento)
        p = prop.leer()
        self.assertTrue(p.hay)
        self.assertEqual(p.fecha, date(2026, 9, 9))
        self.assertFalse(p.recordado)
        self.assertFalse(p.cancelado)

    def test_nocorte_cancela_solo_la_de_hoy(self) -> None:
        prop.anotar_propuesta(datetime(2026, 9, 9, 17, 30))
        self.assertFalse(prop.cancelar(hoy=date(2026, 9, 10)))  # la de ayer no
        self.assertTrue(prop.cancelar(hoy=date(2026, 9, 9)))
        self.assertTrue(prop.leer().cancelado)


class RecordatorioTests(unittest.TestCase):
    HOY = date(2026, 9, 9)

    def _p(self, **kw):
        base = dict(fecha=self.HOY, momento=datetime(2026, 9, 9, 17, 30), recordado=False, cancelado=False)
        base.update(kw)
        return prop.Propuesta(**base)

    def test_pendiente_se_recuerda(self) -> None:
        self.assertTrue(prop.toca_recordar(self._p(), hoy=self.HOY, hubo_corte_despues=False))

    def test_una_sola_vez(self) -> None:
        self.assertFalse(prop.toca_recordar(self._p(recordado=True), hoy=self.HOY, hubo_corte_despues=False))

    def test_si_contesto_no_se_recuerda(self) -> None:
        self.assertFalse(prop.toca_recordar(self._p(), hoy=self.HOY, hubo_corte_despues=True))
        self.assertFalse(prop.toca_recordar(self._p(cancelado=True), hoy=self.HOY, hubo_corte_despues=False))

    def test_la_de_ayer_no_se_recuerda(self) -> None:
        self.assertFalse(
            prop.toca_recordar(self._p(), hoy=self.HOY + timedelta(days=1), hubo_corte_despues=False)
        )

    def test_sin_propuesta_no_hay_nada_que_recordar(self) -> None:
        self.assertFalse(prop.toca_recordar(prop.Propuesta(), hoy=self.HOY, hubo_corte_despues=False))


class ScriptTests(unittest.TestCase):
    """La tarea de las 17:30 propone; ya no cierra la caja sola."""

    def _correr(self, argv):
        from contextlib import contextmanager
        from unittest.mock import MagicMock

        from pos_uniformes.scripts import corte_automatico as script
        from pos_uniformes.services import corte_caja_service, corte_remoto_service, horario_tienda_service

        @contextmanager
        def _sesion():
            yield MagicMock()

        estado = MagicMock()
        estado.resumen.operaciones = 4
        with patch("pos_uniformes.database.connection.get_session", _sesion), patch.object(
            corte_caja_service, "estado_caja", return_value=estado
        ), patch.object(corte_caja_service, "ultimo_corte", return_value=None), patch.object(
            corte_caja_service, "pagos_que_tocan_hoy", return_value=[]
        ), patch.object(
            horario_tienda_service, "decidir_corte_automatico",
            return_value=horario_tienda_service.DecisionCorte(True, "toca el corte"),
        ), patch.object(
            corte_remoto_service, "texto_propuesta_corte", return_value="¿Hacemos el corte?"
        ), patch.object(
            corte_remoto_service, "hacer_corte_y_avisar"
        ) as hacer, patch.object(script, "_mandar") as mandar:
            codigo = script.main(argv)
        return codigo, hacer, mandar

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        parche = patch.object(
            prop, "ruta_estado", return_value=Path(self._dir.name) / "corte_propuesto.json"
        )
        parche.start()
        self.addCleanup(parche.stop)

    def test_por_defecto_pregunta_y_no_cierra(self) -> None:
        codigo, hacer, mandar = self._correr([])
        self.assertEqual(codigo, 0)
        hacer.assert_not_called()  # nada se guarda ni se imprime
        mandar.assert_called_once()
        self.assertIn("corte", mandar.call_args[0][0].lower())
        self.assertTrue(prop.leer().hay)  # queda pendiente de respuesta

    def test_con_hacer_sigue_cerrando_sin_preguntar(self) -> None:
        codigo, hacer, _mandar = self._correr(["--hacer"])
        self.assertEqual(codigo, 0)
        hacer.assert_called_once()


class OpcionesCorteTests(unittest.TestCase):
    """/corte 5000 sintarjeta — cuánto se retira y si se esconde la tarjeta."""

    def _leer(self, texto):
        from pos_uniformes.services.telegram_bot_service import leer_opciones_corte

        return leer_opciones_corte(texto)

    def test_sin_argumento_es_el_corte_de_siempre(self) -> None:
        o = self._leer("")
        self.assertIsNone(o.retirar)
        self.assertFalse(o.sin_tarjeta)

    def test_cifra_y_palabra_en_cualquier_orden(self) -> None:
        from decimal import Decimal

        for texto in ("5000 sintarjeta", "sintarjeta 5000", "sintarjeta $5,000"):
            o = self._leer(texto)
            self.assertEqual(o.retirar, Decimal("5000.00"), texto)
            self.assertTrue(o.sin_tarjeta, texto)

    def test_con_centavos(self) -> None:
        from decimal import Decimal

        self.assertEqual(self._leer("5000.50").retirar, Decimal("5000.50"))

    def test_palabras_raras_explican_como_se_usa(self) -> None:
        with self.assertRaises(ValueError) as caso:
            self._leer("mañana")
        self.assertIn("/corte 5000", str(caso.exception))

    def test_negativo_se_rechaza(self) -> None:
        with self.assertRaises(ValueError):
            self._leer("-100")


class CorteConModificacionesTests(unittest.TestCase):
    """El bot pasa las opciones al corte y el papel cuadra con la cifra."""

    def test_el_comando_llega_al_servicio(self) -> None:
        from contextlib import contextmanager
        from decimal import Decimal
        from unittest.mock import MagicMock

        from pos_uniformes.services import corte_remoto_service as crs
        from pos_uniformes.services import telegram_bot_service as bot

        @contextmanager
        def _sesion():
            yield MagicMock()

        with patch.object(crs, "hacer_corte_y_avisar") as hacer:
            hacer.return_value = MagicMock(mensaje="listo")
            bot.atender_texto("/corte 5000 sintarjeta", session_factory=_sesion)
        self.assertEqual(hacer.call_args.kwargs["retirar"], Decimal("5000.00"))
        self.assertTrue(hacer.call_args.kwargs["sin_tarjeta"])

    def test_argumento_invalido_no_hace_corte(self) -> None:
        from contextlib import contextmanager
        from unittest.mock import MagicMock

        from pos_uniformes.services import corte_remoto_service as crs
        from pos_uniformes.services import telegram_bot_service as bot

        @contextmanager
        def _sesion():
            yield MagicMock()

        with patch.object(crs, "hacer_corte_y_avisar") as hacer:
            r = bot.atender_texto("/corte mañana", session_factory=_sesion)
        hacer.assert_not_called()
        self.assertIn("No entendí", r)


class BotTests(unittest.TestCase):
    def test_nocorte_responde_segun_haya_propuesta(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        with patch.object(prop, "cancelar", return_value=True):
            r = bot.atender_texto("/nocorte", session_factory=None)
        self.assertIn("no se hace el corte", r)
        with patch.object(prop, "cancelar", return_value=False):
            r = bot.atender_texto("/nocorte", session_factory=None)
        self.assertIn("No hay ningún corte propuesto", r)

    def test_el_comando_esta_en_la_ayuda(self) -> None:
        from pos_uniformes.services import telegram_bot_service as bot

        self.assertIn("/nocorte", bot.AYUDA)


if __name__ == "__main__":
    unittest.main()
