"""Tests para AuthService."""

from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pos_uniformes.services.auth_service import AuthService, PBKDF2_PREFIX


# ---------------------------------------------------------------------------
# hash_password
# ---------------------------------------------------------------------------

class HashPasswordTests(unittest.TestCase):

    def test_empty_password_raises(self) -> None:
        with self.assertRaises(ValueError):
            AuthService.hash_password("")

    def test_returns_pbkdf2_format(self) -> None:
        h = AuthService.hash_password("secreto123")
        parts = h.split("$")
        self.assertEqual(parts[0], PBKDF2_PREFIX)
        self.assertEqual(len(parts), 4)

    def test_different_calls_produce_different_hashes(self) -> None:
        h1 = AuthService.hash_password("misma_clave")
        h2 = AuthService.hash_password("misma_clave")
        # La sal es aleatoria — los hashes deben diferir
        self.assertNotEqual(h1, h2)

    def test_hash_contains_iteration_count(self) -> None:
        h = AuthService.hash_password("clave")
        _, iterations, _, _ = h.split("$")
        self.assertGreater(int(iterations), 0)


# ---------------------------------------------------------------------------
# verify_password
# ---------------------------------------------------------------------------

class VerifyPasswordTests(unittest.TestCase):

    def test_correct_password_returns_true(self) -> None:
        stored = AuthService.hash_password("mi_clave")
        self.assertTrue(AuthService.verify_password("mi_clave", stored))

    def test_wrong_password_returns_false(self) -> None:
        stored = AuthService.hash_password("mi_clave")
        self.assertFalse(AuthService.verify_password("otra_clave", stored))

    def test_empty_password_against_hash_returns_false(self) -> None:
        stored = AuthService.hash_password("mi_clave")
        self.assertFalse(AuthService.verify_password("", stored))

    def test_malformed_hash_returns_false(self) -> None:
        self.assertFalse(AuthService.verify_password("clave", "no_es_un_hash_valido"))

    def test_wrong_prefix_returns_false(self) -> None:
        self.assertFalse(AuthService.verify_password("clave", "otro_prefix$120000$salt$digest"))

    def test_hash_with_missing_parts_returns_false(self) -> None:
        self.assertFalse(AuthService.verify_password("clave", f"{PBKDF2_PREFIX}$120000$solodospartes"))

    def test_plain_text_hash_backwards_compat(self) -> None:
        # Seeds de datos iniciales pueden tener contraseña en texto plano
        self.assertTrue(AuthService.verify_password("admin123", "admin123"))

    def test_plain_text_hash_wrong_password(self) -> None:
        self.assertFalse(AuthService.verify_password("otro", "admin123"))


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------

class AuthenticateTests(unittest.TestCase):

    def _make_user(self, *, username: str, password: str, plain: bool = False) -> SimpleNamespace:
        password_hash = password if plain else AuthService.hash_password(password)
        return SimpleNamespace(
            username=username,
            password_hash=password_hash,
            activo=True,
        )

    def _session_returning(self, user) -> MagicMock:
        session = MagicMock()
        session.scalar.return_value = user
        return session

    def test_returns_user_on_correct_credentials(self) -> None:
        user = self._make_user(username="cajero", password="clave123")
        session = self._session_returning(user)

        result = AuthService.authenticate(session, "cajero", "clave123")

        self.assertIs(result, user)

    def test_returns_none_when_user_not_found(self) -> None:
        session = self._session_returning(None)

        result = AuthService.authenticate(session, "noexiste", "clave")

        self.assertIsNone(result)

    def test_returns_none_on_wrong_password(self) -> None:
        user = self._make_user(username="cajero", password="correcta")
        session = self._session_returning(user)

        result = AuthService.authenticate(session, "cajero", "incorrecta")

        self.assertIsNone(result)

    def test_upgrades_plain_text_hash_on_login(self) -> None:
        user = self._make_user(username="admin", password="admin123", plain=True)
        session = self._session_returning(user)

        result = AuthService.authenticate(session, "admin", "admin123")

        self.assertIsNotNone(result)
        # El hash debe haberse actualizado al formato pbkdf2
        self.assertTrue(result.password_hash.startswith(f"{PBKDF2_PREFIX}$"))
        session.add.assert_called_once_with(user)

    def test_pbkdf2_hash_not_upgraded_again(self) -> None:
        user = self._make_user(username="cajero", password="clave123")
        session = self._session_returning(user)

        AuthService.authenticate(session, "cajero", "clave123")

        # No debe llamar session.add porque ya era pbkdf2
        session.add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
