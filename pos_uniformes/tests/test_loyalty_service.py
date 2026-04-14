"""Tests para LoyaltyService."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock

from pos_uniformes.database.models import NivelLealtad, TipoCliente, RolUsuario
from pos_uniformes.services.loyalty_service import LoyaltyService, LoyaltyProgramRules


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rules(
    *,
    review_window_days: int = 365,
    leal_spend_threshold: str = "3000.00",
    leal_purchase_count_threshold: int = 3,
    leal_purchase_sum_threshold: str = "2000.00",
    discount_basico: str = "5.00",
    discount_leal: str = "10.00",
    discount_profesor: str = "15.00",
    discount_mayorista: str = "20.00",
) -> LoyaltyProgramRules:
    return LoyaltyProgramRules(
        review_window_days=review_window_days,
        leal_spend_threshold=Decimal(leal_spend_threshold),
        leal_purchase_count_threshold=leal_purchase_count_threshold,
        leal_purchase_sum_threshold=Decimal(leal_purchase_sum_threshold),
        discount_basico=Decimal(discount_basico),
        discount_leal=Decimal(discount_leal),
        discount_profesor=Decimal(discount_profesor),
        discount_mayorista=Decimal(discount_mayorista),
    )


def _make_client(
    *,
    id: int = 1,
    tipo_cliente: TipoCliente = TipoCliente.GENERAL,
    nivel_lealtad: NivelLealtad = NivelLealtad.BASICO,
    descuento_preferente: str = "0.00",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        tipo_cliente=tipo_cliente,
        nivel_lealtad=nivel_lealtad,
        descuento_preferente=Decimal(descuento_preferente),
        nivel_asignado_por_user_id=None,
        nivel_asignado_por_rol=None,
        nivel_asignacion_motivo=None,
    )


def _make_actor(*, rol: RolUsuario = RolUsuario.CAJERO, id: int = 99) -> SimpleNamespace:
    return SimpleNamespace(id=id, rol=rol)


# ---------------------------------------------------------------------------
# coerce_level
# ---------------------------------------------------------------------------

class CoerceLevelTests(unittest.TestCase):

    def test_enum_passes_through(self) -> None:
        self.assertEqual(LoyaltyService.coerce_level(NivelLealtad.LEAL), NivelLealtad.LEAL)

    def test_valid_string_converted(self) -> None:
        self.assertEqual(LoyaltyService.coerce_level("leal"), NivelLealtad.LEAL)
        self.assertEqual(LoyaltyService.coerce_level("MAYORISTA"), NivelLealtad.MAYORISTA)
        self.assertEqual(LoyaltyService.coerce_level("  profesor  "), NivelLealtad.PROFESOR)

    def test_none_returns_basico(self) -> None:
        self.assertEqual(LoyaltyService.coerce_level(None), NivelLealtad.BASICO)

    def test_empty_string_returns_basico(self) -> None:
        self.assertEqual(LoyaltyService.coerce_level(""), NivelLealtad.BASICO)
        self.assertEqual(LoyaltyService.coerce_level("   "), NivelLealtad.BASICO)


# ---------------------------------------------------------------------------
# visual_spec
# ---------------------------------------------------------------------------

class VisualSpecTests(unittest.TestCase):

    def test_returns_spec_for_each_level(self) -> None:
        for level in NivelLealtad:
            spec = LoyaltyService.visual_spec(level)
            self.assertEqual(spec.level, level)
            self.assertTrue(spec.label)
            self.assertTrue(spec.primary_color.startswith("#"))
            self.assertTrue(spec.secondary_color.startswith("#"))

    def test_none_returns_basico_spec(self) -> None:
        spec = LoyaltyService.visual_spec(None)
        self.assertEqual(spec.level, NivelLealtad.BASICO)

    def test_string_input_resolves_correctly(self) -> None:
        spec = LoyaltyService.visual_spec("leal")
        self.assertEqual(spec.level, NivelLealtad.LEAL)

    def test_all_levels_have_distinct_primary_colors(self) -> None:
        colors = {LoyaltyService.visual_spec(level).primary_color for level in NivelLealtad}
        self.assertEqual(len(colors), len(list(NivelLealtad)))


# ---------------------------------------------------------------------------
# default_level_for_client_type
# ---------------------------------------------------------------------------

class DefaultLevelForClientTypeTests(unittest.TestCase):

    def test_general_returns_basico(self) -> None:
        self.assertEqual(
            LoyaltyService.default_level_for_client_type(TipoCliente.GENERAL),
            NivelLealtad.BASICO,
        )

    def test_profesor_returns_profesor(self) -> None:
        self.assertEqual(
            LoyaltyService.default_level_for_client_type(TipoCliente.PROFESOR),
            NivelLealtad.PROFESOR,
        )

    def test_mayorista_returns_mayorista(self) -> None:
        self.assertEqual(
            LoyaltyService.default_level_for_client_type(TipoCliente.MAYORISTA),
            NivelLealtad.MAYORISTA,
        )

    def test_none_returns_basico(self) -> None:
        self.assertEqual(
            LoyaltyService.default_level_for_client_type(None),
            NivelLealtad.BASICO,
        )

    def test_string_tipo_resolved(self) -> None:
        self.assertEqual(
            LoyaltyService.default_level_for_client_type("PROFESOR"),
            NivelLealtad.PROFESOR,
        )


# ---------------------------------------------------------------------------
# resolve_initial_level
# ---------------------------------------------------------------------------

class ResolveInitialLevelTests(unittest.TestCase):

    def test_admin_can_set_any_level(self) -> None:
        self.assertEqual(
            LoyaltyService.resolve_initial_level(RolUsuario.ADMIN, NivelLealtad.LEAL),
            NivelLealtad.LEAL,
        )
        self.assertEqual(
            LoyaltyService.resolve_initial_level(RolUsuario.ADMIN, NivelLealtad.MAYORISTA),
            NivelLealtad.MAYORISTA,
        )

    def test_cajero_always_gets_basico(self) -> None:
        self.assertEqual(
            LoyaltyService.resolve_initial_level(RolUsuario.CAJERO, NivelLealtad.LEAL),
            NivelLealtad.BASICO,
        )

    def test_admin_with_none_level_returns_basico(self) -> None:
        self.assertEqual(
            LoyaltyService.resolve_initial_level(RolUsuario.ADMIN, None),
            NivelLealtad.BASICO,
        )

    def test_string_role_resolved(self) -> None:
        self.assertEqual(
            LoyaltyService.resolve_initial_level("ADMIN", NivelLealtad.PROFESOR),
            NivelLealtad.PROFESOR,
        )


# ---------------------------------------------------------------------------
# discount_for_level
# ---------------------------------------------------------------------------

class DiscountForLevelTests(unittest.TestCase):

    def _patch_rules(self, rules: LoyaltyProgramRules):
        return patch.object(LoyaltyService, "_load_program_rules", return_value=rules)

    def test_returns_correct_discount_per_level(self) -> None:
        rules = _make_rules(
            discount_basico="5.00",
            discount_leal="10.00",
            discount_profesor="15.00",
            discount_mayorista="20.00",
        )
        session = MagicMock()

        with self._patch_rules(rules):
            self.assertEqual(
                LoyaltyService.discount_for_level(NivelLealtad.BASICO, session),
                Decimal("5.00"),
            )
            self.assertEqual(
                LoyaltyService.discount_for_level(NivelLealtad.LEAL, session),
                Decimal("10.00"),
            )
            self.assertEqual(
                LoyaltyService.discount_for_level(NivelLealtad.PROFESOR, session),
                Decimal("15.00"),
            )
            self.assertEqual(
                LoyaltyService.discount_for_level(NivelLealtad.MAYORISTA, session),
                Decimal("20.00"),
            )

    def test_result_always_has_two_decimal_places(self) -> None:
        rules = _make_rules(discount_leal="10.5")
        session = MagicMock()

        with self._patch_rules(rules):
            result = LoyaltyService.discount_for_level(NivelLealtad.LEAL, session)
            self.assertEqual(result, Decimal("10.50"))
            self.assertEqual(str(result), "10.50")

    def test_unknown_level_falls_back_to_basico_discount(self) -> None:
        rules = _make_rules(discount_basico="5.00")
        session = MagicMock()

        with self._patch_rules(rules):
            # coerce_level con None → BASICO, fallback al mapping de BASICO
            result = LoyaltyService.discount_for_level(None, session)
            self.assertEqual(result, Decimal("5.00"))


# ---------------------------------------------------------------------------
# assign_level
# ---------------------------------------------------------------------------

class AssignLevelTests(unittest.TestCase):

    def test_sets_nivel_lealtad(self) -> None:
        client = _make_client()
        actor = _make_actor(rol=RolUsuario.ADMIN)

        with patch.object(LoyaltyService, "discount_for_level", return_value=Decimal("10.00")):
            LoyaltyService.assign_level(
                client,
                level=NivelLealtad.LEAL,
                actor_user=actor,
                reason="prueba",
            )

        self.assertEqual(client.nivel_lealtad, NivelLealtad.LEAL)

    def test_sets_descuento_preferente(self) -> None:
        client = _make_client()
        actor = _make_actor(rol=RolUsuario.ADMIN)

        with patch.object(LoyaltyService, "discount_for_level", return_value=Decimal("15.00")):
            LoyaltyService.assign_level(
                client,
                level=NivelLealtad.PROFESOR,
                actor_user=actor,
                reason="asignacion manual",
            )

        self.assertEqual(Decimal(str(client.descuento_preferente)), Decimal("15.00"))

    def test_records_actor_and_reason(self) -> None:
        client = _make_client()
        actor = _make_actor(id=42, rol=RolUsuario.ADMIN)

        with patch.object(LoyaltyService, "discount_for_level", return_value=Decimal("20.00")):
            LoyaltyService.assign_level(
                client,
                level=NivelLealtad.MAYORISTA,
                actor_user=actor,
                reason="cliente mayorista confirmado",
            )

        self.assertEqual(client.nivel_asignado_por_user_id, 42)
        self.assertEqual(client.nivel_asignacion_motivo, "cliente mayorista confirmado")

    def test_empty_reason_defaults_to_ajuste_nivel(self) -> None:
        client = _make_client()
        actor = _make_actor()

        with patch.object(LoyaltyService, "discount_for_level", return_value=Decimal("5.00")):
            LoyaltyService.assign_level(
                client,
                level=NivelLealtad.BASICO,
                actor_user=actor,
                reason="   ",
            )

        self.assertEqual(client.nivel_asignacion_motivo, "ajuste_nivel")


# ---------------------------------------------------------------------------
# evaluate_auto_level
# ---------------------------------------------------------------------------

class EvaluateAutoLevelTests(unittest.TestCase):

    def _mock_session(self, *, count: int, total: str) -> MagicMock:
        session = MagicMock()
        session.execute.return_value.one.return_value = (count, Decimal(total))
        return session

    def test_profesor_type_always_returns_profesor(self) -> None:
        client = _make_client(tipo_cliente=TipoCliente.PROFESOR)
        session = MagicMock()

        result = LoyaltyService.evaluate_auto_level(session, client)

        self.assertEqual(result, NivelLealtad.PROFESOR)
        session.execute.assert_not_called()

    def test_mayorista_type_always_returns_mayorista(self) -> None:
        client = _make_client(tipo_cliente=TipoCliente.MAYORISTA)
        session = MagicMock()

        result = LoyaltyService.evaluate_auto_level(session, client)

        self.assertEqual(result, NivelLealtad.MAYORISTA)
        session.execute.assert_not_called()

    def test_general_client_below_thresholds_returns_basico(self) -> None:
        client = _make_client()
        rules = _make_rules(
            leal_spend_threshold="3000.00",
            leal_purchase_count_threshold=3,
            leal_purchase_sum_threshold="2000.00",
        )
        session = self._mock_session(count=1, total="500.00")

        with patch.object(LoyaltyService, "_load_program_rules", return_value=rules):
            result = LoyaltyService.evaluate_auto_level(session, client)

        self.assertEqual(result, NivelLealtad.BASICO)

    def test_general_client_exceeds_spend_threshold_returns_leal(self) -> None:
        client = _make_client()
        rules = _make_rules(leal_spend_threshold="3000.00")
        session = self._mock_session(count=1, total="3000.00")

        with patch.object(LoyaltyService, "_load_program_rules", return_value=rules):
            result = LoyaltyService.evaluate_auto_level(session, client)

        self.assertEqual(result, NivelLealtad.LEAL)

    def test_general_client_meets_count_and_sum_threshold_returns_leal(self) -> None:
        client = _make_client()
        rules = _make_rules(
            leal_spend_threshold="3000.00",
            leal_purchase_count_threshold=3,
            leal_purchase_sum_threshold="2000.00",
        )
        session = self._mock_session(count=3, total="2000.00")

        with patch.object(LoyaltyService, "_load_program_rules", return_value=rules):
            result = LoyaltyService.evaluate_auto_level(session, client)

        self.assertEqual(result, NivelLealtad.LEAL)

    def test_count_threshold_met_but_sum_too_low_returns_basico(self) -> None:
        client = _make_client()
        rules = _make_rules(
            leal_spend_threshold="3000.00",
            leal_purchase_count_threshold=3,
            leal_purchase_sum_threshold="2000.00",
        )
        session = self._mock_session(count=5, total="1999.99")

        with patch.object(LoyaltyService, "_load_program_rules", return_value=rules):
            result = LoyaltyService.evaluate_auto_level(session, client)

        self.assertEqual(result, NivelLealtad.BASICO)

    def test_client_with_no_id_returns_current_level(self) -> None:
        client = _make_client(id=None, nivel_lealtad=NivelLealtad.LEAL)
        client.id = None
        session = MagicMock()

        result = LoyaltyService.evaluate_auto_level(session, client)

        self.assertEqual(result, NivelLealtad.LEAL)
        session.execute.assert_not_called()


# ---------------------------------------------------------------------------
# recalculate_all_clients
# ---------------------------------------------------------------------------

class RecalculateAllClientsTests(unittest.TestCase):

    def test_returns_total_and_changed_counts(self) -> None:
        client_a = _make_client(id=1, nivel_lealtad=NivelLealtad.BASICO)
        client_b = _make_client(id=2, nivel_lealtad=NivelLealtad.LEAL)

        session = MagicMock()
        session.scalars.return_value.all.return_value = [client_a, client_b]
        actor = _make_actor(rol=RolUsuario.ADMIN)

        def fake_refresh(sess, client, *, actor_user, reason, reference_time=None):
            # Simula que client_a sube de nivel
            if client.id == 1:
                client.nivel_lealtad = NivelLealtad.LEAL
                client.descuento_preferente = Decimal("10.00")
            session.add(client)
            return client

        with patch.object(LoyaltyService, "refresh_client_level_from_sales", side_effect=fake_refresh):
            result = LoyaltyService.recalculate_all_clients(
                session,
                actor_user=actor,
                reason="recalculo periodico",
            )

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["changed"], 1)


if __name__ == "__main__":
    unittest.main()
