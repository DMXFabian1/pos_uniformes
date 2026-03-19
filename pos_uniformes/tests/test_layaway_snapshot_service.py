from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.layaway_snapshot_service import (
    LayawaySnapshotRow,
    build_layaway_history_input_rows,
    load_layaway_snapshot_rows,
)


class LayawaySnapshotServiceTests(unittest.TestCase):
    def test_load_layaway_snapshot_rows_maps_layaways(self) -> None:
        layaways = [
            SimpleNamespace(
                id=10,
                folio="AP-001",
                cliente=SimpleNamespace(codigo_cliente="C001"),
                cliente_nombre="Maria",
                cliente_telefono="555",
                fecha_compromiso=datetime(2026, 3, 18, 10, 0),
                estado=SimpleNamespace(value="ACTIVO"),
                total=Decimal("500.00"),
                total_abonado=Decimal("200.00"),
                saldo_pendiente=Decimal("300.00"),
            ),
            SimpleNamespace(
                id=11,
                folio="AP-002",
                cliente=None,
                cliente_nombre="Juan",
                cliente_telefono=None,
                fecha_compromiso=None,
                estado=SimpleNamespace(value="LIQUIDADO"),
                total=Decimal("800.00"),
                total_abonado=Decimal("800.00"),
                saldo_pendiente=Decimal("0.00"),
            ),
        ]
        fake_estado = SimpleNamespace(
            ENTREGADO=SimpleNamespace(value="ENTREGADO"),
            CANCELADO=SimpleNamespace(value="CANCELADO"),
        )

        with patch(
            "pos_uniformes.services.layaway_snapshot_service._resolve_layaway_dependencies",
            return_value=(SimpleNamespace(listar_apartados=lambda session: layaways), fake_estado),
        ):
            rows = load_layaway_snapshot_rows(
                SimpleNamespace(),
                today=date(2026, 3, 19),
                classify_due=lambda fecha, estado: ("Vencido", "danger") if fecha else ("Sin fecha", "neutral"),
            )

        self.assertEqual(
            rows,
            (
                LayawaySnapshotRow(
                    layaway_id=10,
                    folio="AP-001",
                    customer_label="C001 · Maria",
                    estado="ACTIVO",
                    total=Decimal("500.00"),
                    paid=Decimal("200.00"),
                    balance=Decimal("300.00"),
                    due_bucket="overdue",
                    due_text="Vencido",
                    due_tone="danger",
                    searchable="ap-001 c001 maria 555",
                ),
                LayawaySnapshotRow(
                    layaway_id=11,
                    folio="AP-002",
                    customer_label="Manual · Juan",
                    estado="LIQUIDADO",
                    total=Decimal("800.00"),
                    paid=Decimal("800.00"),
                    balance=Decimal("0.00"),
                    due_bucket="none",
                    due_text="Sin fecha",
                    due_tone="neutral",
                    searchable="ap-002  juan ",
                ),
            ),
        )

    def test_build_layaway_history_input_rows(self) -> None:
        rows = build_layaway_history_input_rows(
            (
                LayawaySnapshotRow(
                    layaway_id=10,
                    folio="AP-001",
                    customer_label="C001 · Maria",
                    estado="ACTIVO",
                    total=Decimal("500.00"),
                    paid=Decimal("200.00"),
                    balance=Decimal("300.00"),
                    due_bucket="overdue",
                    due_text="Vencido",
                    due_tone="danger",
                    searchable="ap-001 c001 maria 555",
                ),
            )
        )

        self.assertEqual(
            rows,
            [
                {
                    "id": 10,
                    "folio": "AP-001",
                    "cliente": "C001 · Maria",
                    "estado": "ACTIVO",
                    "total": Decimal("500.00"),
                    "abonado": Decimal("200.00"),
                    "saldo": Decimal("300.00"),
                    "due_bucket": "overdue",
                    "due_text": "Vencido",
                    "due_tone": "danger",
                    "searchable": "ap-001 c001 maria 555",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
