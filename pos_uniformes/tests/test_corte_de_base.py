"""La PC principal se apaga y el kiosko sigue (2026-11-25).

Daniel: «apago la PC principal antes y el kiosko inmediatamente se pone lento;
me ha obligado a encenderla de nuevo o a cerrar el programa». El pre-ping de
cada conexión guardada esperaba a un host que ya no contesta, y cada conexión
nueva esperaba su connect_timeout. `CorteDeBase` lo vuelve un «no» al instante.
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
    def test_si_no_contesta_queda_caida_un_rato_y_luego_se_reintenta(self) -> None:
        reloj = _Reloj()
        corte = cx.CorteDeBase("10.0.0.9", 5432, reloj=reloj, sondear=lambda: False)
        self.assertFalse(corte.host_contesta())
        self.assertTrue(corte.recien_caida())
        reloj.t += corte.ESPERA_TRAS_CAIDA_SEG + 1
        self.assertFalse(corte.recien_caida())

    def test_si_vuelve_a_contestar_se_olvida_la_caida(self) -> None:
        contesta = {"si": False}
        corte = cx.CorteDeBase("10.0.0.9", 5432, reloj=_Reloj(), sondear=lambda: contesta["si"])
        corte.host_contesta()
        contesta["si"] = True
        self.assertTrue(corte.host_contesta())
        self.assertFalse(corte.recien_caida())

    def test_el_sondeo_real_falla_rapido_con_un_puerto_cerrado(self) -> None:
        corte = cx.CorteDeBase("127.0.0.1", 1, reloj=_Reloj())
        self.assertFalse(corte.host_contesta())


class EngineConCorteTests(unittest.TestCase):
    def _engine(self, sondear):
        engine = create_engine("postgresql+psycopg://u:p@10.0.0.9:5432/x", pool_pre_ping=True)
        corte = cx.instalar_corte(engine, cx.CorteDeBase("10.0.0.9", 5432, reloj=_Reloj(), sondear=sondear))
        return engine, corte

    def test_apagada_no_intenta_conectar_y_falla_al_instante(self) -> None:
        engine, _ = self._engine(lambda: False)
        with patch.object(engine.dialect, "connect") as conectar:
            with self.assertRaises(OperationalError):
                engine.connect()
        conectar.assert_not_called()

    def test_recien_caida_ni_siquiera_sondea(self) -> None:
        sondeos = []
        engine, corte = self._engine(lambda: sondeos.append(1) or False)
        corte.anotar_caida()
        with self.assertRaises(OperationalError):
            engine.connect()
        self.assertEqual(sondeos, [])

    def test_si_falla_el_connect_de_postgres_se_anota_la_caida(self) -> None:
        engine, corte = self._engine(lambda: True)
        dbapi = engine.dialect.loaded_dbapi
        with patch.object(engine.dialect, "connect", side_effect=dbapi.OperationalError("timeout")):
            with self.assertRaises(OperationalError):
                engine.connect()
        self.assertTrue(corte.recien_caida())

    def test_el_pre_ping_no_toca_una_conexion_si_el_host_no_contesta(self) -> None:
        # Mandarle SELECT 1 a un host apagado es lo que esperaba ~20 s.
        engine, _ = self._engine(lambda: False)
        conexion_guardada = MagicMock()
        self.assertFalse(engine.dialect.do_ping(conexion_guardada))
        conexion_guardada.cursor.assert_not_called()

    def test_con_host_vivo_el_pre_ping_es_el_de_siempre(self) -> None:
        engine, _ = self._engine(lambda: True)
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

    def _latir(self, *, contesta: bool, en_linea: bool) -> MagicMock:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        ventana = MagicMock()
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

    def test_si_no_contesta_pasa_a_modo_local_ya(self) -> None:
        ventana = self._latir(contesta=False, en_linea=True)
        ventana._latido_sin_base.emit.assert_called_once()
        ventana._latido_con_base.emit.assert_not_called()

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
