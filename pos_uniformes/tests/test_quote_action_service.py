from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock

from pos_uniformes.services.quote_action_service import cancel_quote, emit_quote


def _make_session(quote, user, *, user_id=7):
    return SimpleNamespace(get=lambda model, item_id: user if item_id == user_id else None)


def _fake_service(*, quote, emit_spy=None, cancel_spy=None):
    return SimpleNamespace(
        obtener_presupuesto=lambda _session, quote_id: quote,
        emitir_presupuesto=emit_spy or (lambda **kwargs: None),
        cancelar_presupuesto=cancel_spy or (lambda **kwargs: None),
    )


class EmitQuoteTests(unittest.TestCase):
    def _patch(self, fake_svc):
        return patch(
            "pos_uniformes.services.quote_action_service._resolve_quote_action_dependencies",
            return_value=(fake_svc, object()),
        )

    def test_happy_path_calls_emitir(self) -> None:
        quote = object()
        user = SimpleNamespace(username="cajero")
        called = []
        svc = _fake_service(quote=quote, emit_spy=lambda **kw: called.append(kw))
        session = _make_session(quote, user)
        with self._patch(svc):
            emit_quote(session, quote_id=10, user_id=7)
        self.assertEqual(len(called), 1)

    def test_kwargs_passed_to_emitir(self) -> None:
        quote = object()
        user = SimpleNamespace(username="admin")
        captured = {}
        svc = _fake_service(quote=quote, emit_spy=lambda **kw: captured.update(kw))
        session = _make_session(quote, user)
        with self._patch(svc):
            emit_quote(session, quote_id=5, user_id=7)
        self.assertIs(captured["presupuesto"], quote)
        self.assertIs(captured["usuario"], user)
        self.assertIs(captured["session"], session)

    def test_observacion_contains_username(self) -> None:
        quote = object()
        user = SimpleNamespace(username="vendedora")
        captured = {}
        svc = _fake_service(quote=quote, emit_spy=lambda **kw: captured.update(kw))
        session = _make_session(quote, user)
        with self._patch(svc):
            emit_quote(session, quote_id=1, user_id=7)
        self.assertIn("vendedora", captured["observacion"])

    def test_raises_when_quote_not_found(self) -> None:
        user = SimpleNamespace(username="admin")
        svc = _fake_service(quote=None)
        session = _make_session(None, user)
        with self._patch(svc):
            with self.assertRaises(ValueError):
                emit_quote(session, quote_id=99, user_id=7)

    def test_raises_when_user_not_found(self) -> None:
        quote = object()
        svc = _fake_service(quote=quote)
        session = _make_session(quote, None)
        with self._patch(svc):
            with self.assertRaises(ValueError):
                emit_quote(session, quote_id=1, user_id=99)

    def test_raises_when_both_not_found(self) -> None:
        svc = _fake_service(quote=None)
        session = _make_session(None, None)
        with self._patch(svc):
            with self.assertRaises(ValueError):
                emit_quote(session, quote_id=0, user_id=0)

    def test_emitir_not_called_on_missing_quote(self) -> None:
        user = SimpleNamespace(username="admin")
        called = []
        svc = _fake_service(quote=None, emit_spy=lambda **kw: called.append(kw))
        session = _make_session(None, user)
        with self._patch(svc):
            with self.assertRaises(ValueError):
                emit_quote(session, quote_id=99, user_id=7)
        self.assertEqual(called, [])


class CancelQuoteTests(unittest.TestCase):
    def _patch(self, fake_svc):
        return patch(
            "pos_uniformes.services.quote_action_service._resolve_quote_action_dependencies",
            return_value=(fake_svc, object()),
        )

    def test_happy_path_calls_cancelar(self) -> None:
        quote = object()
        user = SimpleNamespace(username="cajero")
        called = []
        svc = _fake_service(quote=quote, cancel_spy=lambda **kw: called.append(kw))
        session = _make_session(quote, user)
        with self._patch(svc):
            cancel_quote(session, quote_id=3, user_id=7)
        self.assertEqual(len(called), 1)

    def test_kwargs_passed_to_cancelar(self) -> None:
        quote = object()
        user = SimpleNamespace(username="admin")
        captured = {}
        svc = _fake_service(quote=quote, cancel_spy=lambda **kw: captured.update(kw))
        session = _make_session(quote, user)
        with self._patch(svc):
            cancel_quote(session, quote_id=3, user_id=7)
        self.assertIs(captured["presupuesto"], quote)
        self.assertIs(captured["usuario"], user)
        self.assertIs(captured["session"], session)

    def test_observacion_contains_username(self) -> None:
        quote = object()
        user = SimpleNamespace(username="gerente")
        captured = {}
        svc = _fake_service(quote=quote, cancel_spy=lambda **kw: captured.update(kw))
        session = _make_session(quote, user)
        with self._patch(svc):
            cancel_quote(session, quote_id=1, user_id=7)
        self.assertIn("gerente", captured["observacion"])

    def test_raises_when_quote_not_found(self) -> None:
        user = SimpleNamespace(username="admin")
        svc = _fake_service(quote=None)
        session = _make_session(None, user)
        with self._patch(svc):
            with self.assertRaises(ValueError):
                cancel_quote(session, quote_id=99, user_id=7)

    def test_raises_when_user_not_found(self) -> None:
        quote = object()
        svc = _fake_service(quote=quote)
        session = _make_session(quote, None)
        with self._patch(svc):
            with self.assertRaises(ValueError):
                cancel_quote(session, quote_id=1, user_id=99)

    def test_raises_when_both_not_found(self) -> None:
        svc = _fake_service(quote=None)
        session = _make_session(None, None)
        with self._patch(svc):
            with self.assertRaises(ValueError):
                cancel_quote(session, quote_id=0, user_id=0)

    def test_cancelar_not_called_on_missing_user(self) -> None:
        quote = object()
        called = []
        svc = _fake_service(quote=quote, cancel_spy=lambda **kw: called.append(kw))
        session = _make_session(quote, None)
        with self._patch(svc):
            with self.assertRaises(ValueError):
                cancel_quote(session, quote_id=1, user_id=99)
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
