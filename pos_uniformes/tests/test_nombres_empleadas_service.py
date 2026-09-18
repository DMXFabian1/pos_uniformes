"""Donde el sistema guarda VEND-1, en pantalla va el nombre."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Empleada
from pos_uniformes.services import nombres_empleadas_service as ne

NOMBRES = {"VEND-1": "Daniel Fabian", "VEND-3": "Ana López", "ENC-1": "María Pérez"}


class MostrarTests(unittest.TestCase):
    def test_codigo_solo(self) -> None:
        self.assertEqual(ne.mostrar("VEND-1", NOMBRES), "Daniel Fabian")
        self.assertEqual(ne.mostrar("vend-1", NOMBRES), "vend-1")   # solo mayúsculas, como se guardan

    def test_nombre_con_codigo_entre_parentesis_se_queda_con_el_nombre(self) -> None:
        self.assertEqual(ne.mostrar("Ana López (VEND-3)", NOMBRES), "Ana López")
        self.assertEqual(ne.mostrar("Ana López (VEND-3) · hoy", NOMBRES), "Ana López · hoy")

    def test_dentro_de_una_frase(self) -> None:
        self.assertEqual(ne.mostrar("Corte por VEND-1 a las 17:30", NOMBRES), "Corte por Daniel Fabian a las 17:30")
        self.assertEqual(ne.mostrar("Pago: ENC-1 → VEND-3", NOMBRES), "Pago: María Pérez → Ana López")

    def test_lo_que_no_es_codigo_conocido_no_se_toca(self) -> None:
        self.assertEqual(ne.mostrar("admin (satélite)", NOMBRES), "admin (satélite)")
        self.assertEqual(ne.mostrar("VEND-9", NOMBRES), "VEND-9")
        self.assertEqual(ne.mostrar("SKU-123 ABC-1", NOMBRES), "SKU-123 ABC-1")
        self.assertEqual(ne.mostrar(None, NOMBRES), "")
        self.assertEqual(ne.mostrar("", NOMBRES), "")

    def test_corto_es_el_primer_nombre(self) -> None:
        self.assertEqual(ne.mostrar("VEND-1", NOMBRES, corto=True), "Daniel")
        self.assertEqual(ne.mostrar("VEND-9", NOMBRES, corto=True), "VEND-9")
        self.assertEqual(ne.mostrar("Evelyn Ramírez", NOMBRES, corto=True), "Evelyn")
        self.assertEqual(ne.mostrar("Ana López (VEND-3)", NOMBRES, corto=True), "Ana")


class CacheYCopiaLocalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory(); self.addCleanup(self._dir.cleanup)
        p = patch.object(ne, "_ruta_local", return_value=Path(self._dir.name) / "n.json"); p.start(); self.addCleanup(p.stop)
        ne._cache = {}; ne._cache_en = 0.0
        engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add_all([Empleada(codigo="VEND-1", nombre_completo="Daniel Fabian", activo=True),
                        Empleada(codigo="VEND-7", nombre_completo="Ex Empleada", activo=False),
                        Empleada(codigo="VEND-8", nombre_completo="", activo=True)])
        self.s.commit()

    def test_lee_de_la_base_incluye_inactivas_y_guarda_copia_local(self) -> None:
        n = ne.nombres_por_codigo(self.s)
        self.assertEqual(n, {"VEND-1": "Daniel Fabian", "VEND-7": "Ex Empleada"})
        self.assertTrue((Path(self._dir.name) / "n.json").exists())
        self.assertEqual(ne.nombre_de("VEND-7", corto=True), "Ex")

    def test_sin_base_usa_la_copia_local(self) -> None:
        ne.nombres_por_codigo(self.s)
        ne._cache = {}; ne._cache_en = 0.0
        self.assertEqual(ne.nombres_por_codigo(None)["VEND-1"], "Daniel Fabian")

    def test_con_cache_no_vuelve_a_consultar(self) -> None:
        ne.nombres_por_codigo(self.s)
        with patch.object(self.s, "execute", side_effect=AssertionError("no debía consultar")):
            self.assertEqual(ne.nombres_por_codigo(self.s)["VEND-1"], "Daniel Fabian")
        ne.invalidar()
        self.s.add(Empleada(codigo="VEND-9", nombre_completo="Nueva", activo=True)); self.s.commit()
        self.assertEqual(ne.nombres_por_codigo(self.s)["VEND-9"], "Nueva")
