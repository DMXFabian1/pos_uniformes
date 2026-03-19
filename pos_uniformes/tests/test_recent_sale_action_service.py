from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.recent_sale_action_service import cancel_recent_sale


class RecentSaleActionServiceTests(unittest.TestCase):
    def test_cancel_recent_sale_uses_venta_service(self) -> None:
        sale = object()
        admin = object()
        session = SimpleNamespace(
            get=lambda model, item_id: sale if item_id == 10 else admin if item_id == 3 else None
        )
        venta_service = SimpleNamespace(cancelar_venta=lambda **kwargs: None)

        with patch(
            "pos_uniformes.services.recent_sale_action_service._resolve_recent_sale_action_dependencies",
            return_value=(venta_service, object(), object()),
        ):
            cancel_recent_sale(session, sale_id=10, admin_user_id=3)


if __name__ == "__main__":
    unittest.main()
