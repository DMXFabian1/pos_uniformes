"""E4-E: el escáner de la PWA ve el programa activo del cliente.

SQLite en memoria; no toca ninguna base real.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.main import app
from pos_uniformes.database.models import Cliente, ClienteTipo, Membresia, Programa, Usuario


class ApiByQrProgramaTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        for tabla in (Usuario.__table__, ClienteTipo.__table__, Cliente.__table__, Programa.__table__, Membresia.__table__):
            tabla.create(engine)
        self.session = sessionmaker(bind=engine)()
        club = Programa(id=1, clave="CLUB", nombre="Maximoda Club", estado="activo", ingreso_modo="directo_empleada")
        prof = Programa(id=2, clave="PROFESIONAL", nombre="Maximoda Profesional", estado="activo",
                        ingreso_modo="aprobacion_dueno", tipo_sugerido_clave="DOCENTE")
        self.session.add_all([club, prof])
        for i, codigo in enumerate(("CLI-CLUB", "CLI-ESPERA", "CLI-NADA", "CLI-SALIO"), start=1):
            self.session.add(Cliente(id=i, codigo_cliente=codigo, nombre=f"Cliente {codigo}", activo=True))
        self.session.flush()
        self.session.add_all([
            Membresia(cliente_id=1, programa_id=1, estado="activa"),
            Membresia(cliente_id=2, programa_id=1, estado="activa"),
            Membresia(cliente_id=2, programa_id=2, estado="pendiente"),
            Membresia(cliente_id=4, programa_id=1, estado="cancelada"),
        ])
        self.session.commit()
        app.dependency_overrides[get_db] = lambda: self.session
        app.dependency_overrides[get_current_employee] = lambda: (SimpleNamespace(codigo="VEND-1"), None)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()

    def _programa(self, codigo):
        r = self.client.get(f"/api/v1/clients/by-qr/{codigo}")
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["programa"]

    def test_muestra_solo_el_programa_activo(self) -> None:
        self.assertEqual(self._programa("cli-club"), "Maximoda Club")
        self.assertEqual(self._programa("CLI-ESPERA"), "Maximoda Club", "la propuesta pendiente no se muestra")
        self.assertIsNone(self._programa("CLI-NADA"))
        self.assertIsNone(self._programa("CLI-SALIO"), "una membresía cancelada ya no cuenta")

    def test_sin_porcentajes_ni_beneficios(self) -> None:
        texto = self.client.get("/api/v1/clients/by-qr/CLI-CLUB").text
        for prohibido in ("%", "descuento", "beneficio", "pendiente"):
            self.assertNotIn(prohibido, texto)


class PwaEscanerTests(unittest.TestCase):
    def test_el_escaner_pinta_la_etiqueta_si_viene(self) -> None:
        from pathlib import Path

        jsx = (Path(__file__).resolve().parents[2] / "pwa" / "src" / "screens" / "ScannerScreen.jsx").read_text(encoding="utf-8")
        self.assertIn("{result.data.programa && (", jsx)
        self.assertIn("★ {result.data.programa}", jsx)


if __name__ == "__main__":
    unittest.main()
