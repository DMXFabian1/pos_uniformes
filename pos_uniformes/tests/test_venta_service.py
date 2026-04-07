from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.venta_service import VentaItemInput, VentaService


class _SessionStub:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flushed = False

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.flushed = True


class _FakeVenta:
    def __init__(self, **kwargs) -> None:
        self.detalles: list[object] = []
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeVentaDetalle:
    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class VentaServiceLayawayTests(unittest.TestCase):
    def test_validar_stock_disponible_allows_sale_when_guard_is_disabled(self) -> None:
        variante = SimpleNamespace(stock_actual=0)

        with patch("pos_uniformes.services.venta_service.sale_stock_guard_enabled", return_value=False):
            VentaService.validar_stock_disponible(variante, 3)

    def test_validar_stock_disponible_blocks_when_guard_is_enabled(self) -> None:
        variante = SimpleNamespace(stock_actual=0)

        with patch("pos_uniformes.services.venta_service.sale_stock_guard_enabled", return_value=True):
            with self.assertRaisesRegex(ValueError, "Stock insuficiente"):
                VentaService.validar_stock_disponible(variante, 3)

    def test_crear_confirmada_desde_apartado_preserves_rounded_total(self) -> None:
        session = _SessionStub()
        usuario = SimpleNamespace(activo=True, rol="CAJERO", username="caja")
        variante = SimpleNamespace()
        detalle = SimpleNamespace(
            variante=variante,
            cantidad=1,
            precio_unitario=Decimal("439.24"),
            subtotal_linea=Decimal("439.24"),
        )
        apartado = SimpleNamespace(
            detalles=[detalle],
            cliente=None,
            total=Decimal("439.50"),
        )

        with patch("pos_uniformes.services.venta_service.Venta", _FakeVenta), patch(
            "pos_uniformes.services.venta_service.VentaDetalle", _FakeVentaDetalle
        ), patch(
            "pos_uniformes.services.venta_service.LoyaltyService.refresh_client_level_from_sales",
            return_value=None,
        ):
            venta = VentaService.crear_confirmada_desde_apartado(
                session=session,
                usuario=usuario,
                apartado=apartado,
                folio="ENT-AP-001",
                observacion="Entrega de apartado AP-001",
            )

        self.assertEqual(venta.subtotal, Decimal("439.24"))
        self.assertEqual(venta.total, Decimal("439.50"))
        self.assertIn("Entrega de apartado AP-001", venta.observacion)
        self.assertIn("Ajuste redondeo: 0.26", venta.observacion)
        self.assertTrue(session.flushed)

    def test_crear_confirmada_desde_apartado_keeps_observation_without_adjustment(self) -> None:
        session = _SessionStub()
        usuario = SimpleNamespace(activo=True, rol="CAJERO", username="caja")
        variante = SimpleNamespace()
        detalle = SimpleNamespace(
            variante=variante,
            cantidad=1,
            precio_unitario=Decimal("439.50"),
            subtotal_linea=Decimal("439.50"),
        )
        apartado = SimpleNamespace(
            detalles=[detalle],
            cliente=None,
            total=Decimal("439.50"),
        )

        with patch("pos_uniformes.services.venta_service.Venta", _FakeVenta), patch(
            "pos_uniformes.services.venta_service.VentaDetalle", _FakeVentaDetalle
        ), patch(
            "pos_uniformes.services.venta_service.LoyaltyService.refresh_client_level_from_sales",
            return_value=None,
        ):
            venta = VentaService.crear_confirmada_desde_apartado(
                session=session,
                usuario=usuario,
                apartado=apartado,
                folio="ENT-AP-002",
                observacion="Entrega limpia",
            )

        self.assertEqual(venta.subtotal, Decimal("439.50"))
        self.assertEqual(venta.total, Decimal("439.50"))
        self.assertEqual(venta.observacion, "Entrega limpia")

    def test_crear_borrador_preserves_custom_unit_price_for_same_sku(self) -> None:
        session = _SessionStub()
        usuario = SimpleNamespace(activo=True, rol="CAJERO")
        variant = SimpleNamespace(sku="PLY-001", precio_venta=Decimal("189.00"))

        with patch("pos_uniformes.services.venta_service.Venta", _FakeVenta), patch(
            "pos_uniformes.services.venta_service.VentaDetalle", _FakeVentaDetalle
        ), patch.object(
            VentaService,
            "obtener_variante_por_sku",
            side_effect=lambda session, sku: variant if sku == "PLY-001" else None,
        ), patch.object(
            VentaService,
            "validar_stock_disponible",
            return_value=None,
        ):
            venta = VentaService.crear_borrador(
                session=session,
                usuario=usuario,
                folio="V-3PZ-001",
                items=[
                    VentaItemInput(sku="PLY-001", cantidad=1, precio_unitario=Decimal("100.00")),
                    VentaItemInput(sku="PLY-001", cantidad=1, precio_unitario=Decimal("189.00")),
                ],
                observacion="Prueba deportivo",
            )

        self.assertEqual(len(venta.detalles), 2)
        self.assertEqual(venta.detalles[0].precio_unitario, Decimal("100.00"))
        self.assertEqual(venta.detalles[1].precio_unitario, Decimal("189.00"))
        self.assertEqual(venta.subtotal, Decimal("289.00"))


if __name__ == "__main__":
    unittest.main()
