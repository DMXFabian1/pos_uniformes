"""API de bodega desde el celular: solo el dueño; llegó mercancía y pasar al piso."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.main import app
from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import BodegaUbicacion, Empleada, Variante
from pos_uniformes.tests.test_conteo_jornada_service import _seed

_TIENDA = patch("pos_uniformes.api.routers.movil._modo_servidor", return_value="tienda")


class ApiBodegaMovilTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        s = self.session
        s.add_all([
            Empleada(codigo="VEND-1", nombre_completo="Daniel Fabian", activo=True),
            Empleada(codigo="VEND-4", nombre_completo="Stayce Chavarria", activo=True),
            BodegaUbicacion(codigo="ALMACEN-N1", rack="ALMACEN", nivel=1),
        ])
        _seed(s, "Uno", stock=10)
        s.commit()
        self.v = list(s.scalars(select(Variante).order_by(Variante.id)).all())
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app)
        self._tienda = _TIENDA
        self._tienda.start()

    def tearDown(self) -> None:
        self._tienda.stop()
        app.dependency_overrides.clear()
        self.session.close()

    def _como(self, codigo: str) -> None:
        emp = self.session.query(Empleada).filter(Empleada.codigo == codigo).one()
        app.dependency_overrides[get_current_employee] = lambda: (emp, None)

    def test_una_empleada_no_entra(self) -> None:
        self._como("VEND-4")
        self.assertEqual(self.client.get("/api/v1/movil/bodega/cajas").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/movil/bodega/prendas?q=prenda").status_code, 403)
        r = self.client.post("/api/v1/movil/bodega/llego", json={"items": [{"variante_id": self.v[0].id, "cantidad": 1}], "caja_nueva": True})
        self.assertEqual(r.status_code, 403)

    def test_llego_y_pasar_al_piso(self) -> None:
        self._como("VEND-1")
        prendas = self.client.get("/api/v1/movil/bodega/prendas?q=prenda 0").json()["prendas"]
        self.assertEqual(len(prendas), 1)
        vid = prendas[0]["tallas"][0]["variante_id"]
        r = self.client.post("/api/v1/movil/bodega/llego", json={
            "items": [{"variante_id": vid, "cantidad": 12, "a_caja": 9}], "caja_nueva": True, "referencia": "Maquilador",
        })
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["piezas"], r.json()["tallas"], r.json()["al_piso"], r.json()["en_caja"]), (12, 1, 3, 9))
        caja_id = r.json()["caja_id"]
        cajas = self.client.get("/api/v1/movil/bodega/cajas").json()["cajas"]
        self.assertEqual((cajas[0]["id"], cajas[0]["piezas"]), (caja_id, 9))
        contenido = self.client.get(f"/api/v1/movil/bodega/cajas/{caja_id}").json()["contenido"]
        self.assertEqual((contenido[0]["variante_id"], contenido[0]["cantidad"]), (vid, 9))
        r = self.client.post("/api/v1/movil/bodega/piso", json={"caja_id": caja_id, "items": [{"variante_id": vid, "cantidad": 5}]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["quedan"], 4)
        self.session.expire_all()
        self.assertEqual(self.session.get(Variante, vid).stock_actual, 22)

    def test_todo_al_piso_no_abre_caja(self) -> None:
        self._como("VEND-1")
        r = self.client.post("/api/v1/movil/bodega/llego", json={"items": [{"variante_id": self.v[0].id, "cantidad": 3}]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["al_piso"], r.json()["en_caja"], r.json()["caja_id"]), (3, 0, None))
        self.assertEqual(self.client.get("/api/v1/movil/bodega/cajas").json()["cajas"], [])

    def test_sin_piezas_es_422_con_mensaje(self) -> None:
        self._como("VEND-1")
        r = self.client.post("/api/v1/movil/bodega/llego", json={"items": [{"variante_id": self.v[0].id, "cantidad": 0}], "caja_nueva": True})
        self.assertEqual(r.status_code, 422)
        self.assertIn("No hay piezas", r.json()["detail"]["error"]["message"])

    def test_corregir_caja(self) -> None:
        self._como("VEND-1")
        vid = self.v[0].id
        r = self.client.post("/api/v1/movil/bodega/llego", json={"items": [{"variante_id": vid, "cantidad": 9, "a_caja": 9}], "caja_nueva": True}).json()
        r = self.client.post("/api/v1/movil/bodega/corregir", json={"caja_id": r["caja_id"], "items": [{"variante_id": vid, "cantidad": 4}]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["cambios"], r.json()["quedan"]), (1, 4))
        self._como("VEND-4")
        r = self.client.post("/api/v1/movil/bodega/corregir", json={"caja_id": 1, "items": []})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
