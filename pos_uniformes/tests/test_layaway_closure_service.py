from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.layaway_closure_service import (
    LayawayDeliveryResult,
    cancel_layaway,
    deliver_layaway,
)


class LayawayClosureServiceTests(unittest.TestCase):
    def test_deliver_layaway_creates_sale_and_marks_delivered(self) -> None:
        usuario = object()
        apartado = SimpleNamespace(folio="AP-001")
        sale = SimpleNamespace(folio="ENT-AP-001")
        session = SimpleNamespace(get=lambda model, item_id: usuario if item_id == 7 else None)
        fake_apartado_service = SimpleNamespace(
            obtener_apartado=lambda _session, layaway_id: apartado if layaway_id == 10 else None,
            entregar_apartado=lambda *args, **kwargs: None,
        )
        fake_venta_service = SimpleNamespace(crear_confirmada_desde_apartado=lambda **kwargs: sale)

        with patch(
            "pos_uniformes.services.layaway_closure_service._resolve_layaway_closure_dependencies",
            return_value=(fake_apartado_service, object(), fake_venta_service),
        ):
            result = deliver_layaway(SimpleNamespace(get=session.get), layaway_id=10, user_id=7)

        self.assertEqual(result, LayawayDeliveryResult(sale_folio="ENT-AP-001"))

    def test_cancel_layaway_uses_apartado_service(self) -> None:
        usuario = object()
        apartado = object()
        session = SimpleNamespace(get=lambda model, item_id: usuario if item_id == 7 else None)
        fake_apartado_service = SimpleNamespace(
            obtener_apartado=lambda _session, layaway_id: apartado if layaway_id == 10 else None,
            cancelar_apartado=lambda **kwargs: None,
        )

        with patch(
            "pos_uniformes.services.layaway_closure_service._resolve_layaway_closure_dependencies",
            return_value=(fake_apartado_service, object(), object()),
        ):
            cancel_layaway(SimpleNamespace(get=session.get), layaway_id=10, user_id=7, note="Motivo")


if __name__ == "__main__":
    unittest.main()
