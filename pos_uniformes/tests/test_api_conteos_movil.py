"""Contar desde el celular: la API de la hoja sin papel."""

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
from pos_uniformes.database.models import ConteoInventario, ConteoJornada, Empleada, Variante
from pos_uniformes.tests.test_conteo_jornada_service import _seed

_TIENDA = patch("pos_uniformes.api.routers.movil._modo_servidor", return_value="tienda")


class ApiConteosMovilTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        s = self.session
        s.add_all([
            Empleada(codigo="VEND-1", nombre_completo="Daniel Fabian", activo=True),
            Empleada(codigo="VEND-4", nombre_completo="Stayce Chavarria", activo=True),
            Empleada(codigo="VEND-5", nombre_completo="Fanny Ortiz", activo=True),
        ])
        self.escuela = _seed(s, "Uno")    # 2 prendas × 2 tallas
        s.commit()
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

    def _abrir(self, codigo="VEND-4") -> dict:
        self._como(codigo)
        r = self.client.post("/api/v1/movil/conteos", json={"escuela_id": self.escuela.id})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_listar_trae_escuelas_y_basicos_para_empezar(self) -> None:
        self._como("VEND-4")
        data = self.client.get("/api/v1/movil/conteos").json()
        self.assertEqual(data["modo"], "tienda")
        self.assertEqual(data["abiertas"], [])
        self.assertEqual([e["nombre"] for e in data["escuelas"]], ["Uno"])
        self.assertIn("toca", data["escuelas"][0])

    def test_abrir_devuelve_la_hoja_numerada_sin_stock_del_sistema(self) -> None:
        hoja = self._abrir()
        self.assertEqual(hoja["jornada"]["titulo"], "Uno")
        self.assertEqual(hoja["jornada"]["empleada_code"], "VEND-4")
        self.assertEqual(len(hoja["prendas"]), 2)
        p = hoja["prendas"][0]
        self.assertEqual((p["numero"], p["total"]), (1, 2))
        self.assertEqual([t["talla"] for t in p["tallas"]], ["6", "8"])
        self.assertTrue(all(t["fisico"] is None for t in p["tallas"]))
        self.assertNotIn("stock_sistema", str(hoja))
        self.assertNotIn("stock_actual", str(hoja))

    def test_sin_escuela_ni_prenda_no_abre(self) -> None:
        self._como("VEND-4")
        r = self.client.post("/api/v1/movil/conteos", json={"escuela_id": None, "tipo_pieza": ""})
        self.assertEqual(r.status_code, 422)

    def test_guardar_como_en_la_hoja_y_seguir_despues(self) -> None:
        hoja = self._abrir()
        jid = hoja["jornada"]["id"]
        v = hoja["prendas"][0]["tallas"]
        r = self.client.post(f"/api/v1/movil/conteos/{jid}/tallas", json={"items": [
            {"variante_id": v[0]["variante_id"], "fisico": 7, "pedido": 3},
            {"variante_id": v[1]["variante_id"], "fisico": None},
        ]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["guardadas"], 1)
        self.assertEqual(r.json()["avance"]["tallas_hechas"], 1)

        # Cerrar el celular y volver: la hoja trae lo capturado.
        de_nuevo = self.client.get(f"/api/v1/movil/conteos/{jid}").json()
        t0 = de_nuevo["prendas"][0]["tallas"][0]
        self.assertEqual((t0["fisico"], t0["pedido"]), (7, 3))
        self.assertIsNone(de_nuevo["prendas"][0]["tallas"][1]["fisico"])
        # Y aparece entre las abiertas como mía.
        lista = self.client.get("/api/v1/movil/conteos").json()
        self.assertEqual(lista["abiertas"][0]["id"], jid)
        self.assertTrue(lista["abiertas"][0]["mia"])

    def test_corregir_no_duplica_y_el_inventario_no_se_toca(self) -> None:
        hoja = self._abrir()
        jid = hoja["jornada"]["id"]
        vid = hoja["prendas"][0]["tallas"][0]["variante_id"]
        self.client.post(f"/api/v1/movil/conteos/{jid}/tallas", json={"items": [{"variante_id": vid, "fisico": 7}]})
        self.client.post(f"/api/v1/movil/conteos/{jid}/tallas", json={"items": [{"variante_id": vid, "fisico": 9}]})
        renglones = list(self.session.scalars(select(ConteoInventario).where(ConteoInventario.jornada_id == jid)).all())
        self.assertEqual(len(renglones), 1)
        self.assertEqual(renglones[0].stock_fisico, 9)
        self.assertEqual(self.session.get(Variante, vid).stock_actual, 10)   # intacto

    def test_terminar_cierra_y_queda_para_daniel(self) -> None:
        hoja = self._abrir()
        jid = hoja["jornada"]["id"]
        vid = hoja["prendas"][0]["tallas"][0]["variante_id"]
        self.client.post(f"/api/v1/movil/conteos/{jid}/tallas", json={"items": [{"variante_id": vid, "fisico": 7}]})
        r = self.client.post(f"/api/v1/movil/conteos/{jid}/terminar")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Daniel", r.json()["mensaje"])
        self.assertIsNotNone(self.session.get(ConteoJornada, jid).terminada_at)
        # Ya terminada: no se puede seguir guardando.
        r = self.client.post(f"/api/v1/movil/conteos/{jid}/tallas", json={"items": [{"variante_id": vid, "fisico": 1}]})
        self.assertEqual(r.status_code, 409)

    def test_la_jornada_de_otra_no_se_toca_pero_daniel_si_puede(self) -> None:
        hoja = self._abrir("VEND-4")
        jid = hoja["jornada"]["id"]
        vid = hoja["prendas"][0]["tallas"][0]["variante_id"]
        self._como("VEND-5")
        self.assertEqual(self.client.get(f"/api/v1/movil/conteos/{jid}").status_code, 403)
        r = self.client.post(f"/api/v1/movil/conteos/{jid}/tallas", json={"items": [{"variante_id": vid, "fisico": 1}]})
        self.assertEqual(r.status_code, 403)
        lista = self.client.get("/api/v1/movil/conteos").json()
        self.assertFalse(lista["abiertas"][0]["mia"])
        self._como("VEND-1")
        self.assertEqual(self.client.get(f"/api/v1/movil/conteos/{jid}").status_code, 200)

    def test_en_casa_se_puede_ver_pero_no_contar(self) -> None:
        hoja = self._abrir()
        jid = hoja["jornada"]["id"]
        self._tienda.stop()
        with patch("pos_uniformes.api.routers.movil._modo_servidor", return_value="casa"):
            self.assertEqual(self.client.get("/api/v1/movil/conteos").json()["modo"], "casa")
            r = self.client.post(f"/api/v1/movil/conteos/{jid}/tallas", json={"items": []})
            self.assertEqual(r.status_code, 409)
            self.assertEqual(self.client.post("/api/v1/movil/conteos", json={"escuela_id": self.escuela.id}).status_code, 409)
        self._tienda.start()

    def test_jornada_inexistente(self) -> None:
        self._como("VEND-4")
        self.assertEqual(self.client.get("/api/v1/movil/conteos/9999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
