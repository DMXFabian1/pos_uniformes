"""Tests para MarketingAuditService."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pos_uniformes.services.marketing_audit_service import (
    MarketingAuditField,
    MarketingAuditService,
)


# ---------------------------------------------------------------------------
# _stringify
# ---------------------------------------------------------------------------

class StringifyTests(unittest.TestCase):

    def test_none_returns_none(self) -> None:
        self.assertIsNone(MarketingAuditService._stringify(None))

    def test_decimal_formats_two_places(self) -> None:
        self.assertEqual(MarketingAuditService._stringify(Decimal("10.5")), "10.50")

    def test_string_passthrough(self) -> None:
        self.assertEqual(MarketingAuditService._stringify("hola"), "hola")

    def test_integer_converted_to_string(self) -> None:
        self.assertEqual(MarketingAuditService._stringify(42), "42")


# ---------------------------------------------------------------------------
# log_field_changes
# ---------------------------------------------------------------------------

class LogFieldChangesTests(unittest.TestCase):

    def _make_actor(self):
        return SimpleNamespace(id=1, rol=SimpleNamespace(value="ADMIN"))

    def test_logs_changed_fields_only(self) -> None:
        session = MagicMock()
        actor = self._make_actor()

        fields = [
            MarketingAuditField(
                field_key="discount_leal",
                section="lealtad",
                label="Descuento Leal",
                previous_value=Decimal("10.00"),
                new_value=Decimal("15.00"),
            ),
            MarketingAuditField(
                field_key="discount_basico",
                section="lealtad",
                label="Descuento Basico",
                previous_value=Decimal("5.00"),
                new_value=Decimal("5.00"),  # sin cambio
            ),
        ]

        with patch("pos_uniformes.services.marketing_audit_service.CambioMarketingConfiguracion",
                   side_effect=lambda **kw: SimpleNamespace(**kw)):
            changes = MarketingAuditService.log_field_changes(session, actor_user=actor, fields=fields)

        # Solo el primer campo cambió
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].campo, "discount_leal")
        session.add.assert_called_once()

    def test_no_changes_returns_empty_list(self) -> None:
        session = MagicMock()
        actor = self._make_actor()

        fields = [
            MarketingAuditField(
                field_key="discount_leal",
                section="lealtad",
                label="Descuento Leal",
                previous_value=Decimal("10.00"),
                new_value=Decimal("10.00"),
            ),
        ]

        with patch("pos_uniformes.services.marketing_audit_service.CambioMarketingConfiguracion",
                   side_effect=lambda **kw: SimpleNamespace(**kw)):
            changes = MarketingAuditService.log_field_changes(session, actor_user=actor, fields=fields)

        self.assertEqual(changes, [])
        session.add.assert_not_called()

    def test_none_previous_to_value_is_logged(self) -> None:
        session = MagicMock()
        actor = self._make_actor()

        fields = [
            MarketingAuditField(
                field_key="whatsapp_template",
                section="whatsapp",
                label="Template",
                previous_value=None,
                new_value="Hola {nombre}",
            ),
        ]

        with patch("pos_uniformes.services.marketing_audit_service.CambioMarketingConfiguracion",
                   side_effect=lambda **kw: SimpleNamespace(**kw)):
            changes = MarketingAuditService.log_field_changes(session, actor_user=actor, fields=fields)

        self.assertEqual(len(changes), 1)
        self.assertIsNone(changes[0].valor_anterior)
        self.assertEqual(changes[0].valor_nuevo, "Hola {nombre}")


if __name__ == "__main__":
    unittest.main()
