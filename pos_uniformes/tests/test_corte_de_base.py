"""La PC principal se apaga y el kiosko sigue (2026-11-25).

Daniel: «apago la PC principal antes y el kiosko inmediatamente se pone lento;
me ha obligado a encenderla de nuevo o a cerrar el programa». El pre-ping de
cada conexión guardada esperaba a un host que ya no contesta, y cada conexión
nueva esperaba su connect_timeout. `CorteDeBase` lo vuelve un «no» al instante.

2026-11-26: la primera versión sondeaba el puerto con medio segundo y, dentro
del programa, daba «no contesta» con la red bien («el kiosko pierde la conexión
seguido»). Ahora solo cuentan dos conexiones de verdad fallidas seguidas, y el
latido pide dos latidos fallidos seguidos.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from pos_uniformes.database import connection as cx


class _Reloj:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class CorteDeBaseTests(unittest.TestCase):
    def test_una_sola_falla_no_la_da_por_caida(self) -> None:
        # 2026-11-26: un tropiezo suelto no debe sacar al kiosko de línea.
        corte = cx.CorteDeBase("10.0.0.9", 5432, reloj=_Reloj())
        corte.anotar_falla("timeout")
        self.assertFalse(corte.recien_caida())

    def test_dos_fallas_seguidas_la_dan_por_caida_un_rato(self) -> None:
        reloj = _Reloj()
        corte = cx.CorteDeBase("10.0.0.9", 5432, reloj=reloj)
        corte.anotar_falla()
        with self.assertLogs("pos_uniformes.database.connection", level="WARNING") as log:
            corte.anotar_falla("timeout expired")
        self.assertIn("timeout expired", log.output[0])
        self.assertTrue(corte.recien_caida())
        reloj.t += corte.ESPERA_TRAS_CAIDA_SEG + 1
        self.assertFalse(corte.recien_caida())

    def test_un_exito_en_medio_reinicia_la_cuenta(self) -> None:
        corte = cx.CorteDeBase("10.0.0.9", 5432, reloj=_Reloj())
        corte.anotar_falla()
        corte.anotar_exito()
        corte.anotar_falla()
        self.assertFalse(corte.recien_caida())

    def test_si_vuelve_se_olvida_la_caida(self) -> None:
        corte = cx.CorteDeBase("10.0.0.9", 5432, reloj=_Reloj())
        corte.anotar_falla()
        corte.anotar_falla()
        corte.anotar_exito()
        self.assertFalse(corte.recien_caida())

    def test_ya_no_se_sondea_el_puerto(self) -> None:
        # El sondeo de medio segundo daba «no contesta» con la red bien.
        self.assertFalse(hasattr(cx.CorteDeBase, "host_contesta"))
        self.assertNotIn("socket", vars(cx))


class EngineConCorteTests(unittest.TestCase):
    def _engine(self):
        engine = create_engine("postgresql+psycopg://u:p@10.0.0.9:5432/x", pool_pre_ping=True)
        corte = cx.instalar_corte(engine, cx.CorteDeBase("10.0.0.9", 5432, reloj=_Reloj()))
        return engine, corte

    def _caer(self, corte) -> None:
        corte.anotar_falla()
        corte.anotar_falla()

    def test_con_la_base_bien_conecta_de_verdad_sin_sondear(self) -> None:
        engine, corte = self._engine()
        with patch.object(engine.dialect, "connect", return_value=MagicMock()) as conectar:
            try:
                engine.connect()
            except Exception:  # noqa: BLE001 — el MagicMock no es una conexión de verdad
                pass
        conectar.assert_called_once()
        self.assertFalse(corte.recien_caida())

    def test_recien_caida_no_intenta_conectar_y_falla_al_instante(self) -> None:
        engine, corte = self._engine()
        self._caer(corte)
        with patch.object(engine.dialect, "connect") as conectar:
            with self.assertRaises(OperationalError):
                engine.connect()
        conectar.assert_not_called()

    def test_dos_connect_fallidos_la_dan_por_caida(self) -> None:
        engine, corte = self._engine()
        dbapi = engine.dialect.loaded_dbapi
        with patch.object(engine.dialect, "connect", side_effect=dbapi.OperationalError("timeout")) as conectar:
            for _ in range(2):
                with self.assertRaises(OperationalError):
                    engine.connect()
            self.assertTrue(corte.recien_caida())
            with self.assertRaises(OperationalError):
                engine.connect()
        self.assertEqual(conectar.call_count, 2)   # el tercero ni lo intentó

    def test_recien_caida_el_pre_ping_no_toca_la_conexion_guardada(self) -> None:
        # Mandarle SELECT 1 a un host apagado es lo que esperaba ~20 s.
        engine, corte = self._engine()
        self._caer(corte)
        conexion_guardada = MagicMock()
        self.assertFalse(engine.dialect.do_ping(conexion_guardada))
        conexion_guardada.cursor.assert_not_called()

    def test_con_la_base_bien_el_pre_ping_es_el_de_siempre(self) -> None:
        engine, _ = self._engine()
        conexion = MagicMock()
        self.assertTrue(engine.dialect.do_ping(conexion))
        conexion.cursor.assert_called()

    def test_sqlite_no_lleva_corte(self) -> None:
        self.assertFalse(hasattr(cx.crear_engine("sqlite://"), "corte_de_base"))

    def test_el_engine_del_programa_lleva_corte(self) -> None:
        if cx._DB_URL.startswith("sqlite"):
            self.skipTest("engine de snapshot")
        self.assertIsInstance(cx.engine.corte_de_base, cx.CorteDeBase)


class LatidoAvisaTests(unittest.TestCase):
    """El latido (cada minuto) avisa antes que el watchdog (cada 5 min)."""

    def _latir(self, *, contesta: bool, en_linea: bool, ventana: MagicMock | None = None) -> MagicMock:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        if ventana is None:
            ventana = MagicMock()
            ventana._latidos_sin_base = 0
        ventana.db_en_linea = en_linea

        class _Inline:
            def __init__(self, target, **_kw):
                self._t = target

            def start(self):
                self._t()

        with patch("threading.Thread", _Inline), patch(
            "pos_uniformes.services.satellite_startup_service.probe_database_host", return_value=contesta
        ), patch("pos_uniformes.ui.quote_satellite_window.get_session", side_effect=RuntimeError("sin base")):
            QuoteSatelliteWindow._enviar_heartbeat(ventana)
        return ventana

    def test_un_latido_fallido_suelto_no_saca_de_linea(self) -> None:
        # 2026-11-26: «el kiosko pierde la conexión seguido» con la red bien.
        ventana = self._latir(contesta=False, en_linea=True)
        ventana._latido_sin_base.emit.assert_not_called()

    def test_dos_latidos_fallidos_seguidos_pasan_a_modo_local(self) -> None:
        ventana = self._latir(contesta=False, en_linea=True)
        self._latir(contesta=False, en_linea=True, ventana=ventana)
        ventana._latido_sin_base.emit.assert_called_once()
        ventana._latido_con_base.emit.assert_not_called()

    def test_un_latido_bueno_en_medio_reinicia_la_cuenta(self) -> None:
        ventana = self._latir(contesta=False, en_linea=True)
        self._latir(contesta=True, en_linea=True, ventana=ventana)
        self._latir(contesta=False, en_linea=True, ventana=ventana)
        ventana._latido_sin_base.emit.assert_not_called()

    def test_si_vuelve_estando_sin_conexion_lo_avisa(self) -> None:
        ventana = self._latir(contesta=True, en_linea=False)
        ventana._latido_con_base.emit.assert_called_once()
        ventana._latido_sin_base.emit.assert_not_called()

    def test_en_linea_y_contesta_no_avisa_nada(self) -> None:
        ventana = self._latir(contesta=True, en_linea=True)
        ventana._latido_con_base.emit.assert_not_called()
        ventana._latido_sin_base.emit.assert_not_called()

    def test_al_volver_se_trae_el_catalogo_sin_esperar_al_watchdog(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        ventana = MagicMock(db_en_linea=False)
        QuoteSatelliteWindow._volvio_la_base(ventana)
        ventana._start_background_db_refresh.assert_called_once()
        ventana = MagicMock(db_en_linea=True)
        QuoteSatelliteWindow._volvio_la_base(ventana)
        ventana._start_background_db_refresh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
