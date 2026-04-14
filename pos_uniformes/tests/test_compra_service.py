"""Tests para CompraService."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pos_uniformes.database.models import EstadoCompra, RolUsuario
from pos_uniformes.services.compra_service import CompraItemInput, CompraService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin() -> SimpleNamespace:
    return SimpleNamespace(id=1, activo=True, rol=RolUsuario.ADMIN, username="admin")


def _make_cajero() -> SimpleNamespace:
    return SimpleNamespace(id=2, activo=True, rol=RolUsuario.CAJERO, username="cajero")


def _make_variante(*, vid: int, precio: str = "100.00") -> SimpleNamespace:
    return SimpleNamespace(id=vid, activo=True, precio_venta=Decimal(precio), costo_referencia=None)


def _session_with_variantes(*variantes) -> MagicMock:
    session = MagicMock()
    by_id = {v.id: v for v in variantes}
    session.query.return_value.filter.return_value.all.return_value = list(variantes)
    return session


class _FakeCompra:
    def __init__(self, **kwargs) -> None:
        self.detalles: list = []
        self.subtotal = Decimal("0.00")
        self.total = Decimal("0.00")
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeCompraDetalle:
    def __init__(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# _validar_permiso
# ---------------------------------------------------------------------------

class ValidarPermisoTests(unittest.TestCase):

    def test_admin_activo_passes(self) -> None:
        CompraService._validar_permiso(_make_admin())

    def test_cajero_raises_permission_error(self) -> None:
        with self.assertRaises(PermissionError):
            CompraService._validar_permiso(_make_cajero())

    def test_inactive_admin_raises(self) -> None:
        admin = SimpleNamespace(activo=False, rol=RolUsuario.ADMIN)
        with self.assertRaises(PermissionError):
            CompraService._validar_permiso(admin)


# ---------------------------------------------------------------------------
# _validar_items
# ---------------------------------------------------------------------------

class ValidarItemsTests(unittest.TestCase):

    def test_empty_list_raises(self) -> None:
        with self.assertRaises(ValueError):
            CompraService._validar_items([])

    def test_duplicate_variante_raises(self) -> None:
        items = [
            CompraItemInput(variante_id=1, cantidad=2, costo_unitario=Decimal("50.00")),
            CompraItemInput(variante_id=1, cantidad=3, costo_unitario=Decimal("50.00")),
        ]
        with self.assertRaises(ValueError):
            CompraService._validar_items(items)

    def test_zero_cantidad_raises(self) -> None:
        items = [CompraItemInput(variante_id=1, cantidad=0, costo_unitario=Decimal("50.00"))]
        with self.assertRaises(ValueError):
            CompraService._validar_items(items)

    def test_negative_cantidad_raises(self) -> None:
        items = [CompraItemInput(variante_id=1, cantidad=-1, costo_unitario=Decimal("50.00"))]
        with self.assertRaises(ValueError):
            CompraService._validar_items(items)

    def test_negative_costo_raises(self) -> None:
        items = [CompraItemInput(variante_id=1, cantidad=1, costo_unitario=Decimal("-1.00"))]
        with self.assertRaises(ValueError):
            CompraService._validar_items(items)

    def test_valid_items_pass(self) -> None:
        items = [
            CompraItemInput(variante_id=1, cantidad=2, costo_unitario=Decimal("50.00")),
            CompraItemInput(variante_id=2, cantidad=1, costo_unitario=Decimal("0.00")),
        ]
        CompraService._validar_items(items)  # no debe lanzar


# ---------------------------------------------------------------------------
# crear_borrador
# ---------------------------------------------------------------------------

class CrearBorradorTests(unittest.TestCase):

    def test_crea_compra_con_totales_correctos(self) -> None:
        admin = _make_admin()
        proveedor = SimpleNamespace(id=10)
        variante1 = _make_variante(vid=1)
        variante2 = _make_variante(vid=2)
        session = _session_with_variantes(variante1, variante2)

        items = [
            CompraItemInput(variante_id=1, cantidad=3, costo_unitario=Decimal("100.00")),
            CompraItemInput(variante_id=2, cantidad=2, costo_unitario=Decimal("50.00")),
        ]

        with patch("pos_uniformes.services.compra_service.Compra", _FakeCompra), \
             patch("pos_uniformes.services.compra_service.CompraDetalle", _FakeCompraDetalle):
            compra = CompraService.crear_borrador(
                session, proveedor, admin,
                numero_documento="FAC-001",
                items=items,
            )

        self.assertEqual(compra.total, Decimal("400.00"))  # 300 + 100
        self.assertEqual(len(compra.detalles), 2)
        session.add.assert_called_once_with(compra)

    def test_cajero_no_puede_crear_compra(self) -> None:
        cajero = _make_cajero()
        session = MagicMock()

        with self.assertRaises(PermissionError):
            CompraService.crear_borrador(
                session, SimpleNamespace(), cajero,
                numero_documento="FAC-001",
                items=[CompraItemInput(variante_id=1, cantidad=1, costo_unitario=Decimal("10.00"))],
            )

    def test_variante_inexistente_raises(self) -> None:
        admin = _make_admin()
        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = []  # ninguna variante encontrada

        with patch("pos_uniformes.services.compra_service.Compra", _FakeCompra):
            with self.assertRaises(ValueError):
                CompraService.crear_borrador(
                    session, SimpleNamespace(), admin,
                    numero_documento="FAC-001",
                    items=[CompraItemInput(variante_id=99, cantidad=1, costo_unitario=Decimal("10.00"))],
                )


# ---------------------------------------------------------------------------
# confirmar_compra
# ---------------------------------------------------------------------------

class ConfirmarCompraTests(unittest.TestCase):

    def test_confirma_borrador_y_registra_inventario(self) -> None:
        admin = _make_admin()
        variante = _make_variante(vid=1)
        detalle = SimpleNamespace(
            variante=variante,
            cantidad=5,
            costo_unitario=Decimal("80.00"),
        )
        compra = SimpleNamespace(
            usuario=admin,
            estado=EstadoCompra.BORRADOR,
            detalles=[detalle],
            numero_documento="FAC-001",
        )
        session = MagicMock()

        with patch("pos_uniformes.services.compra_service.InventarioService.registrar_ingreso_compra") as mock_inv:
            result = CompraService.confirmar_compra(session, compra)

        self.assertEqual(result.estado, EstadoCompra.CONFIRMADA)
        self.assertIsNotNone(result.confirmada_at)
        mock_inv.assert_called_once()
        self.assertEqual(variante.costo_referencia, Decimal("80.00"))

    def test_no_puede_confirmar_compra_ya_confirmada(self) -> None:
        admin = _make_admin()
        compra = SimpleNamespace(
            usuario=admin,
            estado=EstadoCompra.CONFIRMADA,
            detalles=[SimpleNamespace()],
        )
        session = MagicMock()

        with self.assertRaises(ValueError):
            CompraService.confirmar_compra(session, compra)

    def test_no_puede_confirmar_compra_sin_detalles(self) -> None:
        admin = _make_admin()
        compra = SimpleNamespace(
            usuario=admin,
            estado=EstadoCompra.BORRADOR,
            detalles=[],
        )
        session = MagicMock()

        with self.assertRaises(ValueError):
            CompraService.confirmar_compra(session, compra)


if __name__ == "__main__":
    unittest.main()
