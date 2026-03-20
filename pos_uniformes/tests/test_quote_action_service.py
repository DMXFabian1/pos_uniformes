from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.quote_action_service import cancel_quote, emit_quote


class QuoteActionServiceTests(unittest.TestCase):
    def test_emit_quote_uses_presupuesto_service(self) -> None:
        quote = object()
        user = SimpleNamespace(username="admin")
        session = SimpleNamespace(get=lambda model, item_id: user if item_id == 7 else None)
        fake_service = SimpleNamespace(
            obtener_presupuesto=lambda _session, quote_id: quote if quote_id == 10 else None,
            emitir_presupuesto=lambda **kwargs: None,
        )

        with patch(
            "pos_uniformes.services.quote_action_service._resolve_quote_action_dependencies",
            return_value=(fake_service, object()),
        ):
            emit_quote(session, quote_id=10, user_id=7)

    def test_cancel_quote_uses_presupuesto_service(self) -> None:
        quote = object()
        user = SimpleNamespace(username="admin")
        session = SimpleNamespace(get=lambda model, item_id: user if item_id == 7 else None)
        fake_service = SimpleNamespace(
            obtener_presupuesto=lambda _session, quote_id: quote if quote_id == 10 else None,
            cancelar_presupuesto=lambda **kwargs: None,
        )

        with patch(
            "pos_uniformes.services.quote_action_service._resolve_quote_action_dependencies",
            return_value=(fake_service, object()),
        ):
            cancel_quote(session, quote_id=10, user_id=7)


if __name__ == "__main__":
    unittest.main()
