"""La base de prueba por proceso de xdist (tests/base_por_trabajador.py).

Protege el arreglo de la falla intermitente del informe de finanzas
(2026-11-11): con `-n 6` los procesos compartían `pos_uniformes_test` y el
informe sumaba las ventas que otra prueba estaba escribiendo.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from pos_uniformes.utils.config import settings
from tests import base_por_trabajador as bpt

_AHORA = 1_800_000_000  # 2027-01-15, fijo


class NombresTests(unittest.TestCase):
    def test_nombres_terminan_en_test_y_son_locales_a_la_corrida(self) -> None:
        corrida = bpt.nueva_corrida(_AHORA)
        self.assertRegex(corrida, r"^1800000000_[0-9a-f]{6}$")
        gw0 = bpt.nombre_base_trabajador(corrida, "gw0")
        gw1 = bpt.nombre_base_trabajador(corrida, "gw1")
        plantilla = bpt.nombre_plantilla(corrida)
        self.assertNotEqual(gw0, gw1)
        for nombre in (gw0, gw1, plantilla):
            self.assertTrue(nombre.endswith("_test"), nombre)  # la red de conftest no cambia
            self.assertLessEqual(len(nombre), 63)               # límite de Postgres
            self.assertTrue(bpt.es_temporal_de_prueba(nombre))
            self.assertTrue(bpt.es_de_la_corrida(nombre, corrida))
        self.assertFalse(bpt.es_de_la_corrida(gw0, bpt.nueva_corrida(_AHORA)))

    def test_dos_corridas_no_comparten_nombres(self) -> None:
        a, b = bpt.nueva_corrida(_AHORA), bpt.nueva_corrida(_AHORA)
        self.assertNotEqual(bpt.nombre_base_trabajador(a, "gw0"), bpt.nombre_base_trabajador(b, "gw0"))

    def test_rechaza_nombres_raros(self) -> None:
        with self.assertRaises(ValueError):
            bpt.nombre_base_trabajador("1800000000_abcdef", "gw0; DROP DATABASE x")
        with self.assertRaises(ValueError):
            bpt.nombre_plantilla("cualquiera")

    def test_nunca_toca_la_base_fuente_ni_otras(self) -> None:
        for nombre in ("pos_uniformes_test", "pos_uniformes", "pos_uniformes_copia",
                       "pos_uniformes_test_e1a_19b25189", "pos_uniformes_tmp_x_test"):
            self.assertFalse(bpt.es_temporal_de_prueba(nombre), nombre)
            self.assertFalse(bpt.es_vieja(nombre, _AHORA + 10**6), nombre)
            with self.assertRaises(ValueError):
                bpt.borrar("postgresql+psycopg://postgres@127.0.0.1/postgres", nombre)

    def test_vieja_a_partir_de_12_horas(self) -> None:
        nombre = bpt.nombre_base_trabajador(bpt.nueva_corrida(_AHORA), "gw3")
        self.assertFalse(bpt.es_vieja(nombre, _AHORA + 11 * 3600))
        self.assertTrue(bpt.es_vieja(nombre, _AHORA + 13 * 3600))

    def test_base_de_prueba_local(self) -> None:
        corrida = bpt.nueva_corrida(_AHORA)
        url = make_url("postgresql+psycopg://postgres@127.0.0.1/pos_uniformes_test")
        self.assertTrue(bpt.es_base_de_prueba_local(url))
        self.assertTrue(bpt.es_base_de_prueba_local(url.set(database=bpt.nombre_base_trabajador(corrida, "gw2"))))
        self.assertFalse(bpt.es_base_de_prueba_local(url.set(database=bpt.nombre_plantilla(corrida))))
        self.assertFalse(bpt.es_base_de_prueba_local(url.set(database="pos_uniformes")))
        self.assertFalse(bpt.es_base_de_prueba_local(url.set(host="192.168.0.99")))

    def test_que_base_le_toca_a_cada_proceso(self) -> None:
        sin_xdist: dict = {}
        self.assertEqual(bpt.base_para_este_proceso(sin_xdist), "pos_uniformes_test")
        corrida = sin_xdist[bpt.ENV_CORRIDA]
        gw = {bpt.ENV_CORRIDA: corrida, bpt.ENV_TRABAJADOR: "gw4"}
        primero = bpt.base_para_este_proceso(gw)
        self.assertEqual(primero, bpt.nombre_base_trabajador(corrida, "gw4"))
        self.assertEqual(bpt.base_para_este_proceso(gw), primero)  # conftest se importa dos veces


class EsteProcesoTests(unittest.TestCase):
    """Lo que de verdad quedó configurado en el proceso que corre esto."""

    def test_usa_la_base_que_le_toca(self) -> None:
        trabajador = os.environ.get(bpt.ENV_TRABAJADOR)
        if trabajador:
            esperado = bpt.nombre_base_trabajador(os.environ[bpt.ENV_CORRIDA], trabajador)
        else:
            esperado = bpt.BASE_FUENTE
        self.assertEqual(settings.db_name, esperado)
        self.assertTrue(bpt.es_base_de_prueba_local(make_url(settings.database_url)))
        from pos_uniformes.database.connection import engine

        with engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT current_database()")).scalar(), esperado)


class CopiaYBorradoTests(unittest.TestCase):
    """Dos copias de la plantilla son bases distintas: lo de una no está en la otra."""

    def setUp(self) -> None:
        self.url = settings.database_url
        self.corrida = bpt.nueva_corrida()
        self.addCleanup(bpt.limpiar, self.url, corrida=self.corrida)
        self.a = bpt.nombre_base_trabajador(self.corrida, "gw90")
        self.b = bpt.nombre_base_trabajador(self.corrida, "gw91")
        # La base de este proceso está en uso (por él mismo): se copia a una
        # plantilla propia con pg_dump —el camino de respaldo cuando la fuente
        # está ocupada— y de esa plantilla, que nadie usa, salen las dos copias.
        fuente = bpt.nombre_plantilla(self.corrida)
        bpt.crear_desde(self.url, fuente, settings.db_name, intentos=0)
        bpt.crear_desde(self.url, self.a, fuente)
        bpt.crear_desde(self.url, self.b, fuente)

    def _motor(self, nombre):
        motor = create_engine(make_url(self.url).set(database=nombre))
        self.addCleanup(motor.dispose)
        return motor

    def test_lo_escrito_en_una_copia_no_aparece_en_la_otra(self) -> None:
        marca = f"AISLA-{uuid.uuid4().hex[:8]}"
        with self._motor(self.a).begin() as conn:
            conn.execute(text("INSERT INTO caja_retiro (monto, motivo, creado_por, created_at) "
                              "VALUES (1, :m, 'gw90', now())"), {"m": marca})
        contar = text("SELECT count(*) FROM caja_retiro WHERE motivo = :m")
        with self._motor(self.a).connect() as conn:
            self.assertEqual(conn.execute(contar, {"m": marca}).scalar(), 1)
        with self._motor(self.b).connect() as conn:
            self.assertEqual(conn.execute(contar, {"m": marca}).scalar(), 0)
        from pos_uniformes.database.connection import engine

        with engine.connect() as conn:  # ni en la base de este proceso
            self.assertEqual(conn.execute(contar, {"m": marca}).scalar(), 0)

    def test_limpiar_borra_solo_lo_de_la_corrida(self) -> None:
        self.assertTrue(bpt.existe(self.url, self.a))
        borradas = bpt.limpiar(self.url, corrida=self.corrida)
        self.assertIn(self.a, borradas)
        self.assertIn(self.b, borradas)
        self.assertTrue(all(bpt.es_de_la_corrida(n, self.corrida) for n in borradas))
        self.assertFalse(bpt.existe(self.url, self.a))
        self.assertTrue(bpt.existe(self.url, bpt.BASE_FUENTE))
        self.assertTrue(bpt.existe(self.url, settings.db_name))


class CorridaConcurrenteTests(unittest.TestCase):
    """Un pytest aparte con -n 2: cada proceso escribe, confirma y cuenta todo."""

    def test_dos_procesos_no_se_ven(self) -> None:
        aqui = Path(__file__).resolve().parent.parent
        from pos_uniformes.database.connection import engine

        engine.dispose()  # sin conexiones de este proceso, la copia no espera
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("PYTEST_XDIST") and k not in {bpt.ENV_CORRIDA, "PYTEST_CURRENT_TEST"}}
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/_ayuda_aislamiento_trabajadores.py",
             "-n", "2", "--dist", "load", "-q", "-p", "no:cacheprovider"],
            cwd=aqui, env=env, capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL,
        )
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertIn("8 passed", r.stdout)


if __name__ == "__main__":
    unittest.main()
