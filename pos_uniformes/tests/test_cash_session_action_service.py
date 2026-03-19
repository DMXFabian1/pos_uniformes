from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pos_uniformes.services.cash_session_action_service import (
    close_cash_session_action,
    correct_cash_opening_action,
    load_cash_cut_prompt_snapshot,
    load_cash_movement_target_snapshot,
    load_cash_opening_amount,
    load_cash_opening_suggested_amount,
    load_cash_session_gate_snapshot,
    open_cash_session_action,
    register_cash_movement_action,
)


class _FakeMovementType:
    REACTIVO = "reactivo"
    INGRESO = "ingreso"
    RETIRO = "retiro"


class CashSessionActionServiceTests(unittest.TestCase):
    def test_load_cash_session_gate_snapshot_detects_active_session(self) -> None:
        active_session = SimpleNamespace(
            id=9,
            abierta_por=SimpleNamespace(nombre_completo="Daniel"),
            abierta_at=datetime(2026, 3, 19, 10, 30),
            monto_apertura=Decimal("500.00"),
        )
        fake_service = SimpleNamespace(obtener_sesion_activa=lambda session: active_session)
        session = SimpleNamespace(get=lambda model, id: None)

        with patch(
            "pos_uniformes.services.cash_session_action_service._resolve_cash_session_action_dependencies",
            return_value=(fake_service, object(), object(), _FakeMovementType),
        ):
            snapshot = load_cash_session_gate_snapshot(
                session,
                user_id=3,
                is_stale_session=lambda current: True,
            )

        self.assertTrue(snapshot.has_active_session)
        self.assertEqual(snapshot.active_session_id, 9)
        self.assertTrue(snapshot.requires_cut)

    def test_open_cash_session_action_opens_with_authenticated_user(self) -> None:
        user_model = object()
        user = SimpleNamespace(id=2)
        created_session = SimpleNamespace(id=11)
        session = SimpleNamespace(
            get=lambda model, id: user if model is user_model else None,
            commit=lambda: None,
        )
        fake_service = SimpleNamespace(
            abrir_sesion=lambda **kwargs: created_session,
        )

        with patch(
            "pos_uniformes.services.cash_session_action_service._resolve_cash_session_action_dependencies",
            return_value=(fake_service, user_model, object(), _FakeMovementType),
        ):
            session_id = open_cash_session_action(
                session,
                user_id=2,
                opening_amount=Decimal("300.00"),
                opening_note="Inicio",
            )

        self.assertEqual(session_id, 11)

    def test_load_cash_movement_target_snapshot_returns_target_for_reactivo(self) -> None:
        cash_session_model = object()
        cash_session = SimpleNamespace(monto_apertura=Decimal("200.00"))
        resumen = SimpleNamespace(reactivo_total=Decimal("50.00"))
        session = SimpleNamespace(get=lambda model, id: cash_session if model is cash_session_model else None)
        fake_service = SimpleNamespace(resumir_sesion=lambda session, cash_session: resumen)

        with patch(
            "pos_uniformes.services.cash_session_action_service._resolve_cash_session_action_dependencies",
            return_value=(fake_service, object(), cash_session_model, _FakeMovementType),
        ):
            snapshot = load_cash_movement_target_snapshot(
                session,
                active_cash_session_id=5,
                movement_type=_FakeMovementType.REACTIVO,
            )

        self.assertEqual(snapshot.target_total, Decimal("250.00"))

    def test_register_cash_movement_action_uses_service_and_commits(self) -> None:
        cash_session_model = object()
        user_model = object()
        cash_session = SimpleNamespace(id=7)
        user = SimpleNamespace(id=4)
        session = SimpleNamespace(
            get=lambda model, id: cash_session if model is cash_session_model else user,
            commit=lambda: None,
        )
        captured: dict[str, object] = {}

        def _registrar_movimiento(**kwargs):
            captured.update(kwargs)

        fake_service = SimpleNamespace(registrar_movimiento=_registrar_movimiento)

        with patch(
            "pos_uniformes.services.cash_session_action_service._resolve_cash_session_action_dependencies",
            return_value=(fake_service, user_model, cash_session_model, _FakeMovementType),
        ):
            register_cash_movement_action(
                session,
                active_cash_session_id=7,
                user_id=4,
                movement_type=_FakeMovementType.INGRESO,
                amount=Decimal("100.00"),
                concept="Venta extra",
            )

        self.assertEqual(captured["tipo"], _FakeMovementType.INGRESO)
        self.assertEqual(captured["monto"], Decimal("100.00"))

    def test_load_cash_opening_amount_returns_zero_without_session(self) -> None:
        session = SimpleNamespace(get=lambda model, id: None)

        with patch(
            "pos_uniformes.services.cash_session_action_service._resolve_cash_session_action_dependencies",
            return_value=(object(), object(), object(), _FakeMovementType),
        ):
            amount = load_cash_opening_amount(session, active_cash_session_id=8)

        self.assertEqual(amount, Decimal("0.00"))

    def test_correct_cash_opening_action_returns_previous_and_new_amount(self) -> None:
        cash_session_model = object()
        user_model = object()
        cash_session = SimpleNamespace(monto_apertura=Decimal("300.00"))
        user = SimpleNamespace(id=1)
        session = SimpleNamespace(
            get=lambda model, id: cash_session if model is cash_session_model else user,
            commit=lambda: None,
        )
        fake_service = SimpleNamespace(corregir_apertura=lambda **kwargs: cash_session)

        with patch(
            "pos_uniformes.services.cash_session_action_service._resolve_cash_session_action_dependencies",
            return_value=(fake_service, user_model, cash_session_model, _FakeMovementType),
        ):
            result = correct_cash_opening_action(
                session,
                active_cash_session_id=5,
                user_id=1,
                new_amount=Decimal("450.00"),
                note="Ajuste",
            )

        self.assertEqual(result.previous_amount, Decimal("300.00"))
        self.assertEqual(result.new_amount, Decimal("450.00"))

    def test_load_cash_cut_prompt_snapshot_maps_summary(self) -> None:
        cash_session_model = object()
        cash_session = SimpleNamespace(
            abierta_at=datetime(2026, 3, 19, 9, 0),
            monto_apertura=Decimal("200.00"),
        )
        resumen = SimpleNamespace(
            reactivo_count=1,
            reactivo_total=Decimal("20.00"),
            ingresos_count=2,
            ingresos_total=Decimal("50.00"),
            retiros_count=1,
            retiros_total=Decimal("10.00"),
            ventas_efectivo_count=3,
            efectivo_ventas=Decimal("600.00"),
            abonos_efectivo_count=1,
            efectivo_abonos=Decimal("100.00"),
            esperado_en_caja=Decimal("960.00"),
        )
        session = SimpleNamespace(get=lambda model, id: cash_session if model is cash_session_model else None)
        fake_service = SimpleNamespace(resumir_sesion=lambda session, cash_session: resumen)

        with patch(
            "pos_uniformes.services.cash_session_action_service._resolve_cash_session_action_dependencies",
            return_value=(fake_service, object(), cash_session_model, _FakeMovementType),
        ):
            snapshot = load_cash_cut_prompt_snapshot(session, active_cash_session_id=4)

        self.assertEqual(snapshot.opening_amount, Decimal("200.00"))
        self.assertEqual(snapshot.expected_amount, Decimal("960.00"))

    def test_close_cash_session_action_maps_closed_session_amounts(self) -> None:
        cash_session_model = object()
        user_model = object()
        cash_session = SimpleNamespace(id=3)
        user = SimpleNamespace(id=1)
        closed_session = SimpleNamespace(
            monto_esperado_cierre=Decimal("800.00"),
            monto_cierre_declarado=Decimal("790.00"),
            diferencia_cierre=Decimal("-10.00"),
        )
        session = SimpleNamespace(
            get=lambda model, id: cash_session if model is cash_session_model else user,
            commit=lambda: None,
        )
        fake_service = SimpleNamespace(cerrar_sesion=lambda **kwargs: closed_session)

        with patch(
            "pos_uniformes.services.cash_session_action_service._resolve_cash_session_action_dependencies",
            return_value=(fake_service, user_model, cash_session_model, _FakeMovementType),
        ):
            result = close_cash_session_action(
                session,
                active_cash_session_id=3,
                user_id=1,
                counted_amount=Decimal("790.00"),
                closing_note="Fin",
            )

        self.assertEqual(result.expected_amount, Decimal("800.00"))
        self.assertEqual(result.counted_amount, Decimal("790.00"))
        self.assertEqual(result.difference, Decimal("-10.00"))

    def test_load_cash_opening_suggested_amount_delegates_to_service(self) -> None:
        fake_service = SimpleNamespace(obtener_ultimo_reactivo_sugerido=lambda session: Decimal("250.00"))

        with patch(
            "pos_uniformes.services.cash_session_action_service._resolve_cash_session_action_dependencies",
            return_value=(fake_service, object(), object(), _FakeMovementType),
        ):
            amount = load_cash_opening_suggested_amount(object())

        self.assertEqual(amount, Decimal("250.00"))


if __name__ == "__main__":
    unittest.main()
