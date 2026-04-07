from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.presupuesto_service import PresupuestoItemInput, PresupuestoService


def _build_variant(*, sku: str, price: str = "189.00", base_name: str = "Playera deportiva") -> SimpleNamespace:
    return SimpleNamespace(
        sku=sku,
        precio_venta=price,
        talla="CH",
        color="Azul",
        producto=SimpleNamespace(nombre_base=base_name),
    )


class PresupuestoServiceTests(unittest.TestCase):
    def test_build_quote_details_uses_custom_description_and_price(self) -> None:
        variant = _build_variant(sku="PLY-001")

        with (
            patch.object(PresupuestoService, "obtener_variante_por_sku", return_value=variant),
            patch(
                "pos_uniformes.services.presupuesto_service.PresupuestoDetalle",
                side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
            ),
        ):
            detail_rows, total = PresupuestoService._build_quote_details(
                SimpleNamespace(),
                items=[
                    PresupuestoItemInput(
                        sku="PLY-001",
                        cantidad=2,
                        precio_unitario=Decimal("100.00"),
                        descripcion_snapshot="Playera deportiva (Conjunto deportivo 3pz)",
                        pricing_rule_key="SPORTS_UNIFORM_3PZ_PLAYERA",
                        pricing_rule_label="Conjunto deportivo 3pz",
                    )
                ],
            )

        self.assertEqual(total, Decimal("200.00"))
        self.assertEqual(detail_rows[0].precio_unitario, Decimal("100.00"))
        self.assertEqual(detail_rows[0].descripcion_snapshot, "Playera deportiva (Conjunto deportivo 3pz)")

    def test_build_quote_details_allows_same_sku_with_different_pricing_rule(self) -> None:
        variant = _build_variant(sku="PLY-001")

        with (
            patch.object(PresupuestoService, "obtener_variante_por_sku", return_value=variant),
            patch(
                "pos_uniformes.services.presupuesto_service.PresupuestoDetalle",
                side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
            ),
        ):
            detail_rows, total = PresupuestoService._build_quote_details(
                SimpleNamespace(),
                items=[
                    PresupuestoItemInput(sku="PLY-001", cantidad=1),
                    PresupuestoItemInput(
                        sku="PLY-001",
                        cantidad=1,
                        precio_unitario=Decimal("100.00"),
                        descripcion_snapshot="Playera deportiva (Conjunto deportivo 3pz)",
                        pricing_rule_key="SPORTS_UNIFORM_3PZ_PLAYERA",
                        pricing_rule_label="Conjunto deportivo 3pz",
                    ),
                ],
            )

        self.assertEqual(len(detail_rows), 2)
        self.assertEqual(total, Decimal("289.00"))


if __name__ == "__main__":
    unittest.main()
