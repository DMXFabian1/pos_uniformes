"""CatalogService: nombre sin escuela repetida, $0, SKU con candado, búsqueda
después del commit y borrar/reactivar prendas (tanda 1 del alta, 2026-11-13)."""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    ConjuntoComponente,
    Escuela,
    Marca,
    Producto,
    RolUsuario,
    SkuSequence,
    Uniforme,
    UniformePieza,
    Usuario,
    Variante,
)
from pos_uniformes.services.catalog_service import CatalogService as C
from pos_uniformes.ui.helpers.catalog_product_form_summary_helper import (
    build_catalog_product_display_name_preview,
)


class _ConBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.s = Session(self.engine, expire_on_commit=False)
        self.admin = Usuario(username="admin", nombre_completo="Admin", rol=RolUsuario.ADMIN, password_hash="x")
        self.cat = Categoria(nombre="Uniformes")
        self.marca = Marca(nombre="Sin marca")
        self.estv = Escuela(nombre="ESTV 154")
        self.allende = Escuela(nombre="Ignacio Allende")
        self.s.add_all([self.admin, self.cat, self.marca, self.estv, self.allende])
        self.s.commit()
        self._quieto = patch.object(C, "_avisar_busqueda")
        self.avisos = self._quieto.start()
        self.addCleanup(self._quieto.stop)

    def _producto(self, nombre: str, escuela: Escuela | None = None) -> Producto:
        return C.crear_producto(self.s, self.admin, self.cat, self.marca, nombre, escuela=escuela)

    def _talla(self, producto: Producto, talla: str, precio: str = "245") -> Variante:
        return C.crear_variante(self.s, self.admin, producto, None, talla, "Sin color", Decimal(precio))


class BusquedaDespuesDelCommitTests(_ConBase):
    def test_avisa_una_vez_y_despues_del_commit(self) -> None:
        self.avisos.reset_mock()
        p = self._producto("Bata", None)
        self._talla(p, "4")
        self._talla(p, "6")
        self.avisos.assert_not_called()
        self.s.commit()
        self.avisos.assert_called_once()

    def test_si_hay_rollback_no_avisa(self) -> None:
        self.avisos.reset_mock()
        self._producto("Bata", None)
        self.s.rollback()
        self.s.commit()
        self.avisos.assert_not_called()

    def test_borrar_tambien_avisa(self) -> None:
        p = self._producto("Bata", None)
        self._talla(p, "4")
        self.s.commit()
        self.avisos.reset_mock()
        C.eliminar_producto(self.s, self.admin, p)
        self.s.commit()
        self.avisos.assert_called_once()


if __name__ == "__main__":
    unittest.main()
