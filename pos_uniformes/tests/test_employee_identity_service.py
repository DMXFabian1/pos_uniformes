from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from pos_uniformes.database.models import RolUsuario
from pos_uniformes.services.auth_service import AuthService
from pos_uniformes.services.employee_identity_service import EmployeeIdentityService


class EmployeeIdentityServiceTests(unittest.TestCase):
    def test_generate_employee_code_uses_next_numeric_suffix(self) -> None:
        session = Mock()
        session.scalar.return_value = 7

        code = EmployeeIdentityService.generate_employee_code(session)

        self.assertEqual(code, "VEND-8")

    def test_build_visible_employee_name_uses_first_and_last_token(self) -> None:
        self.assertEqual(
            EmployeeIdentityService.build_visible_employee_name("Guadalupe Gomez Ruiz"),
            "Guadalupe Ruiz",
        )

    def test_resolve_employee_by_qr_code_returns_active_employee(self) -> None:
        session = Mock()
        employee = SimpleNamespace(codigo="VEND-1", nombre_completo="Lupita Gomez", activo=True)
        session.scalar.return_value = employee

        resolved = EmployeeIdentityService.resolve_employee_by_qr_code(session, "EMP:VEND-1")

        self.assertIs(resolved, employee)

    def test_resolve_employee_by_qr_code_returns_none_for_inactive_employee(self) -> None:
        session = Mock()
        session.scalar.return_value = SimpleNamespace(codigo="VEND-1", nombre_completo="Lupita Gomez", activo=False)

        resolved = EmployeeIdentityService.resolve_employee_by_qr_code(session, "EMP:VEND-1")

        self.assertIsNone(resolved)

    def test_normalize_pin_requires_digits_and_length(self) -> None:
        self.assertEqual(EmployeeIdentityService.normalize_pin(" 634700 "), "634700")
        with self.assertRaisesRegex(ValueError, "solo numeros"):
            EmployeeIdentityService.normalize_pin("63A700")
        with self.assertRaisesRegex(ValueError, "entre 4 y 8"):
            EmployeeIdentityService.normalize_pin("123")

    def test_set_pin_hashes_value_and_marks_employee_with_pin(self) -> None:
        session = Mock()
        admin_user = SimpleNamespace(activo=True, rol=RolUsuario.ADMIN)
        employee = SimpleNamespace(pin_hash=None)

        updated = EmployeeIdentityService.set_pin(
            session,
            admin_user=admin_user,
            employee=employee,
            pin="634700",
        )

        self.assertIs(updated, employee)
        self.assertTrue(str(employee.pin_hash).startswith("pbkdf2_sha256$"))
        self.assertTrue(AuthService.verify_password("634700", str(employee.pin_hash)))
        self.assertTrue(EmployeeIdentityService.has_pin(employee))
        session.add.assert_called_once_with(employee)


if __name__ == "__main__":
    unittest.main()
