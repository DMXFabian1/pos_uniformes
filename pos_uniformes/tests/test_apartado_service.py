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


if __name__ == "__main__":
    unittest.main()
