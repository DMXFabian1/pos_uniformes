from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.ui.helpers.inventory_bulk_qr_helper import (
    InventoryBulkQrCancelled,
    build_inventory_bulk_qr_progress,
    generate_inventory_bulk_qr,
)


class InventoryBulkQrHelperTests(unittest.TestCase):
    def test_build_inventory_bulk_qr_progress_formats_message(self) -> None:
        progress = build_inventory_bulk_qr_progress(current=3, total=12, sku="sku-009")

        self.assertEqual(progress.sku, "SKU-009")
        self.assertEqual(progress.message, "Generando etiqueta 3 de 12: SKU-009")

    def test_generate_inventory_bulk_qr_runs_one_by_one_and_reports_progress(self) -> None:
        variantes = [
            SimpleNamespace(sku="sku-001"),
            SimpleNamespace(sku="sku-002"),
        ]
        progress_messages: list[str] = []

        with patch(
            "pos_uniformes.ui.helpers.inventory_bulk_qr_helper.QrGenerator.generate_for_variant",
            side_effect=[Path("/tmp/1.png"), Path("/tmp/2.png")],
        ) as generate_mock:
            paths = generate_inventory_bulk_qr(
                variantes,
                on_progress=lambda progress: progress_messages.append(progress.message),
            )

        self.assertEqual(paths, [Path("/tmp/1.png"), Path("/tmp/2.png")])
        self.assertEqual(
            progress_messages,
            [
                "Generando etiqueta 1 de 2: SKU-001",
                "Generando etiqueta 2 de 2: SKU-002",
            ],
        )
        self.assertEqual(generate_mock.call_count, 2)

    def test_generate_inventory_bulk_qr_honors_cancellation(self) -> None:
        variantes = [
            SimpleNamespace(sku="sku-001"),
            SimpleNamespace(sku="sku-002"),
        ]
        cancellation_checks = iter([False, True])

        with patch("pos_uniformes.ui.helpers.inventory_bulk_qr_helper.QrGenerator.generate_for_variant") as generate_mock:
            with self.assertRaises(InventoryBulkQrCancelled):
                generate_inventory_bulk_qr(
                    variantes,
                    is_cancelled=lambda: next(cancellation_checks),
                )

        generate_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
