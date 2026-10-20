"""El celular nombra la ropa normal que entró con código, por el mismo camino que el POS."""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.main import app
from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    Empleada,
    Marca,
    Producto,
    RolUsuario,
    TipoPieza,
    Usuario,
    Variante,
)


class ApiPorNombrarTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = sessionmaker(bind=engine)()
        cat, marca = Categoria(nombre="Ropa casual"), Marca(nombre="Darong")
        self.s.add_all([
            Empleada(codigo="VEND-1", nombre_completo="Daniel Fabian", activo=True),
            Empleada(codigo="VEND-4", nombre_completo="Stayce", activo=True),
            Usuario(username="admin", nombre_completo="Admin", password_hash="x", rol=RolUsuario.ADMIN, activo=True),
            cat, marca, TipoPieza(nombre="Sudadera"),
        ])
        self.s.flush()
        self.p = Producto(nombre="YT0572", nombre_base="YT0572", categoria=cat, marca=marca, genero="Mujer", por_identificar=True)
        self.s.add(self.p)
        self.s.flush()
        self.s.add(Variante(producto_id=self.p.id, sku="SKU005647", talla="Unitalla", color="Surtido",
                            precio_venta=Decimal("99.00"), stock_actual=30))
        self.s.commit()
        app.dependency_overrides[get_db] = lambda: self.s
        self.client = TestClient(app)
        self._quieto = patch("pos_uniformes.services.catalog_service.CatalogService._notify_meili")
        self._quieto.start()
        self._tienda = patch("pos_uniformes.api.routers.movil._modo_servidor", return_value="tienda")
        self._tienda.start()

    def tearDown(self) -> None:
        self._tienda.stop()
        self._quieto.stop()
        app.dependency_overrides.clear()
        self.s.close()

    def _como(self, codigo: str) -> None:
        emp = self.s.query(Empleada).filter(Empleada.codigo == codigo).one()
        app.dependency_overrides[get_current_employee] = lambda: (emp, None)

    def test_el_dueno_ve_lo_pendiente_con_sugerencias(self) -> None:
        self._como("VEND-1")
        d = self.client.get("/api/v1/movil/dueno/por_nombrar").json()
        self.assertEqual([p["nombre"] for p in d["pendientes"]], ["YT0572"])
        self.assertEqual(d["pendientes"][0]["existencia"], 30)
        self.assertIn("Sudadera", d["piezas"])

    def test_una_empleada_no(self) -> None:
        self._como("VEND-4")
        self.assertEqual(self.client.get("/api/v1/movil/dueno/por_nombrar").status_code, 403)

    def test_nombrar_y_mandar_etiquetas(self) -> None:
        self._como("VEND-1")
        with patch("pos_uniformes.services.por_nombrar_service.encolar_etiquetas", return_value=30) as etq:
            r = self.client.post("/api/v1/movil/dueno/nombrar", json={
                "producto_id": self.p.id, "nombre": "Chamarra YT0572", "pieza": "Chamarra",
                "detalle": "Invierno", "color": "Negro", "imprimir_etiquetas": True,
            }).json()
        self.assertEqual((r["ok"], r["nombre"], r["quedan"], r["etiquetas"]), (True, "Chamarra YT0572", 0, 30))
        etq.assert_called_once()
        self.s.refresh(self.p)
        self.assertFalse(self.p.por_identificar)
        self.assertEqual(self.p.tipo_pieza.nombre, "Chamarra")

    def test_sin_pieza_regresa_el_motivo(self) -> None:
        self._como("VEND-1")
        r = self.client.post("/api/v1/movil/dueno/nombrar", json={"producto_id": self.p.id, "nombre": "Algo YT0572"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("pieza", r.json()["detail"]["error"]["message"])


if __name__ == "__main__":
    unittest.main()
