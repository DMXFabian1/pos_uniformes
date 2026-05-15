from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.apartado_service import ApartadoItemInput, ApartadoService


def _build_variant(*, sku: str, price: str = "189.00") -> SimpleNamespace:
    return SimpleNamespace(
        sku=sku,
        precio_venta=Decimal(price),
    )


class ApartadoServiceTests(unittest.TestCase):
    def test_crear_apartado_uses_custom_price_for_three_piece_playera(self) -> None:
        apartado = SimpleNamespace(
            detalles=[],
            total_abonado=Decimal("0.00"),
            saldo_pendiente=Decimal("0.00"),
            folio="APT-001",
            cliente_nombre="Maria",
        )
        usuario = SimpleNamespace(username="cajero")
        cliente = None

        with (
            patch.object(ApartadoService, "_validar_operador"),
            patch.object(ApartadoService, "_recalcular_estado"),
            patch("pos_uniformes.services.apartado_service.Apartado", return_value=apartado),
            patch(
                "pos_uniformes.services.apartado_service.ApartadoDetalle",
                side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
            ),
            patch.object(ApartadoService, "obtener_variante_por_sku", return_value=_build_variant(sku="PLY-001")),
            patch("pos_uniformes.services.apartado_service.InventarioService.validar_stock_disponible"),
            patch("pos_uniformes.services.apartado_service.InventarioService.registrar_reserva_apartado"),
            patch("pos_uniformes.services.apartado_service.ApartadoAbono", side_effect=lambda **kwargs: SimpleNamespace(**kwargs)),
            patch("pos_uniformes.services.apartado_service.resolve_layaway_client_discount_percent", return_value=Decimal("0.00")),
            patch("pos_uniformes.services.apartado_service.build_layaway_pricing", return_value=SimpleNamespace(subtotal=Decimal("100.00"), total=Decimal("100.00"))),
            patch("pos_uniformes.services.apartado_service.resolve_layaway_min_deposit", return_value=Decimal("20.00")),
        ):
            result = ApartadoService.crear_apartado(
                session=SimpleNamespace(add=lambda _value: None, flush=lambda: None),
                usuario=usuario,
                folio="APT-001",
                cliente_nombre="Maria",
                cliente_telefono="555",
                items=[
                    ApartadoItemInput(
                        sku="PLY-001",
                        cantidad=1,
                        precio_unitario=Decimal("100.00"),
                        pricing_rule_key="SPORTS_UNIFORM_3PZ_PLAYERA",
                        pricing_rule_label="Conjunto deportivo 3pz",
                    )
                ],
                anticipo=Decimal("20.00"),
                cliente=cliente,
            )

        self.assertEqual(result.detalles[0].precio_unitario, Decimal("100.00"))
        self.assertEqual(result.total, Decimal("100.00"))


class ApartadoEmployeeAttributionTests(unittest.TestCase):
    def _base_patches(self, apartado):
        return [
            patch.object(ApartadoService, "_validar_operador"),
            patch.object(ApartadoService, "_recalcular_estado"),
            patch("pos_uniformes.services.apartado_service.Apartado", return_value=apartado),
            patch(
                "pos_uniformes.services.apartado_service.ApartadoDetalle",
                side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
            ),
            patch.object(ApartadoService, "obtener_variante_por_sku", return_value=SimpleNamespace(sku="A01", precio_venta=Decimal("100.00"))),
            patch("pos_uniformes.services.apartado_service.InventarioService.validar_stock_disponible"),
            patch("pos_uniformes.services.apartado_service.InventarioService.registrar_reserva_apartado"),
            patch("pos_uniformes.services.apartado_service.ApartadoAbono", side_effect=lambda **kwargs: SimpleNamespace(**kwargs)),
            patch("pos_uniformes.services.apartado_service.resolve_layaway_client_discount_percent", return_value=Decimal("0.00")),
            patch("pos_uniformes.services.apartado_service.build_layaway_pricing", return_value=SimpleNamespace(subtotal=Decimal("100.00"), total=Decimal("100.00"))),
            patch("pos_uniformes.services.apartado_service.resolve_layaway_min_deposit", return_value=Decimal("20.00")),
        ]

    def test_crear_apartado_stores_seller_employee(self) -> None:
        apartado = SimpleNamespace(
            detalles=[],
            total_abonado=Decimal("0.00"),
            saldo_pendiente=Decimal("0.00"),
            folio="APT-EMP",
            cliente_nombre="Cliente",
            seller_employee_code=None,
            seller_employee_display_name=None,
        )
        captured: list[SimpleNamespace] = []

        def capture_apartado(**kwargs):
            apartado.seller_employee_code = kwargs.get("seller_employee_code")
            apartado.seller_employee_display_name = kwargs.get("seller_employee_display_name")
            return apartado

        patches = self._base_patches(apartado)
        patches[2] = patch("pos_uniformes.services.apartado_service.Apartado", side_effect=capture_apartado)

        abono_captured: dict = {}

        def capture_abono(**kwargs):
            abono_captured.update(kwargs)
            return SimpleNamespace(**kwargs)

        patches[7] = patch("pos_uniformes.services.apartado_service.ApartadoAbono", side_effect=capture_abono)

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10]:
            ApartadoService.crear_apartado(
                session=SimpleNamespace(add=lambda _v: None, flush=lambda: None),
                usuario=SimpleNamespace(username="cajero"),
                folio="APT-EMP",
                cliente_nombre="Cliente",
                cliente_telefono=None,
                items=[ApartadoItemInput(sku="A01", cantidad=1)],
                anticipo=Decimal("20.00"),
                seller_employee_code="LUZ",
                seller_employee_display_name="Luz R.",
            )

        self.assertEqual(apartado.seller_employee_code, "LUZ")
        self.assertEqual(apartado.seller_employee_display_name, "Luz R.")
        self.assertEqual(abono_captured.get("seller_employee_code"), "LUZ")

    def test_registrar_abono_stores_seller_employee(self) -> None:
        apartado = SimpleNamespace(
            estado=SimpleNamespace(name="ACTIVO"),
            saldo_pendiente=Decimal("50.00"),
            total=Decimal("100.00"),
            total_abonado=Decimal("50.00"),
        )
        from pos_uniformes.database.models import EstadoApartado
        apartado.estado = EstadoApartado.ACTIVO
        abono_captured: dict = {}

        def capture_abono(**kwargs):
            abono_captured.update(kwargs)
            return SimpleNamespace(**kwargs)

        with (
            patch.object(ApartadoService, "_validar_operador"),
            patch.object(ApartadoService, "_recalcular_estado"),
            patch("pos_uniformes.services.apartado_service.ApartadoAbono", side_effect=capture_abono),
        ):
            ApartadoService.registrar_abono(
                session=SimpleNamespace(add=lambda _v: None),
                apartado=apartado,
                usuario=SimpleNamespace(username="cajero"),
                monto=Decimal("50.00"),
                seller_employee_code="ANA",
                seller_employee_display_name="Ana L.",
            )

        self.assertEqual(abono_captured.get("seller_employee_code"), "ANA")
        self.assertEqual(abono_captured.get("seller_employee_display_name"), "Ana L.")

    def test_entregar_apartado_stores_delivery_employee(self) -> None:
        from pos_uniformes.database.models import EstadoApartado
        apartado = SimpleNamespace(
            estado=EstadoApartado.LIQUIDADO,
            saldo_pendiente=Decimal("0.00"),
            delivery_employee_code=None,
            delivery_employee_display_name=None,
            entregado_por=None,
            entregado_at=None,
        )
        usuario = SimpleNamespace(username="cajero")

        with (
            patch.object(ApartadoService, "_validar_operador"),
        ):
            ApartadoService.entregar_apartado(
                session=SimpleNamespace(add=lambda _v: None),
                apartado=apartado,
                usuario=usuario,
                delivery_employee_code="SOFIA",
                delivery_employee_display_name="Sofia M.",
            )

        self.assertEqual(apartado.delivery_employee_code, "SOFIA")
        self.assertEqual(apartado.delivery_employee_display_name, "Sofia M.")

    def test_entregar_apartado_no_employee_leaves_field_none(self) -> None:
        from pos_uniformes.database.models import EstadoApartado
        apartado = SimpleNamespace(
            estado=EstadoApartado.LIQUIDADO,
            saldo_pendiente=Decimal("0.00"),
            delivery_employee_code=None,
            delivery_employee_display_name=None,
            entregado_por=None,
            entregado_at=None,
        )

        with patch.object(ApartadoService, "_validar_operador"):
            ApartadoService.entregar_apartado(
                session=SimpleNamespace(add=lambda _v: None),
                apartado=apartado,
                usuario=SimpleNamespace(username="cajero"),
            )

        self.assertIsNone(apartado.delivery_employee_code)


if __name__ == "__main__":
    unittest.main()
