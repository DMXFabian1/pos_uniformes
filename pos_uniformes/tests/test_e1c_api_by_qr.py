"""E1-C4 (T-N10): `GET /api/v1/clients/by-qr/{codigo}` sobre el modelo nuevo.

SQLite en memoria; no toca ninguna base real.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.main import app
from pos_uniformes.database.models import Cliente, ClienteTipo, NivelLealtad, TipoCliente, Usuario


class ApiByQrE1C4Tests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        for tabla in (Usuario.__table__, ClienteTipo.__table__, Cliente.__table__):
            tabla.create(engine)
        self.session = sessionmaker(bind=engine)()
        docente = ClienteTipo(id=2, clave="DOCENTE", nombre="Docente", orden=2)
        self.session.add(docente)

        def cliente(codigo, *, activo=True, archivado=False, tipo_id=None):
            return Cliente(codigo_cliente=codigo, nombre=f"Cliente {codigo}", tipo_cliente=TipoCliente.MAYORISTA,
                           descuento_preferente=Decimal("20.00"), nivel_lealtad=NivelLealtad.MAYORISTA,
                           telefono="6671234567", activo=activo, tipo_cliente_id=tipo_id,
                           archivado_en=datetime.now(timezone.utc) if archivado else None)

        self.session.add_all([
            cliente("CLI-OK1", tipo_id=2),
            cliente("CLI-SIN1"),
            cliente("CLI-INA1", activo=False),
            cliente("CLI-ARC1", activo=False, archivado=True),
        ])
        self.session.commit()
        app.dependency_overrides[get_db] = lambda: self.session
        app.dependency_overrides[get_current_employee] = lambda: (SimpleNamespace(codigo="VEND-1"), None)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()

    def test_respuesta_sin_nivel_ni_descuento_y_telefono_enmascarado(self) -> None:
        r = self.client.get("/api/v1/clients/by-qr/cli-ok1")
        self.assertEqual(r.status_code, 200, r.text)
        datos = r.json()
        self.assertEqual(set(datos), {"id", "codigo_cliente", "nombre", "tipo", "telefono_enmascarado"})
        self.assertEqual(datos["tipo"], "Docente")
        self.assertNotIn("6671234567", r.text)
        self.assertEqual(datos["telefono_enmascarado"], "•••• ••45 67")
        for prohibido in ("nivel", "descuento", "MAYORISTA", "20.00"):
            self.assertNotIn(prohibido, r.text)

    def test_sin_tipo_responde_null(self) -> None:
        r = self.client.get("/api/v1/clients/by-qr/CLI-SIN1")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(r.json()["tipo"])

    def test_inactivo_archivado_e_inexistente_dan_404(self) -> None:
        for codigo in ("CLI-INA1", "CLI-ARC1", "CLI-NOEXISTE"):
            with self.subTest(codigo=codigo):
                r = self.client.get(f"/api/v1/clients/by-qr/{codigo}")
                self.assertEqual(r.status_code, 404, r.text)
                self.assertNotIn("Cliente CLI", r.text)


if __name__ == "__main__":
    unittest.main()
