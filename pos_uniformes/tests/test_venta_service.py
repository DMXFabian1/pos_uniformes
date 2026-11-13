from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.database.models import ModoOrigenVenta
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
        variante = SimpleNamespace(sku="PLY-001-S-BL", producto=SimpleNamespace(nombre="Playera"))
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
        variante = SimpleNamespace(sku="PNT-002-M-AZ", producto=SimpleNamespace(nombre="Pantalon"))
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
        variant = SimpleNamespace(sku="PLY-001", precio_venta=Decimal("189.00"), producto=SimpleNamespace(nombre="Playera"))

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

    def test_crear_borrador_persists_sale_origin_fields(self) -> None:
        session = _SessionStub()
        usuario = SimpleNamespace(activo=True, rol="CAJERO")
        variant = SimpleNamespace(sku="SKU-001", precio_venta=Decimal("65.00"), producto=SimpleNamespace(nombre="Camisa"))

        with patch("pos_uniformes.services.venta_service.Venta", _FakeVenta), patch(
            "pos_uniformes.services.venta_service.VentaDetalle", _FakeVentaDetalle
        ), patch.object(
            VentaService,
            "obtener_variante_por_sku",
            return_value=variant,
        ), patch.object(
            VentaService,
            "validar_stock_disponible",
            return_value=None,
        ):
            venta = VentaService.crear_borrador(
                session=session,
                usuario=usuario,
                folio="VTA-ORIGEN-001",
                items=[VentaItemInput(sku="SKU-001", cantidad=1)],
                credit_mode=ModoOrigenVenta.OPERATOR_DIRECT,
                seller_employee_code="",
                seller_employee_display_name="",
            )

        self.assertEqual(venta.credit_mode, ModoOrigenVenta.OPERATOR_DIRECT)
        self.assertIsNone(venta.seller_employee_code)
        self.assertIsNone(venta.seller_employee_display_name)


class VentaServiceNivelViejoRetiradoTests(unittest.TestCase):
    """2026-11-12: «el nivel viejo retíralo» (Daniel). Cobrar, entregar un
    apartado o cancelar una venta ya no revisa `nivel_lealtad` ni toca
    `descuento_preferente` ni los metadatos de asignación."""

    @staticmethod
    def _cliente() -> SimpleNamespace:
        return SimpleNamespace(
            id=9,
            codigo_cliente="CLI-000009",
            nivel_lealtad="BASICO",
            descuento_preferente=Decimal("5.00"),
            nivel_asignado_por_user_id=None,
            nivel_asignado_por_rol=None,
            nivel_asignacion_motivo=None,
        )

    def _assert_cliente_intacto(self, cliente: SimpleNamespace) -> None:
        self.assertEqual(cliente.nivel_lealtad, "BASICO")
        self.assertEqual(cliente.descuento_preferente, Decimal("5.00"))
        self.assertIsNone(cliente.nivel_asignado_por_user_id)
        self.assertIsNone(cliente.nivel_asignacion_motivo)

    def test_venta_service_ya_no_importa_loyalty_service(self) -> None:
        from pos_uniformes.services import venta_service

        self.assertFalse(hasattr(venta_service, "LoyaltyService"))

    def test_confirmar_venta_no_cambia_nivel(self) -> None:
        from pos_uniformes.database.models import EstadoVenta, RolUsuario

        cliente = self._cliente()
        venta = SimpleNamespace(
            usuario=SimpleNamespace(activo=True, rol=RolUsuario.CAJERO, username="caja"),
            estado=EstadoVenta.BORRADOR,
            detalles=[SimpleNamespace(variante=None, cantidad=1)],
            cliente=cliente,
            folio="V-NIV-001",
        )
        session = _SessionStub()

        VentaService.confirmar_venta(session, venta)

        self.assertEqual(venta.estado, EstadoVenta.CONFIRMADA)
        self._assert_cliente_intacto(cliente)

    def test_crear_confirmada_desde_apartado_no_cambia_nivel(self) -> None:
        cliente = self._cliente()
        variante = SimpleNamespace(sku="PLY-001", producto=SimpleNamespace(nombre="Playera"))
        apartado = SimpleNamespace(
            detalles=[
                SimpleNamespace(
                    variante=variante,
                    cantidad=1,
                    precio_unitario=Decimal("100.00"),
                    subtotal_linea=Decimal("100.00"),
                )
            ],
            cliente=cliente,
            total=Decimal("100.00"),
        )
        usuario = SimpleNamespace(activo=True, rol="CAJERO", username="caja")

        with patch("pos_uniformes.services.venta_service.Venta", _FakeVenta), patch(
            "pos_uniformes.services.venta_service.VentaDetalle", _FakeVentaDetalle
        ):
            VentaService.crear_confirmada_desde_apartado(
                session=_SessionStub(), usuario=usuario, apartado=apartado, folio="ENT-NIV-001"
            )

        self._assert_cliente_intacto(cliente)

    def test_cancelar_venta_no_cambia_nivel(self) -> None:
        from pos_uniformes.database.models import EstadoVenta, RolUsuario

        cliente = self._cliente()
        venta = SimpleNamespace(
            estado=EstadoVenta.CONFIRMADA,
            detalles=[SimpleNamespace(variante=None, cantidad=1)],
            cliente=cliente,
            folio="V-NIV-002",
            observacion=None,
        )
        admin = SimpleNamespace(activo=True, rol=RolUsuario.ADMIN, username="admin")

        VentaService.cancelar_venta(_SessionStub(), venta, admin)

        self.assertEqual(venta.estado, EstadoVenta.CANCELADA)
        self._assert_cliente_intacto(cliente)


if __name__ == "__main__":
    unittest.main()
