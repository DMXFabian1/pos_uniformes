from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.settings_marketing_action_service import (
    SettingsMarketingRecalculationResult,
    load_settings_marketing_history_rows,
    recalculate_settings_loyalty_levels,
)


class SettingsMarketingActionServiceTests(unittest.TestCase):
    def test_recalculate_settings_loyalty_levels(self) -> None:
        admin_user = object()
        session = SimpleNamespace(get=lambda model, item_id: admin_user if item_id == 7 else None)
        fake_loyalty = SimpleNamespace(recalculate_all_clients=lambda *args, **kwargs: {"total": 9, "changed": 2})

        with patch(
            "pos_uniformes.services.settings_marketing_action_service._resolve_settings_marketing_recalc_dependencies",
            return_value=(fake_loyalty, object()),
        ):
            result = recalculate_settings_loyalty_levels(session, admin_user_id=7)

        self.assertEqual(result, SettingsMarketingRecalculationResult(total=9, changed=2))

    def test_load_settings_marketing_history_rows(self) -> None:
        change = SimpleNamespace(
            created_at=datetime(2026, 3, 19, 10, 0),
            usuario=SimpleNamespace(username="admin"),
            rol_usuario="ADMIN",
            seccion="reglas",
            etiqueta_campo="Campo",
            valor_anterior="1",
            valor_nuevo="2",
        )
        fake_audit = SimpleNamespace(list_recent=lambda session, limit=120: [change])

        with patch(
            "pos_uniformes.services.settings_marketing_action_service._resolve_settings_marketing_history_dependencies",
            return_value=fake_audit,
        ):
            rows = load_settings_marketing_history_rows(object(), limit=120)

        self.assertEqual(rows[0]["username"], "admin")
        self.assertEqual(rows[0]["section_label"], "Reglas")


if __name__ == "__main__":
    unittest.main()
