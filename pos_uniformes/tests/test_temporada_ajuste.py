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
