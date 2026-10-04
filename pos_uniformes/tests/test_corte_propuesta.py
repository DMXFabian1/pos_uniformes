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

    def test_el_texto_suelto_es_la_nota(self) -> None:
        # Antes cualquier palabra rara daba error. Desde 2026-10-04 el texto
        # suelto es el motivo del corte —«/corte 5000 deposité al banco»— que
        # es el campo que faltaba desde el celular.
        self.assertEqual(self._leer("deposité al banco").nota, "deposité al banco")

    def test_una_palabra_mal_escrita_se_vuelve_nota_y_por_eso_se_repite(self) -> None:
        # El costo de aceptar texto libre: «sintarjets» ya no da error. Por eso
        # la respuesta del bot repite la nota, para que el dedazo se vea.
        opciones = self._leer("sintarjets")
        self.assertFalse(opciones.sin_tarjeta)
        self.assertEqual(opciones.nota, "sintarjets")

    def test_falta_la_cantidad_despues_de_la_palabra_clave(self) -> None:
        # Esto sí es error: «fondo» sin cifra no quiere decir nada.
        with self.assertRaises(ValueError) as caso:
            self._leer("fondo")
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

    def test_lo_que_no_es_cifra_ni_palabra_clave_viaja_como_nota(self) -> None:
        from contextlib import contextmanager
        from unittest.mock import MagicMock

        from pos_uniformes.services import corte_remoto_service as crs
        from pos_uniformes.services import telegram_bot_service as bot

        @contextmanager
        def _sesion():
            yield MagicMock()

        with patch.object(crs, "hacer_corte_y_avisar") as hacer:
            hacer.return_value = MagicMock(mensaje="listo")
            bot.atender_texto("/corte deposité al banco", session_factory=_sesion)
        self.assertEqual(hacer.call_args.kwargs["nota"], "deposité al banco")
        self.assertIsNone(hacer.call_args.kwargs["retirar"])

    def test_una_palabra_clave_sin_cifra_si_detiene_el_corte(self) -> None:
        from contextlib import contextmanager
        from unittest.mock import MagicMock

        from pos_uniformes.services import corte_remoto_service as crs
        from pos_uniformes.services import telegram_bot_service as bot

        @contextmanager
        def _sesion():
            yield MagicMock()

        with patch.object(crs, "hacer_corte_y_avisar") as hacer:
            r = bot.atender_texto("/corte fondo", session_factory=_sesion)
        hacer.assert_not_called()
        self.assertIn("falta la cantidad", r.lower())

    def test_el_fondo_y_los_otros_viajan(self) -> None:
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
            bot.atender_texto(
                "/corte 5000 fondo 2000 otros 350 me lo llevé", session_factory=_sesion
            )
        k = hacer.call_args.kwargs
        self.assertEqual(k["retirar"], Decimal("5000.00"))
        self.assertEqual(k["fondo"], Decimal("2000.00"))
        self.assertEqual(k["otros"], Decimal("350.00"))
        self.assertEqual(k["nota"], "me lo llevé")


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


class CerrarSoloTests(unittest.TestCase):
    """Si no contestó y ya cerró, el corte se hace solo.

    En el kiosko el botón del corte únicamente sale con el gafete de Daniel, así
    que sin esto un día suyo fuera es un día sin corte: el cajón se acumula sin
    registro y al volver no se sabe de qué día es cada peso.
    """

    HOY = date(2026, 10, 1)

    def _propuesta(self, **cambios):
        base = dict(
            fecha=self.HOY,
            momento=datetime(2026, 10, 1, 17, 30),
            recordado=True,
            cancelado=False,
        )
        base.update(cambios)
        return prop.Propuesta(**base)

    def _toca(self, propuesta=None, **cambios):
        args = dict(
            hoy=self.HOY,
            minutos_tras_cierre=60,
            hubo_corte_despues=False,
            hubo_movimiento=True,
        )
        args.update(cambios)
        return prop.toca_cerrar_solo(propuesta or self._propuesta(), **args)

    def test_pasado_el_cierre_y_sin_contestar_se_hace(self) -> None:
        self.assertTrue(self._toca())

    def test_todavia_no_pasa_el_margen(self) -> None:
        # Da tiempo a que conteste tras el recordatorio y a la última venta.
        self.assertFalse(self._toca(minutos_tras_cierre=10))

    def test_justo_en_el_margen_si(self) -> None:
        self.assertTrue(self._toca(minutos_tras_cierre=prop.MINUTOS_DESPUES_DE_CERRAR))

    def test_antes_de_cerrar_nunca(self) -> None:
        self.assertFalse(self._toca(minutos_tras_cierre=-30))

    def test_nocorte_se_respeta(self) -> None:
        # Si dijo que hoy no, es que hoy no.
        self.assertFalse(self._toca(self._propuesta(cancelado=True)))

    def test_sin_recordatorio_todavia_no(self) -> None:
        # Primero se le insiste; esto es el último eslabón, no el primero.
        self.assertFalse(self._toca(self._propuesta(recordado=False)))

    def test_si_ya_hay_corte_no_se_hace_otro(self) -> None:
        self.assertFalse(self._toca(hubo_corte_despues=True))

    def test_un_dia_sin_ventas_no_se_corta(self) -> None:
        self.assertFalse(self._toca(hubo_movimiento=False))

    def test_sin_propuesta_de_hoy_no_se_toca_nada(self) -> None:
        # Si el camino normal no corrió (PC apagada a esa hora), no se improvisa.
        self.assertFalse(self._toca(prop.Propuesta()))
        self.assertFalse(self._toca(self._propuesta(fecha=date(2026, 9, 30))))
