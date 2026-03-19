from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.quote_detail_service import (
    QuoteDetailLineSnapshot,
    QuoteDetailSnapshot,
    load_quote_detail_snapshot,
)


class QuoteDetailServiceTests(unittest.TestCase):
    def test_load_quote_detail_snapshot_maps_selected_quote(self) -> None:
        quote = SimpleNamespace(
            folio="PRE-001",
            cliente_nombre="Maria",
            cliente_telefono="555",
            cliente=None,
            estado=SimpleNamespace(value="EMITIDO"),
            total=Decimal("350.00"),
            vigencia_hasta=datetime(2026, 3, 25, 0, 0),
            usuario=SimpleNamespace(username="cajero"),
            observacion="Observacion",
            detalles=[
                SimpleNamespace(
                    sku_snapshot="SKU-1",
                    descripcion_snapshot="Playera",
                    cantidad=2,
                    precio_unitario=Decimal("175.00"),
                    subtotal_linea=Decimal("350.00"),
                )
            ],
        )
        fake_service = SimpleNamespace(obtener_presupuesto=lambda session, quote_id: quote if quote_id == 10 else None)

        with patch(
            "pos_uniformes.services.quote_detail_service._resolve_quote_detail_dependencies",
            return_value=fake_service,
        ):
            snapshot = load_quote_detail_snapshot(SimpleNamespace(), quote_id=10)

        self.assertEqual(
            snapshot,
            QuoteDetailSnapshot(
                folio="PRE-001",
                customer_label="Maria",
                phone_text="555",
                status_label="EMITIDO",
                total=Decimal("350.00"),
                validity_label="2026-03-25",
                user_label="cajero",
                notes_text="Observacion",
                detail_rows=(
                    QuoteDetailLineSnapshot(
                        sku="SKU-1",
                        description="Playera",
                        quantity=2,
                        unit_price=Decimal("175.00"),
                        subtotal=Decimal("350.00"),
                    ),
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
