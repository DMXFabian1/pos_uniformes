"""Resiliencia del satélite ante caídas de conexión con la PC principal.

Reportado en piso (2026-07-08): "(psycopg.OperationalError) server closed the
connection unexpectedly" mostrado como traceback crudo al escanear un SKU. La
LAN por Wi-Fi parpadea; la consulta debe caer al catálogo local y mostrar un
mensaje amigable en vez del traceback.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from sqlalchemy.exc import OperationalError

from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow


def _db_down(*_a, **_k):
    raise OperationalError("SELECT ...", {}, Exception("server closed the connection"))


class EnginePoolConfigTests(unittest.TestCase):
    def test_engine_has_pre_ping_and_recycle(self) -> None:
        from pos_uniformes.database.connection import engine

        # pool_pre_ping se refleja en el pool como _pre_ping True.
        self.assertTrue(getattr(engine.pool, "_pre_ping", False))
        self.assertEqual(engine.pool._recycle, 1800)


class KioskLookupFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _online_window(self) -> QuoteSatelliteWindow:
        window = QuoteSatelliteWindow(user_id=1)
        window.offline_mode = False
        window.catalog_snapshot_rows = [
            {
                "sku": "SKU004201", "producto_nombre_base": "Pants 2pz", "escuela_nombre": "General",
                "tipo_prenda_nombre": "Pant", "tipo_pieza_nombre": "Pants 2pz", "talla": "6",
                "color": "Azul", "precio_venta": "450.00", "stock_actual": 3,
                "producto_activo": True, "variante_activo": True,
            }
        ]
        # La búsqueda va por el índice O(1), no por la lista: sin esto el test
        # dependía de lo que trajera data/catalog_cache.json en esta máquina.
        window._rebuild_sku_index()
        return window

    def test_lookup_falls_back_to_cache_on_db_error(self) -> None:
        window = self._online_window()
        window.kiosk_scan_input.setText("SKU004201")
        with patch(
            "pos_uniformes.ui.quote_satellite_window.get_session", side_effect=_db_down
        ), patch(
            "pos_uniformes.ui.quote_satellite_window.QMessageBox.warning"
        ) as warn:
            window._handle_lookup_scan()
        # Encontró el precio local — sin popup de error, con snapshot cargado.
        self.assertIsNotNone(window.lookup_snapshot)
        self.assertEqual(window.lookup_snapshot.sku, "SKU004201")
        warn.assert_not_called()

    def test_lookup_no_ugly_traceback_when_cache_also_misses(self) -> None:
        window = self._online_window()
        window.catalog_snapshot_rows = []  # ni en cache
        window.kiosk_scan_input.setText("SKU999999")
        with patch(
            "pos_uniformes.ui.quote_satellite_window.get_session", side_effect=_db_down
        ), patch(
            "pos_uniformes.ui.quote_satellite_window.QMessageBox.warning"
        ) as warn:
            window._handle_lookup_scan()
        self.assertIsNone(window.lookup_snapshot)
        warn.assert_called_once()
        msg = warn.call_args.args[2]
        # Lo esencial: NUNCA el traceback de psycopg en pantalla.
        self.assertNotIn("psycopg", msg)
        self.assertNotIn("Traceback", msg)
        self.assertNotIn("OperationalError", msg)

    def test_lookup_shows_friendly_message_when_db_down_and_no_cache_loaded(self) -> None:
        # Si _kiosk_lookup_from_cache lanza un error de DB (no ValueError),
        # se muestra el mensaje de "sin conexión".
        window = self._online_window()
        window.kiosk_scan_input.setText("SKU004201")
        with patch(
            "pos_uniformes.ui.quote_satellite_window.get_session", side_effect=_db_down
        ), patch.object(
            window, "_kiosk_lookup_from_cache", side_effect=_db_down
        ), patch(
            "pos_uniformes.ui.quote_satellite_window.QMessageBox.warning"
        ) as warn:
            window._handle_lookup_scan()
        self.assertIsNone(window.lookup_snapshot)
        msg = warn.call_args.args[2]
        self.assertIn("Sin conexion con la PC principal", msg)
        self.assertNotIn("psycopg", msg)

    def test_add_item_falls_back_to_cache_on_db_error(self) -> None:
        window = self._online_window()
        window._can_build_cart = lambda: True
        window._add_quote_item_from_cache = Mock()
        with patch(
            "pos_uniformes.ui.quote_satellite_window.get_session", side_effect=_db_down
        ):
            window._add_quote_item_by_sku("SKU004201", 1)
        window._add_quote_item_from_cache.assert_called_once_with("SKU004201", 1)


    def test_lookup_clears_input_on_unknown_sku(self) -> None:
        # SKU inexistente: el cajón debe quedar vacío para que el siguiente
        # escaneo no se apile con el código que no existía.
        window = self._online_window()
        window.offline_mode = True  # busca solo en el cache local
        window.catalog_snapshot_rows = []  # nada → "no encontrado"
        window.kiosk_scan_input.setText("NOEXISTE123")
        with patch(
            "pos_uniformes.ui.quote_satellite_window.QMessageBox.warning"
        ):
            window._handle_lookup_scan()
        self.assertEqual(window.kiosk_scan_input.text(), "")

    def test_lookup_clears_input_on_success(self) -> None:
        window = self._online_window()
        window.offline_mode = True
        window.kiosk_scan_input.setText("SKU004201")
        window._handle_lookup_scan()
        self.assertEqual(window.kiosk_scan_input.text(), "")


if __name__ == "__main__":
    unittest.main()


class SeCaeAMediaTardeTests(unittest.TestCase):
    """Si la PC principal se apaga con el satélite ya abierto.

    Daniel (01/10): "si la pc principal se apaga, el satélite empieza a fallar
    y sugiere cerrar". El arranque sin conexión siempre funcionó; lo que no
    estaba cubierto es caerse A MEDIA TARDE, porque `offline_mode` se decidía
    una vez al abrir y ya no cambiaba: las treinta decisiones que cuelgan de
    él seguían tomando el camino de la base.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _ventana(self) -> QuoteSatelliteWindow:
        return QuoteSatelliteWindow(user_id=1)

    def test_arranca_en_linea(self) -> None:
        w = self._ventana()
        self.assertFalse(w.offline_mode)
        self.assertTrue(w.db_en_linea)

    def test_al_caerse_la_ventana_se_vuelve_local(self) -> None:
        w = self._ventana()
        w.marcar_sin_conexion()
        self.assertTrue(w.offline_mode)
        self.assertFalse(w.db_en_linea)

    def test_al_volver_la_pc_vuelve_a_estar_en_linea(self) -> None:
        w = self._ventana()
        w.marcar_sin_conexion()
        w._on_db_refresh_ready([{"sku": "SKU1"}], None)
        self.assertFalse(w.offline_mode)

    def test_el_watchdog_sin_filas_la_marca_local(self) -> None:
        w = self._ventana()
        w._on_db_refresh_ready(None, None)
        self.assertTrue(w.offline_mode)

    def test_marcar_dos_veces_no_hace_nada_la_segunda(self) -> None:
        w = self._ventana()
        w.marcar_sin_conexion()
        w._set_db_connectivity_banner = Mock()
        w.marcar_sin_conexion()
        w._set_db_connectivity_banner.assert_not_called()

    def test_el_que_arranco_offline_sigue_offline_aunque_vuelva(self) -> None:
        # Booteó sin user_id ni catálogo en vivo: volver a "en línea" a media
        # tarde la dejaría a medias. Se reinicia y ya.
        w = QuoteSatelliteWindow(user_id=None, offline_mode=True, offline_catalog_cache=[])
        w._db_online = True
        self.assertTrue(w.offline_mode)

    def test_el_banner_dice_que_se_puede_seguir_vendiendo(self) -> None:
        # Un banner que solo informa de la falla invita a apagar y volver a
        # abrir, que es lo peor que puede hacerse con ventas a medias.
        w = self._ventana()
        w.marcar_sin_conexion()
        texto = w.offline_banner.text()
        self.assertIn("seguir vendiendo", texto)
        self.assertIn("se sube solo", texto)

    def test_avisar_del_banner_no_puede_tumbar_la_venta(self) -> None:
        w = self._ventana()
        w._set_db_connectivity_banner = Mock(side_effect=RuntimeError("widget muerto"))
        w.marcar_sin_conexion()          # no debe propagar
        self.assertTrue(w.offline_mode)


class GafeteSinConexionTests(unittest.TestCase):
    """El gate decía «código no encontrado» cuando lo que faltaba era la PC."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _vista(self, *, offline=False):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        satellite = SimpleNamespace(
            offline_mode=offline,
            _kiosk_lookup_from_cache=None,
            marcar_sin_conexion=Mock(),
        )
        vista = QuickSaleWidget.__new__(QuickSaleWidget)
        vista.satellite = satellite
        return vista, satellite

    def test_resuelve_el_gafete_con_la_copia_local(self) -> None:
        vista, _ = self._vista()
        with patch(
            "pos_uniformes.services.nombres_empleadas_service.nombres_por_codigo",
            return_value={"VEND-3": "Evelyn Ortiz"},
        ):
            self.assertEqual(vista._empleada_de_cache("vend-3"), ("VEND-3", "Evelyn Ortiz"))

    def test_sin_copia_local_acepta_el_formato_de_siempre(self) -> None:
        # Vale más vender que validar: es el mismo criterio que cuando el
        # programa arranca sin conexión.
        vista, _ = self._vista()
        with patch(
            "pos_uniformes.services.nombres_empleadas_service.nombres_por_codigo",
            return_value={},
        ):
            self.assertEqual(vista._empleada_de_cache("VEND-9"), ("VEND-9", "VEND-9"))
            self.assertEqual(vista._empleada_de_cache("ENC-1"), ("ENC-1", "ENC-1"))

    def test_un_codigo_que_no_es_gafete_no_abre(self) -> None:
        vista, _ = self._vista()
        with patch(
            "pos_uniformes.services.nombres_empleadas_service.nombres_por_codigo",
            return_value={},
        ):
            self.assertIsNone(vista._empleada_de_cache("SKU000123"))

    def test_si_la_copia_truena_no_revienta(self) -> None:
        vista, _ = self._vista()
        with patch(
            "pos_uniformes.services.nombres_empleadas_service.nombres_por_codigo",
            side_effect=OSError("disco"),
        ):
            self.assertEqual(vista._empleada_de_cache("VEND-3"), ("VEND-3", "VEND-3"))

    def test_avisa_a_la_ventana_para_no_reintentar(self) -> None:
        # Sin esto cada operación vuelve a esperar el timeout de 5 s hasta que
        # pase el watchdog, que tarda 5 minutos.
        vista, satellite = self._vista()
        vista._avisar_sin_conexion()
        satellite.marcar_sin_conexion.assert_called_once()

    def test_una_ventana_sin_ese_metodo_no_revienta(self) -> None:
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        vista = QuickSaleWidget.__new__(QuickSaleWidget)
        vista.satellite = SimpleNamespace(offline_mode=False)
        vista._avisar_sin_conexion()  # no debe lanzar


class EsperarALaPrincipalTests(unittest.TestCase):
    """Se va la luz, vuelve, y todo se prende junto.

    El servidor tarda en levantar Postgres; el kiosko bootea en segundos. Antes
    probaba UNA vez, no encontraba nada, y se quedaba en modo local toda la
    mañana — o se negaba a abrir si tampoco tenía catálogo guardado.
    """

    def setUp(self) -> None:
        from pos_uniformes.services import satellite_startup_service as sss

        self.sss = sss
        self.dormido = []

    def _esperar(self, respuestas, **extra):
        pasos = iter(respuestas)
        reloj = {"t": 0.0}

        def _probe():
            return next(pasos, False)

        def _dormir(seg):
            self.dormido.append(seg)
            reloj["t"] += seg

        args = dict(probe=_probe, dormir=_dormir, reloj=lambda: reloj["t"])
        args.update(extra)
        return self.sss.esperar_base(**args)

    def test_si_ya_esta_encendida_no_espera_nada(self) -> None:
        # El caso de todos los días: esperar solo cuesta cuando no hay nadie.
        self.assertTrue(self._esperar([True]))
        self.assertEqual(self.dormido, [])

    def test_aguanta_mientras_el_servidor_levanta(self) -> None:
        self.assertTrue(self._esperar([False, False, True]))
        self.assertEqual(len(self.dormido), 2)

    def test_se_rinde_y_sigue_en_modo_local(self) -> None:
        # Rendirse está bien: abre con el catálogo guardado. Lo que no está
        # bien es quedarse esperando para siempre con la tienda abriendo.
        self.assertFalse(self._esperar([False] * 100, limite_seg=10, cada_seg=3))

    def test_no_espera_mas_del_limite(self) -> None:
        self._esperar([False] * 100, limite_seg=9, cada_seg=3)
        self.assertLessEqual(sum(self.dormido), 9)

    def test_le_cuenta_al_de_la_pantalla_cuanto_falta(self) -> None:
        avisos = []
        self._esperar([False, False, True], avisar=lambda i, r: avisos.append((i, r)))
        self.assertEqual([i for i, _ in avisos], [1, 2])
        self.assertTrue(all(r >= 0 for _, r in avisos))

    def test_un_aviso_que_truena_no_detiene_la_espera(self) -> None:
        def _truena(*_a):
            raise RuntimeError("splash cerrado")

        self.assertTrue(self._esperar([False, True], avisar=_truena))
