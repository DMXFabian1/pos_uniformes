from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.layaway_creation_service import (
    LayawayCreationResult,
    create_layaway_from_payload,
)


class LayawayCreationServiceTests(unittest.TestCase):
    def test_create_layaway_from_payload_uses_apartado_service(self) -> None:
        usuario = object()
        cliente = object()
        created_layaway = SimpleNamespace(id=10, folio="AP-001")
        session = SimpleNamespace(
            get=lambda model, item_id: usuario if item_id == 7 else cliente if item_id == 2 else None
        )
        fake_apartado_service = SimpleNamespace(crear_apartado=lambda **kwargs: created_layaway)

        with patch(
            "pos_uniformes.services.layaway_creation_service._resolve_layaway_creation_dependencies",
            return_value=(fake_apartado_service, object(), object()),
        ):
            result = create_layaway_from_payload(
                session,
                user_id=7,
                folio="AP-001",
                payload={
                    "cliente_id": 2,
                    "cliente_nombre": "Maria",
                    "cliente_telefono": "555",
                    "items": [SimpleNamespace(sku="SKU-1", cantidad=1)],
                    "anticipo": Decimal("100.00"),
                    "fecha_compromiso": "2026-03-20",
                    "observacion": "",
                },
                default_note="Creado desde Caja.",
            )

        self.assertEqual(result, LayawayCreationResult(layaway_id=10, layaway_folio="AP-001"))


if __name__ == "__main__":
    unittest.main()
