from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services import settings_marketing_action_service
from pos_uniformes.services.settings_marketing_action_service import (
    load_settings_marketing_history_rows,
)


class SettingsMarketingActionServiceTests(unittest.TestCase):
    def test_ya_no_hay_recalcular_niveles(self) -> None:
        # 2026-11-12: «el nivel viejo retíralo» (Daniel).
        self.assertFalse(hasattr(settings_marketing_action_service, "recalculate_settings_loyalty_levels"))

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
