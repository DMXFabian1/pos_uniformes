"""Tests para UserService."""

from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pos_uniformes.database.models import RolUsuario
from pos_uniformes.services.user_service import UserService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin(*, id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(id=id, activo=True, rol=RolUsuario.ADMIN)


def _make_cajero(*, id: int = 2) -> SimpleNamespace:
    return SimpleNamespace(id=id, activo=True, rol=RolUsuario.CAJERO)


def _make_session(*, admin_count: int = 2, existing_username: object = None):
    session = MagicMock()
    session.flush.return_value = None
    session.scalar.side_effect = lambda stmt: (
        existing_username if existing_username is not None else None
    )
    # Para _active_admin_count usamos un scalar que devuelve el count
    # Sobrescribimos dependiendo del contexto en cada test
    session.scalar.return_value = None
    session._admin_count = admin_count
    return session


# ---------------------------------------------------------------------------
# _validar_admin
# ---------------------------------------------------------------------------

class ValidarAdminTests(unittest.TestCase):

    def test_inactive_admin_raises_permission_error(self) -> None:
        admin = SimpleNamespace(activo=False, rol=RolUsuario.ADMIN)
        with self.assertRaises(PermissionError):
            UserService._validar_admin(admin)

    def test_cajero_raises_permission_error(self) -> None:
        cajero = _make_cajero()
        with self.assertRaises(PermissionError):
            UserService._validar_admin(cajero)

    def test_active_admin_passes(self) -> None:
        admin = _make_admin()
        UserService._validar_admin(admin)  # no debe lanzar


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

class CreateUserTests(unittest.TestCase):

    def _session_no_duplicate(self) -> MagicMock:
        session = MagicMock()
        session.scalar.return_value = None
        return session

    def test_creates_user_successfully(self) -> None:
        admin = _make_admin()
        session = self._session_no_duplicate()

        with patch("pos_uniformes.services.user_service.AuthService.hash_password", return_value="hash"), \
             patch("pos_uniformes.services.user_service.select", return_value=MagicMock()), \
             patch("pos_uniformes.services.user_service.Usuario", side_effect=lambda **kw: SimpleNamespace(**kw)):
            user = UserService.create_user(
                session, admin,
                username="nuevocajero",
                nombre_completo="Juan Perez",
                rol=RolUsuario.CAJERO,
                password="secreto",
            )

        self.assertEqual(user.username, "nuevocajero")
        self.assertEqual(user.rol, RolUsuario.CAJERO)
        session.add.assert_called_once()

    def test_normalizes_username_to_lowercase(self) -> None:
        admin = _make_admin()
        session = self._session_no_duplicate()

        with patch("pos_uniformes.services.user_service.AuthService.hash_password", return_value="hash"), \
             patch("pos_uniformes.services.user_service.select", return_value=MagicMock()), \
             patch("pos_uniformes.services.user_service.Usuario", side_effect=lambda **kw: SimpleNamespace(**kw)):
            user = UserService.create_user(
                session, admin,
                username="  CAJERO01  ",
                nombre_completo="Ana",
                rol=RolUsuario.CAJERO,
                password="clave",
            )

        self.assertEqual(user.username, "cajero01")

    def test_raises_if_username_empty(self) -> None:
        admin = _make_admin()
        session = self._session_no_duplicate()

        with self.assertRaises(ValueError):
            UserService.create_user(session, admin, username="  ", nombre_completo="Ana", rol=RolUsuario.CAJERO, password="x")

    def test_raises_if_username_too_short(self) -> None:
        admin = _make_admin()
        session = self._session_no_duplicate()

        with self.assertRaises(ValueError):
            UserService.create_user(session, admin, username="ab", nombre_completo="Ana", rol=RolUsuario.CAJERO, password="x")

    def test_raises_if_nombre_completo_empty(self) -> None:
        admin = _make_admin()
        session = self._session_no_duplicate()

        with self.assertRaises(ValueError):
            UserService.create_user(session, admin, username="abc", nombre_completo="   ", rol=RolUsuario.CAJERO, password="x")

    def test_raises_if_username_already_exists(self) -> None:
        admin = _make_admin()
        session = MagicMock()
        session.scalar.return_value = SimpleNamespace(username="cajero01")  # ya existe

        with self.assertRaises(ValueError):
            UserService.create_user(session, admin, username="cajero01", nombre_completo="Ana", rol=RolUsuario.CAJERO, password="x")

    def test_non_admin_cannot_create_user(self) -> None:
        cajero = _make_cajero()
        session = self._session_no_duplicate()

        with self.assertRaises(PermissionError):
            UserService.create_user(session, cajero, username="nuevo", nombre_completo="X", rol=RolUsuario.CAJERO, password="x")


# ---------------------------------------------------------------------------
# toggle_active
# ---------------------------------------------------------------------------

class ToggleActiveTests(unittest.TestCase):

    def _session_with_admin_count(self, count: int) -> MagicMock:
        session = MagicMock()
        session.flush.return_value = None
        session.scalar.return_value = count
        return session

    def test_deactivates_cajero(self) -> None:
        admin = _make_admin(id=1)
        cajero = _make_cajero(id=2)
        session = self._session_with_admin_count(2)

        result = UserService.toggle_active(session, admin, cajero)

        self.assertFalse(result.activo)

    def test_activates_inactive_cajero(self) -> None:
        admin = _make_admin(id=1)
        cajero = SimpleNamespace(id=2, activo=False, rol=RolUsuario.CAJERO)
        session = self._session_with_admin_count(2)

        result = UserService.toggle_active(session, admin, cajero)

        self.assertTrue(result.activo)

    def test_cannot_deactivate_self(self) -> None:
        admin = _make_admin(id=1)
        session = self._session_with_admin_count(2)

        with self.assertRaises(ValueError):
            UserService.toggle_active(session, admin, admin)

    def test_cannot_deactivate_last_admin(self) -> None:
        admin = _make_admin(id=1)
        other_admin = SimpleNamespace(id=2, activo=True, rol=RolUsuario.ADMIN)
        session = self._session_with_admin_count(1)

        with self.assertRaises(ValueError):
            UserService.toggle_active(session, admin, other_admin)


# ---------------------------------------------------------------------------
# change_role
# ---------------------------------------------------------------------------

class ChangeRoleTests(unittest.TestCase):

    def _session_with_admin_count(self, count: int) -> MagicMock:
        session = MagicMock()
        session.flush.return_value = None
        session.scalar.return_value = count
        return session

    def test_changes_cajero_to_admin(self) -> None:
        admin = _make_admin(id=1)
        cajero = _make_cajero(id=2)
        session = self._session_with_admin_count(2)

        result = UserService.change_role(session, admin, cajero, RolUsuario.ADMIN)

        self.assertEqual(result.rol, RolUsuario.ADMIN)

    def test_same_role_is_noop(self) -> None:
        admin = _make_admin(id=1)
        cajero = _make_cajero(id=2)
        session = self._session_with_admin_count(2)

        result = UserService.change_role(session, admin, cajero, RolUsuario.CAJERO)

        self.assertEqual(result.rol, RolUsuario.CAJERO)
        session.add.assert_not_called()

    def test_cannot_remove_own_admin_role(self) -> None:
        admin = _make_admin(id=1)
        session = self._session_with_admin_count(2)

        with self.assertRaises(ValueError):
            UserService.change_role(session, admin, admin, RolUsuario.CAJERO)

    def test_cannot_remove_last_admin_role(self) -> None:
        admin = _make_admin(id=1)
        other_admin = SimpleNamespace(id=2, activo=True, rol=RolUsuario.ADMIN)
        session = self._session_with_admin_count(1)

        with self.assertRaises(ValueError):
            UserService.change_role(session, admin, other_admin, RolUsuario.CAJERO)


# ---------------------------------------------------------------------------
# change_password
# ---------------------------------------------------------------------------

class ChangePasswordTests(unittest.TestCase):

    def test_updates_password_hash(self) -> None:
        admin = _make_admin()
        target = _make_cajero()
        session = MagicMock()

        with patch("pos_uniformes.services.user_service.AuthService.hash_password", return_value="nuevo_hash"):
            result = UserService.change_password(session, admin, target, "nueva_clave")

        self.assertEqual(result.password_hash, "nuevo_hash")
        session.add.assert_called_once_with(target)


if __name__ == "__main__":
    unittest.main()
