"""Encender, apagar o fijar los adornos de temporada desde el menú.

Existían desde octubre pero solo se podían mirar antes de tiempo con un .bat
que vencía en dos horas, y apagarlos no se podía (Daniel, 2026-10-07).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services import temporada_service as temp


class _ConAjuste(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        (base / "data").mkdir()
        self._p = patch("pos_uniformes.utils.config.runtime_base_dir", return_value=base)
        self._p.start()
        # Una prueba forzada de antes no debe ensuciar estas pruebas.
        temp.quitar_forzada()

    def tearDown(self) -> None:
        self._p.stop()
        self._tmp.cleanup()


class ElAjusteMandaTests(_ConAjuste):
    HALLOWEEN = date(2026, 10, 25)
    DIA_CUALQUIERA = date(2026, 6, 15)   # junio: no hay temporada ninguna

    def test_por_omision_es_el_calendario_de_siempre(self) -> None:
        self.assertEqual(temp.ajuste(), (temp.AUTO, ""))
        self.assertIsNotNone(temp.actual(self.HALLOWEEN))
        self.assertIsNone(temp.actual(self.DIA_CUALQUIERA))

    def test_apagados_no_sale_nada_ni_en_su_fecha(self) -> None:
        temp.guardar_ajuste(temp.APAGADA)
        self.assertIsNone(temp.actual(self.HALLOWEEN))

    def test_fija_sale_aunque_no_sea_la_fecha(self) -> None:
        """Lo que Daniel pidió: calabazas el 7 de octubre."""
        temp.guardar_ajuste(temp.FIJA, "halloween")
        t = temp.actual(self.DIA_CUALQUIERA)
        self.assertIsNotNone(t)
        self.assertEqual(t.nombre, "Halloween")

    def test_fija_no_acepta_una_temporada_inventada(self) -> None:
        with self.assertRaises(ValueError):
            temp.guardar_ajuste(temp.FIJA, "dia_del_programador")

    def test_un_modo_inventado_tampoco(self) -> None:
        with self.assertRaises(ValueError):
            temp.guardar_ajuste("a_veces")

    def test_un_archivo_roto_cae_al_calendario(self) -> None:
        temp.ruta_ajuste().write_text("{no es json", encoding="utf-8")
        self.assertEqual(temp.ajuste(), (temp.AUTO, ""))
        self.assertIsNotNone(temp.actual(self.HALLOWEEN))

    def test_volver_a_automatico_limpia_la_fija(self) -> None:
        temp.guardar_ajuste(temp.FIJA, "navidad")
        temp.guardar_ajuste(temp.AUTO)
        self.assertEqual(temp.ajuste(), (temp.AUTO, ""))
        self.assertIsNone(temp.actual(self.DIA_CUALQUIERA))


class LaPruebaDeDosHorasSigueMandandoTests(_ConAjuste):
    def test_lo_forzado_gana_sobre_el_ajuste(self) -> None:
        """Forzar es para mirar algo AHORA; por eso pisa al ajuste. Y vence
        solo, para que una prueba no se quede puesta hasta marzo."""
        temp.guardar_ajuste(temp.APAGADA)
        temp.forzar("navidad")
        t = temp.actual(date(2026, 6, 15))
        self.assertIsNotNone(t)
        self.assertEqual(t.nombre, "Navidad")


if __name__ == "__main__":
    unittest.main()


class LaTemporadaSobreviveAlCerrarElProgramaTests(unittest.TestCase):
    """«quise poner halloween desde ahora, y ahorita que reinicié ya no
    aparece» (Daniel, 2026-10-09).

    Lo estaba guardando con `runtime_base_dir`, que en el kiosko empaquetado
    es la carpeta del .exe. Los otros ajustes por máquina —impresoras,
    ESC/POS— viven en `satellite_data_dir` (AppData en el bundle) justamente
    porque esa carpeta sí dura.
    """

    def test_vive_donde_los_demas_ajustes_de_maquina(self) -> None:
        """El conftest aísla `ruta_ajuste` por test, así que no se llama:
        se comprueba la carpeta que el módulo dice usar."""
        from pos_uniformes.services import escpos_settings_cache_service as esc
        from pos_uniformes.services import print_routing_cache_service as rut
        from pos_uniformes.utils.config import satellite_data_dir

        vecinos = {esc._cache_path().parent, rut._cache_path().parent}
        self.assertEqual(len(vecinos), 1, "los otros ajustes ya no coinciden")
        self.assertEqual(satellite_data_dir() / "data", vecinos.pop())

    def test_no_se_guarda_junto_al_exe(self) -> None:
        """Esa carpeta la reemplaza la actualización del kiosko.

        Se mira la IMPORTACIÓN y no la palabra: el porqué está escrito en un
        comentario del propio archivo, y buscar el nombre a secas hacía
        fallar el test por su propia explicación."""
        from pathlib import Path

        from pos_uniformes.services import temporada_service as t

        codigo = Path(t.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import runtime_base_dir", codigo)
        self.assertEqual(codigo.count("import satellite_data_dir"), 2)

    def test_lo_guardado_se_lee_de_vuelta(self) -> None:
        """La comprobación de siempre, por si el camino cambia otra vez."""
        from pos_uniformes.services import temporada_service as t

        t.guardar_ajuste(t.FIJA, "halloween")
        self.assertEqual(t.ajuste(), (t.FIJA, "halloween"))
        self.assertTrue(t.ruta_ajuste().exists())


#: La lectura real, capturada al importar: el conftest la sustituye en cada
#: test para que ninguno herede la temporada de otro.
from pos_uniformes.services.temporada_service import (  # noqa: E402
    _ajuste_de_la_tienda as _LECTURA_DE_VERDAD,
)


class LaTemporadaEsDeLaTiendaTests(unittest.TestCase):
    """«si pongo una temporada en una quiero que se replique en las demás»
    (Daniel, 2026-10-09).

    Era un ajuste por máquina: había que ponerlo tres veces y se
    desincronizaban. Ahora la base manda y el archivo local es la red de
    abajo, para que el kiosko sin red siga sabiendo qué mes es.
    """

    def setUp(self) -> None:
        from pos_uniformes.services import temporada_service as t

        t.olvidar_lo_leido()
        self.addCleanup(t.olvidar_lo_leido)

    def test_lo_que_dice_la_base_manda_sobre_el_archivo(self) -> None:
        from unittest.mock import patch

        from pos_uniformes.services import temporada_service as t

        t.guardar_ajuste(t.FIJA, "halloween")      # deja el archivo local
        with patch.object(t, "_ajuste_de_la_tienda", return_value=(t.APAGADA, "")):
            self.assertEqual(t.ajuste(), (t.APAGADA, ""))

    def test_sin_base_manda_el_archivo_de_esta_maquina(self) -> None:
        """El kiosko sin red tiene que seguir sabiendo qué mes es."""
        from unittest.mock import patch

        from pos_uniformes.services import temporada_service as t

        t.guardar_ajuste(t.FIJA, "navidad")
        with patch.object(t, "_ajuste_de_la_tienda", return_value=None):
            self.assertEqual(t.ajuste(), (t.FIJA, "navidad"))

    def test_guardar_dice_si_llego_a_las_demas(self) -> None:
        """Sin eso creería que ya quedó en toda la tienda."""
        from unittest.mock import patch

        from pos_uniformes.services import temporada_service as t

        with patch("pos_uniformes.database.connection.get_session",
                   side_effect=OSError("sin red")):
            self.assertFalse(t.guardar_ajuste(t.FIJA, "halloween"))
        # Y aun así esta máquina quedó bien.
        with patch.object(t, "_ajuste_de_la_tienda", return_value=None):
            self.assertEqual(t.ajuste(), (t.FIJA, "halloween"))

    def test_no_se_pregunta_a_la_base_en_cada_renglon(self) -> None:
        """`actual()` se llama por ticket y por repintado.

        Se devuelve la función de verdad: el conftest la parchea para que
        ningún test herede la temporada de otro, y aquí es justamente lo que
        se quiere medir."""
        from unittest.mock import patch

        from pos_uniformes.services import temporada_service as t

        with patch.object(t, "_ajuste_de_la_tienda", _LECTURA_DE_VERDAD), \
             patch("pos_uniformes.services.business_settings_service"
                   ".BusinessSettingsService.get_or_create") as leer:
            leer.return_value = type("C", (), {"temporada_modo": t.APAGADA,
                                               "temporada_archivo": ""})()
            for _ in range(5):
                t.ajuste()
        self.assertEqual(leer.call_count, 1)

    def test_al_guardar_se_olvida_lo_memorizado(self) -> None:
        """Si no, el propio cambio tardaría medio minuto en verse aquí."""
        from unittest.mock import patch

        from pos_uniformes.services import temporada_service as t

        with patch.object(t, "_ajuste_de_la_tienda", return_value=None):
            t.ajuste()                                    # llena la memoria
            t.guardar_ajuste(t.FIJA, "san_valentin")
            self.assertEqual(t._memoria, (0.0, None))

    def test_un_modo_raro_en_la_base_no_manda(self) -> None:
        """Una columna con basura no puede apagar los adornos de la tienda."""
        from unittest.mock import patch

        with patch("pos_uniformes.services.business_settings_service"
                   ".BusinessSettingsService.get_or_create") as leer:
            leer.return_value = type("C", (), {"temporada_modo": "vete a saber",
                                               "temporada_archivo": ""})()
            self.assertIsNone(_LECTURA_DE_VERDAD())


class ElKioskoSeEnteraSinReiniciarTests(unittest.TestCase):
    def test_el_latido_lee_y_la_pantalla_repinta(self) -> None:
        """Leer va en el hilo del latido, repintar en el de la UI: tocar
        widgets desde un hilo tumba Qt."""
        from pathlib import Path

        codigo = Path(__file__).resolve().parents[1].joinpath(
            "ui/quote_satellite_window.py"
        ).read_text(encoding="utf-8")
        trozo = codigo[codigo.index("def _enviar_heartbeat"):][:1800]
        self.assertIn("from pos_uniformes.services.temporada_service import actual",
                      trozo)
        self.assertIn("QTimer.singleShot(", trozo)
        self.assertIn("_repintar_si_cambio_la_temporada", trozo)

    def test_no_repinta_si_no_cambio(self) -> None:
        """Repintar cada minuto sin motivo parpadearía la pantalla."""
        from pathlib import Path

        codigo = Path(__file__).resolve().parents[1].joinpath(
            "ui/quote_satellite_window.py"
        ).read_text(encoding="utf-8")
        trozo = codigo[codigo.index("def _repintar_si_cambio_la_temporada"):][:700]
        self.assertIn("_temporada_vista", trozo)
        self.assertIn("return", trozo)
