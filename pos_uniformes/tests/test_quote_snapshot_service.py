from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.quote_snapshot_service import (
    QuoteSnapshotRow,
    build_quote_history_input_rows,
    load_quote_snapshot_rows,
)


class QuoteSnapshotServiceTests(unittest.TestCase):
    def test_load_quote_snapshot_rows_maps_quotes(self) -> None:
        quotes = [
            SimpleNamespace(
                id=10,
                folio="PRE-001",
                cliente_nombre="Maria",
                cliente_telefono="555",
                cliente=None,
                estado=SimpleNamespace(value="EMITIDO"),
                total=Decimal("350.00"),
                usuario=SimpleNamespace(username="cajero"),
                vigencia_hasta=datetime(2026, 3, 25, 0, 0),
                created_at=datetime(2026, 3, 19, 11, 5),
                detalles=[SimpleNamespace(sku_snapshot="SKU-1"), SimpleNamespace(sku_snapshot="SKU-2")],
            ),
            SimpleNamespace(
                id=11,
                folio="PRE-002",
                cliente_nombre="",
                cliente_telefono=None,
                cliente=None,
                estado=SimpleNamespace(value="BORRADOR"),
                total=Decimal("0.00"),
                usuario=None,
                vigencia_hasta=None,
                created_at=None,
                detalles=[],
            ),
        ]
        fake_service = SimpleNamespace(listar_presupuestos=lambda session, limit=200: quotes)

        with patch(
            "pos_uniformes.services.quote_snapshot_service._resolve_quote_snapshot_dependencies",
            return_value=fake_service,
        ):
            rows = load_quote_snapshot_rows(SimpleNamespace(), limit=200)

        self.assertEqual(
            rows,
            (
                QuoteSnapshotRow(
                    quote_id=10,
                    folio="PRE-001",
                    customer_label="Maria",
                    estado="EMITIDO",
                    total=Decimal("350.00"),
                    username="cajero",
                    validity_label="25/03/2026",
                    created_at_label="19/03/2026 11:05",
                    searchable="PRE-001 Maria 555 SKU-1 SKU-2",
                ),
                QuoteSnapshotRow(
                    quote_id=11,
                    folio="PRE-002",
                    customer_label="Mostrador / sin cliente",
                    estado="BORRADOR",
                    total=Decimal("0.00"),
                    username="",
                    validity_label="Sin vigencia",
                    created_at_label="",
                    searchable="PRE-002   ",
                ),
            ),
        )

    def test_build_quote_history_input_rows(self) -> None:
        rows = build_quote_history_input_rows(
            (
                QuoteSnapshotRow(
                    quote_id=10,
                    folio="PRE-001",
                    customer_label="Maria",
                    estado="EMITIDO",
                    total=Decimal("350.00"),
                    username="cajero",
                    validity_label="25/03/2026",
                    created_at_label="19/03/2026 11:05",
                    searchable="PRE-001 Maria 555 SKU-1 SKU-2",
                ),
            )
        )

        self.assertEqual(
            rows,
            [
                {
                    "id": 10,
                    "folio": "PRE-001",
                    "cliente": "Maria",
                    "estado": "EMITIDO",
                    "total": Decimal("350.00"),
                    "usuario": "cajero",
                    "vigencia": "25/03/2026",
                    "fecha": "19/03/2026 11:05",
                    "searchable": "PRE-001 Maria 555 SKU-1 SKU-2",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
