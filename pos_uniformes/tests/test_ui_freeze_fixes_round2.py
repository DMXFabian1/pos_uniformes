"""Ronda 2 de fixes de congelamiento de UI.

1. statement_timeout en la conexión: una query colgada ya no congela la UI
   hasta los keepalives (~60s); el servidor la corta al límite configurado.
2. Búsquedas de Configuración (proveedores/clientes/empleadas) con debounce:
   antes cada tecla disparaba una query — y en proveedores/clientes el texto
   tecleado llegaba como `session` (bug: caía siempre a la vista de error).
3. Actividad de empleadas en batch: una sola query de ventas para todas
   (antes N+1 por empleada, por cada tecla).
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("POS_UNIFORMES_DB_HOST", "localhost")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pos_uniformes.database.connection import build_connect_args
from pos_uniformes.services.employee_activity_service import (
    load_employee_activity_snapshots,
)
from pos_uniformes.utils.config import Settings, _to_timeout_ms


class StatementTimeoutConfigTests(unittest.TestCase):
    def test_to_timeout_ms_parses_and_defaults(self) -> None:
        self.assertEqual(_to_timeout_ms("20000"), 20_000)
        self.assertEqual(_to_timeout_ms("0"), 0)
        self.assertEqual(_to_timeout_ms("abc"), 15_000)
        self.assertEqual(_to_timeout_ms("-5"), 15_000)

    def test_settings_default_and_env_override(self) -> None:
        with patch(
            "pos_uniformes.utils.config.load_runtime_env_overrides", return_value={}
        ):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("POS_UNIFORMES_DB_STATEMENT_TIMEOUT_MS", None)
                self.assertEqual(Settings.from_env().db_statement_timeout_ms, 15_000)
            with patch.dict(
                os.environ, {"POS_UNIFORMES_DB_STATEMENT_TIMEOUT_MS": "30000"}
            ):
                self.assertEqual(Settings.from_env().db_statement_timeout_ms, 30_000)

    def test_connect_args_include_statement_timeout(self) -> None:
        args = build_connect_args(15_000)
        self.assertEqual(args["options"], "-c statement_timeout=15000")
        self.assertEqual(args["connect_timeout"], 2)  # lo existente no cambia

    def test_connect_args_zero_disables_timeout(self) -> None:
        self.assertNotIn("options", build_connect_args(0))


class BatchEmployeeActivityTests(unittest.TestCase):
    def _employee(self, emp_id: int, codigo: str) -> SimpleNamespace:
        return SimpleNamespace(
            id=emp_id, codigo=codigo, nombre_completo=f"Emp {codigo}", activo=True
        )

    def _run(self, employees, ventas):
        session = MagicMock()
        session.scalars.return_value.all.return_value = ventas
        svc = "pos_uniformes.services"
        with patch(
            f"{svc}.employee_identity_service.EmployeeIdentityService.has_pin",
            return_value=False,
        ), patch(
            f"{svc}.employee_identity_service.EmployeeIdentityService.build_visible_employee_name",
            side_effect=lambda name: str(name),
        ), patch(
            "pos_uniformes.utils.qr_generator.QrGenerator.exists_for_employee",
            return_value=False,
        ), patch(
            f"{svc}.employee_card_service.EmployeeCardService.exists_for_employee",
            return_value=False,
        ):
            snapshots = load_employee_activity_snapshots(session, employees)
        return session, snapshots

    def test_single_query_for_all_employees(self) -> None:
        employees = [self._employee(1, "VEND-1"), self._employee(2, "VEND-2")]
        session, snapshots = self._run(employees, ventas=[])
        session.scalars.assert_called_once()
        self.assertEqual(set(snapshots), {1, 2})

    def test_sales_grouped_by_code_case_insensitive(self) -> None:
        employees = [self._employee(1, "VEND-1"), self._employee(2, "VEND-2")]
        venta = SimpleNamespace(
            seller_employee_code="vend-1",
            confirmada_at=datetime.now(timezone.utc),
            detalles=[SimpleNamespace(cantidad=3)],
            total="150.00",
        )
        _session, snapshots = self._run(employees, ventas=[venta])
        self.assertEqual(snapshots[1].today_tickets, 1)
        self.assertEqual(snapshots[1].today_pieces, 3)
        self.assertEqual(snapshots[2].today_tickets, 0)

    def test_empty_employee_list_skips_query(self) -> None:
        session = MagicMock()
        self.assertEqual(load_employee_activity_snapshots(session, []), {})
        session.scalars.assert_not_called()


class SettingsSearchDebounceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        from pos_uniformes.ui.main_window import MainWindow

        return MainWindow(user_id=1)

    def test_typing_starts_debounce_instead_of_refreshing(self) -> None:
        # Las conexiones se hacen al construir cada diálogo de Configuración.
        from pos_uniformes.ui.dialogs.settings_dialogs import (
            build_clients_settings_dialog,
            build_employees_settings_dialog,
            build_suppliers_settings_dialog,
        )

        window = self._window()
        for attr, builder, input_name, timer_name in [
            ("_refresh_settings_suppliers", build_suppliers_settings_dialog,
             "settings_suppliers_search_input", "settings_suppliers_debounce_timer"),
            ("_refresh_settings_clients", build_clients_settings_dialog,
             "settings_clients_search_input", "settings_clients_debounce_timer"),
            ("_refresh_settings_employees", build_employees_settings_dialog,
             "settings_employees_search_input", "settings_employees_debounce_timer"),
        ]:
            with self.subTest(attr=attr):
                refresh = MagicMock()
                setattr(window, attr, refresh)
                builder(window)
                refresh.reset_mock()  # el build puede refrescar una vez; eso es aparte
                getattr(window, input_name).setText("MARIA")
                refresh.assert_not_called()  # ninguna query por tecla
                timer = getattr(window, timer_name)
                self.assertTrue(timer.isActive())
                timer.stop()
                # Al vencer el debounce, refresca UNA vez y SIN argumentos
                # (antes el texto llegaba como `session` y tronaba).
                timer.timeout.emit()
                refresh.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
