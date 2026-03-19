from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.inventory_label_service import (
    InventoryLabelContext,
    load_inventory_label_context,
    render_inventory_label,
)
from pos_uniformes.utils.label_generator import LabelRenderResult


class InventoryLabelServiceTests(unittest.TestCase):
    def test_load_inventory_label_context_returns_header_data(self) -> None:
        variant = SimpleNamespace(
            id=8,
            sku="SKU-008",
            talla="16",
            color="Azul Marino",
            producto=SimpleNamespace(
                nombre="Pants Deportivo | Patria | Deportivo | Pants #4",
                nombre_base="Pants Deportivo",
            ),
        )
        session = SimpleNamespace(get=lambda _model, _variant_id: variant)

        context = load_inventory_label_context(session, 8)

        self.assertEqual(
            context,
            InventoryLabelContext(
                variant_id=8,
                sku="SKU-008",
                product_name="Pants Deportivo",
                talla="16",
                color="Azul Marino",
            ),
        )

    def test_render_inventory_label_delegates_to_label_generator(self) -> None:
        variant = SimpleNamespace(
            producto=SimpleNamespace(
                nombre="Pants Deportivo",
                escuela=SimpleNamespace(nombre="Colegio Mexico"),
                nivel_educativo=SimpleNamespace(nombre="Secundaria"),
            )
        )
        session = SimpleNamespace(get=lambda _model, _variant_id: variant)
        expected = LabelRenderResult(
            mode="standard",
            image_path=Path("/tmp/label.png"),
            effective_copies=2,
            requested_copies=2,
        )

        with patch(
            "pos_uniformes.services.inventory_label_service.LabelGenerator.render_for_variant",
            return_value=expected,
        ) as render_mock:
            result = render_inventory_label(
                session,
                9,
                mode="standard",
                requested_copies=2,
            )

        render_mock.assert_called_once_with(
            variant,
            mode="standard",
            requested_copies=2,
        )
        self.assertEqual(result, expected)

    def test_render_inventory_label_rejects_missing_variant(self) -> None:
        session = SimpleNamespace(get=lambda _model, _variant_id: None)

        with self.assertRaisesRegex(ValueError, "Presentacion no encontrada"):
            render_inventory_label(
                session,
                99,
                mode="split",
                requested_copies=4,
            )


if __name__ == "__main__":
    unittest.main()
