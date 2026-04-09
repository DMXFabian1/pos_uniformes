from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from pos_uniformes.services.employee_identity_service import EmployeeIdentityService


class EmployeeIdentityServiceTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
