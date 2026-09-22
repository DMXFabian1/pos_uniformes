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

    # ── Cómo va cada escuela, desde el celular ─────────────────────────────

    def test_escuelas_trae_el_estado_y_lo_urgente_primero(self) -> None:
        self._como("VEND-1")
        data = self.client.get("/api/v1/movil/conteos/escuelas").json()
        filas = data["escuelas"]
        self.assertEqual([f["nombre"] for f in filas], ["Uno"])
        fila = filas[0]
        # No se recalcula nada aquí: es lo que dice el servicio.
        for campo in ("salud", "titular", "pct_al_dia", "agotadas", "vendido", "ultimo"):
            self.assertIn(campo, fila)

    def test_lo_rojo_va_antes_que_lo_verde(self) -> None:
        from pos_uniformes.database.models import Escuela

        otra = _seed(self.session, "Dos")
        # A la de abajo le dejamos una talla diciendo que hay menos que nada.
        talla = self.session.scalars(
            select(Variante).join(Variante.producto).where(
                Variante.producto.has(escuela_id=otra.id)
            )
        ).first()
        talla.stock_actual = -2
        self.session.commit()

        self._como("VEND-1")
        filas = self.client.get("/api/v1/movil/conteos/escuelas").json()["escuelas"]
        self.assertEqual(filas[0]["nombre"], "Dos")
        self.assertEqual(filas[0]["salud"], "rojo")
        self.assertEqual(self.session.get(Escuela, otra.id).nombre, "Dos")

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

    def test_cualquiera_sigue_la_jornada_y_cada_talla_dice_quien(self) -> None:
        # Fanny imprime con la sesión de Ana y luego captura con la suya: da igual.
        hoja = self._abrir("VEND-4")
        jid = hoja["jornada"]["id"]
        vid = hoja["prendas"][0]["tallas"][0]["variante_id"]
        self._como("VEND-5")
        self.assertEqual(self.client.get(f"/api/v1/movil/conteos/{jid}").status_code, 200)
        r = self.client.post(f"/api/v1/movil/conteos/{jid}/tallas", json={"items": [{"variante_id": vid, "fisico": 1}]})
        self.assertEqual(r.status_code, 200, r.text)
        renglon = self.session.scalars(select(ConteoInventario).where(ConteoInventario.jornada_id == jid)).one()
        self.assertIn("VEND-5", renglon.contado_por)
        lista = self.client.get("/api/v1/movil/conteos").json()
        self.assertTrue(lista["abiertas"][0]["mia"])

    def test_lo_que_otra_capturo_con_otro_numero_no_se_pisa_sin_reemplazar(self) -> None:
        hoja = self._abrir("VEND-4")
        jid = hoja["jornada"]["id"]
        vid = hoja["prendas"][0]["tallas"][0]["variante_id"]
        self.client.post(f"/api/v1/movil/conteos/{jid}/tallas", json={"items": [{"variante_id": vid, "fisico": 5}]})
        self._como("VEND-5")
        r = self.client.post(f"/api/v1/movil/conteos/{jid}/tallas", json={"items": [{"variante_id": vid, "fisico": 7}]}).json()
        self.assertEqual(r["guardadas"], 0)
        c = r["conflictos"][0]
        self.assertEqual((c["variante_id"], c["quien"], c["fisico_suyo"], c["fisico_tuyo"]), (vid, "Stayce", 5, 7))
        # La hoja dice quién la capturó.
        hoja = self.client.get(f"/api/v1/movil/conteos/{jid}").json()
        self.assertEqual(hoja["prendas"][0]["tallas"][0]["quien"], "Stayce")
        self.assertEqual(hoja["prendas"][0]["tallas"][0]["fisico"], 5)
        # Con reemplazar=true gana lo de Fanny.
        r = self.client.post(f"/api/v1/movil/conteos/{jid}/tallas", json={"items": [{"variante_id": vid, "fisico": 7}], "reemplazar": True}).json()
        self.assertEqual((r["guardadas"], r["conflictos"]), (1, []))
        renglon = self.session.scalars(select(ConteoInventario).where(ConteoInventario.jornada_id == jid)).one()
        self.assertEqual((renglon.stock_fisico, renglon.contado_por), (7, "Fanny Ortiz (VEND-5)"))

    def test_una_sola_jornada_por_escuela_la_segunda_sigue_la_primera(self) -> None:
        hoja = self._abrir("VEND-4")
        jid = hoja["jornada"]["id"]
        # La lista marca la escuela como en proceso.
        lista = self.client.get("/api/v1/movil/conteos").json()
        self.assertEqual(lista["escuelas"][0]["en_proceso"]["jornada_id"], jid)
        self.assertEqual(lista["escuelas"][0]["en_proceso"]["quien"], "Stayce Chavarria")
        # Otra empleada intenta abrir la misma: recibe la que ya existe, marcada.
        self._como("VEND-5")
        r = self.client.post("/api/v1/movil/conteos", json={"escuela_id": self.escuela.id})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["jornada"]["id"], jid)
        self.assertEqual(r.json()["en_proceso"]["quien"], "Stayce Chavarria")
        self.assertEqual(len(self.session.scalars(select(ConteoJornada)).all()), 1)

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


class UltimoConteoEnLaListaTests(ApiConteosMovilTests):
    """Cada escuela dice cuándo se contó, para no contar la misma a cada rato."""

    def test_nunca_contada(self) -> None:
        self._como("VEND-4")
        e = self.client.get("/api/v1/movil/conteos").json()["escuelas"][0]
        self.assertEqual(e["ultimo"], {"texto": "nunca", "dias": None, "quien": "", "reciente": False})

    def test_despues_de_terminar_dice_hoy_y_quien(self) -> None:
        hoja = self._abrir("VEND-4")
        jid = hoja["jornada"]["id"]
        vid = hoja["prendas"][0]["tallas"][0]["variante_id"]
        self.client.post(f"/api/v1/movil/conteos/{jid}/tallas", json={"items": [{"variante_id": vid, "fisico": 7}]})
        self.client.post(f"/api/v1/movil/conteos/{jid}/terminar")
        e = self.client.get("/api/v1/movil/conteos").json()["escuelas"][0]
        self.assertEqual(e["ultimo"]["dias"], 0)
        self.assertEqual(e["ultimo"]["quien"], "Stayce Chavarria")
        self.assertEqual(e["ultimo"]["texto"], "hoy (Stayce)")
        self.assertTrue(e["ultimo"]["reciente"])   # el celular la esconde hasta "Ver todas"

    def test_una_escuela_nunca_contada_no_lleva_alerta_y_una_vencida_si(self) -> None:
        # ⚠ solo para las que ya se contaron y se les pasó la vigencia: si todo trae ⚠, nada destaca.
        from types import SimpleNamespace
        from unittest.mock import patch

        self._como("VEND-4")
        eid = self.escuela.id
        r = self.client.get("/api/v1/movil/conteos").json()
        self.assertFalse(next(e for e in r["escuelas"] if e["escuela_id"] == eid)["toca"])   # nunca contada
        vencida = [SimpleNamespace(escuela_id=eid, dias_para_vencer=-3)]
        with patch("pos_uniformes.services.conteo_calendario_service.escuelas_con_conteo_vencido", return_value=vencida):
            r = self.client.get("/api/v1/movil/conteos").json()
        self.assertTrue(next(e for e in r["escuelas"] if e["escuela_id"] == eid)["toca"])

    def test_los_basicos_traen_sus_prendas_y_se_puede_contar_una_sola(self) -> None:
        # Daniel (2026-09-14): "a veces no quiero contar todos los pantalones, solo un tipo o un color".
        from pos_uniformes.tests.test_conteo_jornada_service import _seed_basicos

        gris, azul = _seed_basicos(self.session, self.escuela, "Pantalón")
        self.session.commit()
        self._como("VEND-4")
        basicos = self.client.get("/api/v1/movil/conteos").json()["basicos"]
        pant = next(b for b in basicos if b["tipo_pieza"] == "Pantalón")
        self.assertEqual([p["corto"] for p in pant["prendas"]], ["Pantalón Azul Escolar", "Pantalón Gris Escolar"])
        self.assertEqual(pant["prendas"][0]["ultimo"]["texto"], "nunca")
        # Abrir solo la gris: la hoja trae una prenda, y el tipo dice que la gris está en proceso.
        r = self.client.post("/api/v1/movil/conteos", json={"escuela_id": None, "tipo_pieza": "Pantalón", "prenda": gris})
        self.assertEqual(r.status_code, 200, r.text)
        hoja = r.json()
        self.assertEqual([p["nombre"] for p in hoja["prendas"]], ["Pantalón Gris Escolar"])
        basicos = self.client.get("/api/v1/movil/conteos").json()["basicos"]
        pant = next(b for b in basicos if b["tipo_pieza"] == "Pantalón")
        por_nombre = {p["nombre"]: p for p in pant["prendas"]}
        self.assertEqual(por_nombre[gris]["en_proceso"]["quien"], "Stayce Chavarria")
        self.assertIsNone(por_nombre[azul]["en_proceso"])
        self.assertIsNone(pant["en_proceso"])   # "todas" sigue libre

    def test_los_basicos_tambien_traen_su_fecha(self) -> None:
        self._como("VEND-4")
        basicos = self.client.get("/api/v1/movil/conteos").json()["basicos"]
        for b in basicos:
            self.assertIn("tipo_pieza", b)
            self.assertIn("ultimo", b)
