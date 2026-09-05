"""Tests de la API móvil Fase 1 (solo lectura) y del snapshot SQLite.

La app FastAPI se prueba con TestClient y una base SQLite en memoria via
dependency_overrides — sin tocar Postgres.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.main import app
from pos_uniformes.database.models import (
    Empleada,
    EmpleadaEvento,
    EmpleadaHorario,
    LibretaCorte,
    LibretaVenta,
)

_TABLAS = (Empleada, EmpleadaHorario, EmpleadaEvento, LibretaCorte, LibretaVenta)


class ApiMovilTests(unittest.TestCase):
    def setUp(self) -> None:
        # TestClient corre la app en otro hilo: sqlite necesita permitirlo.
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}
        )
        for t in _TABLAS:
            t.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()
        self._sembrar()
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()

    def _sembrar(self) -> None:
        s = self.session
        s.add_all(
            [
                Empleada(codigo="VEND-1", nombre_completo="Daniel Fabian", activo=True),
                Empleada(codigo="ENC-1", nombre_completo="León Fabian", activo=True),
                Empleada(codigo="VEND-4", nombre_completo="Fanny Ortiz", activo=True),
            ]
        )
        s.add(
            EmpleadaHorario(
                employee_code="VEND-4", descanso_weekday=3,
                ciclo_dias_pago=7, fecha_ultimo_pago=date.today(),
            )
        )
        s.add(
            LibretaVenta(
                employee_code="VEND-4", employee_name="Fanny", tipo="venta",
                piezas=2, comisiones=2, monto_total=Decimal("500.00"),
                monto_neto=Decimal("500.00"), detalle=[],
                created_at=datetime.now(),
            )
        )
        s.add(
            LibretaCorte(
                fecha=date.today(), monto_final=Decimal("17180.00"),
                operaciones=29, piezas=76, creado_por="VEND-1",
            )
        )
        s.commit()

    def _como(self, codigo: str) -> None:
        emp = (
            self.session.query(Empleada).filter(Empleada.codigo == codigo).one()
        )
        app.dependency_overrides[get_current_employee] = lambda: (emp, None)

    def test_empleada_ve_su_banner_y_calendario(self) -> None:
        self._como("VEND-4")
        data = self.client.get("/api/v1/movil/inicio").json()
        self.assertEqual(data["rol"], "empleada")
        self.assertEqual(data["nombre"], "Fanny")
        emp = data["empleada"]
        self.assertEqual(emp["comisiones_ciclo"], 0)  # pagada hoy: en ceros
        self.assertIsNotNone(emp["proximo_pago"])
        self.assertTrue(emp["calendario"]["dias"])  # el mes viene pintado
        # Su jueves fijo aparece pintado como descanso en el mes.
        self.assertIn("descanso", set(emp["calendario"]["dias"].values()))

    def test_encargado_ve_solo_cortes(self) -> None:
        self._como("ENC-1")
        data = self.client.get("/api/v1/movil/inicio").json()
        self.assertEqual(data["rol"], "encargado")
        self.assertEqual(len(data["cortes"]), 1)
        self.assertEqual(data["cortes"][0]["monto"], "17180.00")
        self.assertNotIn("dueno", data)
        self.assertNotIn("empleada", data)

    def test_dueno_ve_resumen_completo(self) -> None:
        self._como("VEND-1")
        data = self.client.get("/api/v1/movil/inicio").json()
        self.assertEqual(data["rol"], "dueno")
        d = data["dueno"]
        self.assertEqual(d["hoy"]["venta"], "500.00")
        self.assertEqual(d["hoy"]["piezas"], 2)
        self.assertEqual(d["ranking"][0]["codigo"], "VEND-4")
        self.assertEqual(d["ciclos"][0]["nombre"], "Fanny Ortiz")
        self.assertEqual(len(d["cortes"]), 1)

    def test_calendario_navegable(self) -> None:
        self._como("VEND-4")
        data = self.client.get("/api/v1/movil/calendario?year=2026&month=10").json()
        self.assertEqual(data["month"], 10)
        # Octubre 2026: los jueves (su descanso fijo) van pintados.
        self.assertEqual(data["dias"]["2026-10-01"], "descanso")  # jueves
        self.assertEqual(data["dias"]["2026-10-02"], "trabajo")

    def test_sin_token_da_401_o_403(self) -> None:
        app.dependency_overrides.pop(get_current_employee, None)
        r = self.client.get("/api/v1/movil/inicio")
        self.assertIn(r.status_code, (401, 403))


class SnapshotTests(unittest.TestCase):
    def test_exporta_y_el_snapshot_sirve_para_leer(self) -> None:
        import tempfile
        from pathlib import Path

        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import sessionmaker as _sm

        # Origen simulado: un sqlite con las tablas y algo de datos.
        origen = _ce("sqlite://")
        for t in _TABLAS:
            t.__table__.create(origen)
        ses = _sm(bind=origen)()
        ses.add(Empleada(codigo="VEND-4", nombre_completo="Fanny", activo=True))
        ses.add(
            LibretaCorte(
                fecha=date(2026, 9, 4), monto_final=Decimal("100.00"),
                operaciones=1, piezas=1, creado_por="VEND-1",
            )
        )
        ses.commit()

        with tempfile.TemporaryDirectory() as tmp, patch(
            "pos_uniformes.database.connection.engine", origen
        ):
            destino = Path(tmp) / "snap.sqlite"
            from pos_uniformes.scripts.exportar_snapshot_movil import exportar

            conteos = exportar(destino)
            self.assertEqual(conteos["empleada"], 1)
            self.assertEqual(conteos["libreta_corte"], 1)
            self.assertTrue(destino.exists())

            # El snapshot se puede leer con los mismos modelos.
            lector = _sm(bind=_ce(f"sqlite:///{destino}"))()
            self.assertEqual(lector.query(Empleada).count(), 1)
            corte = lector.query(LibretaCorte).one()
            self.assertEqual(corte.monto_final, Decimal("100.00"))
            lector.close()
        ses.close()


if __name__ == "__main__":
    unittest.main()
