from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDoubleSpinBox,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidgetItem,
)

from pos_uniformes.services.active_filter_service import ActiveFilterToken
from pos_uniformes.database.models import ModoOrigenVenta, RolUsuario, TipoMovimientoCaja
from pos_uniformes.ui.main_window import (
    CATALOG_PAGE_SIZE,
    INVENTORY_PAGE_SIZE,
    MainWindow,
    MultiSelectPickerButton,
    _TableSpinTabNavigator,
    _build_bulk_selection_label,
    _catalog_toggle_feedback_action,
)


class MainWindowSnapshotCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_catalog_snapshot_cache_reuses_rows_until_invalidated(self) -> None:
        window = MainWindow(user_id=1)
        sentinel_session = object()
        window._invalidate_listing_snapshot_caches()

        with patch(
            "pos_uniformes.ui.main_window.load_catalog_snapshot_rows",
            return_value=[{"variante_id": 1, "sku": "SKU-001"}],
        ) as loader:
            first_rows = window._load_catalog_snapshot_rows(sentinel_session)
            second_rows = window._load_catalog_snapshot_rows(sentinel_session)

            self.assertEqual(first_rows, second_rows)
            self.assertEqual(loader.call_count, 1)

            window._invalidate_listing_snapshot_caches(catalog=True, inventory=False)
            reloaded_rows = window._load_catalog_snapshot_rows(sentinel_session)

            self.assertEqual(reloaded_rows, first_rows)
            self.assertEqual(loader.call_count, 2)

    def test_catalog_toggle_feedback_action_uses_supported_result_keys(self) -> None:
        self.assertEqual(_catalog_toggle_feedback_action(True), "activate")
        self.assertEqual(_catalog_toggle_feedback_action(False), "deactivate")

    def test_inventory_snapshot_cache_reuses_rows_until_invalidated(self) -> None:
        window = MainWindow(user_id=1)
        sentinel_session = object()
        window._invalidate_listing_snapshot_caches()

        with patch(
            "pos_uniformes.ui.main_window.load_inventory_snapshot_rows",
            return_value=[{"variante_id": 2, "sku": "SKU-002"}],
        ) as loader:
            first_rows = window._load_inventory_snapshot_rows(sentinel_session)
            second_rows = window._load_inventory_snapshot_rows(sentinel_session)

            self.assertEqual(first_rows, second_rows)
            self.assertEqual(loader.call_count, 1)

            window._invalidate_listing_snapshot_caches(catalog=False, inventory=True)
            reloaded_rows = window._load_inventory_snapshot_rows(sentinel_session)

            self.assertEqual(reloaded_rows, first_rows)
            self.assertEqual(loader.call_count, 2)

    def test_multi_select_picker_button_opens_without_missing_group_attr(self) -> None:
        button = MultiSelectPickerButton(
            "Tallas: ninguna",
            title="Seleccionar tallas",
            helper_text="Selecciona varias tallas.",
        )
        button.set_items([("12", "12"), ("14", "14")])

        with patch("pos_uniformes.ui.main_window.QDialog.exec", return_value=0):
            button._open_picker()

        self.assertEqual(button.selected_labels(), [])

    def test_cash_session_label_hides_expected_amount_from_hero(self) -> None:
        window = MainWindow(user_id=1)
        active_session = SimpleNamespace(id=5, monto_apertura="1000.00")
        resumen = SimpleNamespace(esperado_en_caja="2450.00")

        with patch("pos_uniformes.ui.main_window.CajaService.obtener_sesion_activa", return_value=active_session), patch(
            "pos_uniformes.ui.main_window.CajaService.resumir_sesion",
            return_value=resumen,
        ), patch.object(window, "_is_stale_cash_session", return_value=True):
            window._refresh_cash_session(object())

        # Desde cc21062 el label es HTML con spans y, con corte pendiente,
        # tampoco muestra el reactivo de apertura.
        label_text = window.cash_session_label.text()
        self.assertIn("Rol ADMIN", label_text)
        self.assertIn("Corte pendiente", label_text)
        self.assertNotIn("Esperado", label_text)
        self.assertNotIn("2450", label_text)
        self.assertNotIn("1000.00", label_text)

    def test_cashier_role_sees_open_session_reactivo_in_hero(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.CAJERO
        active_session = SimpleNamespace(id=5, monto_apertura="1000.00")

        with patch("pos_uniformes.ui.main_window.CajaService.obtener_sesion_activa", return_value=active_session), patch.object(
            window, "_is_stale_cash_session", return_value=False
        ):
            window._refresh_cash_session(object())

        # Desde cc21062 el hero usa spans HTML y muestra "Reactivo $X" para
        # todos los roles con caja abierta (antes, 6dbabe1 lo ocultaba a
        # CAJERO). El monto esperado del corte sigue sin aparecer.
        label_text = window.cash_session_label.text()
        self.assertIn("Rol CAJERO", label_text)
        self.assertIn("Caja abierta", label_text)
        self.assertIn("Reactivo $1000.00", label_text)
        self.assertNotIn("Reactivo inicial", label_text)
        self.assertNotIn("Esperado", label_text)

    def test_cashier_role_hides_manual_discount_controls(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.CAJERO

        window._apply_role_navigation()
        window._refresh_permissions()

        self.assertTrue(window.sale_discount_field_label.isHidden())
        self.assertTrue(window.sale_discount_combo.isHidden())

    def test_logout_shows_window_before_ensuring_cash_session_for_new_user(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.ADMIN
        order: list[str] = []

        class FakeSignal:
            def __init__(self) -> None:
                self._callback = None

            def connect(self, callback) -> None:
                self._callback = callback

        class FakeLoginDialog:
            class DialogCode:
                Accepted = 1

            def __init__(self) -> None:
                self.authenticated = FakeSignal()

            def clear_loading_state(self) -> None:
                return None

            def accept(self) -> None:
                return None

            def hide(self) -> None:
                order.append("dialog-hide")

            def show(self) -> None:
                order.append("dialog-show")

            def exec(self) -> int:
                assert self.authenticated._callback is not None
                self.authenticated._callback(2)
                return self.DialogCode.Accepted

            def raise_(self) -> None:
                return None

            def activateWindow(self) -> None:
                return None

        # El diálogo de confirmación es un QDialog propio (no QMessageBox):
        # sin este mock, exec() modal cuelga la suite en offscreen.
        with patch.object(
            QDialog,
            "exec",
            return_value=int(QDialog.DialogCode.Accepted),
        ), patch.object(
            window,
            "_run_quick_backup_flow",
            return_value=True,
        ), patch("pos_uniformes.ui.main_window.LoginDialog", FakeLoginDialog), patch.object(
            window,
            "show",
            side_effect=lambda: order.append("show"),
        ), patch.object(window, "raise_", side_effect=lambda: order.append("raise")), patch.object(
            window,
            "activateWindow",
            side_effect=lambda: order.append("activate"),
        ), patch.object(
            window,
            "ensure_cash_session",
            side_effect=lambda: order.append("ensure") or False,
        ), patch.object(window, "refresh_all"), patch.object(window, "_set_sale_feedback"):
            window._handle_logout()

        self.assertIn("dialog-hide", order)
        self.assertIn("show", order)
        self.assertIn("ensure", order)
        self.assertLess(order.index("dialog-hide"), order.index("ensure"))
        self.assertLess(order.index("show"), order.index("ensure"))

    def test_logout_closes_and_resets_cached_dialogs(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.CAJERO
        dialog_attr_names = (
            "sales_dialog",
            "settings_users_dialog",
            "settings_suppliers_dialog",
            "settings_clients_dialog",
            "settings_employees_dialog",
            "settings_employee_day_sales_dialog",
            "settings_employee_sale_detail_dialog",
            "settings_backup_dialog",
            "settings_cash_history_dialog",
            "settings_business_dialog",
            "settings_marketing_dialog",
            "settings_whatsapp_dialog",
        )
        for attr_name in dialog_attr_names:
            setattr(window, attr_name, Mock())

        class FakeSignal:
            def __init__(self) -> None:
                self._callback = None

            def connect(self, callback) -> None:
                self._callback = callback

        class FakeLoginDialog:
            class DialogCode:
                Accepted = 1

            def __init__(self) -> None:
                self.authenticated = FakeSignal()

            def clear_loading_state(self) -> None:
                return None

            def accept(self) -> None:
                return None

            def hide(self) -> None:
                return None

            def show(self) -> None:
                return None

            def exec(self) -> int:
                assert self.authenticated._callback is not None
                self.authenticated._callback(2)
                return self.DialogCode.Accepted

            def raise_(self) -> None:
                return None

            def activateWindow(self) -> None:
                return None

        # Idem: el QDialog de confirmación real colgaría la suite en offscreen.
        with patch.object(
            QDialog,
            "exec",
            return_value=int(QDialog.DialogCode.Accepted),
        ), patch("pos_uniformes.ui.main_window.LoginDialog", FakeLoginDialog), patch.object(
            window,
            "ensure_cash_session",
            return_value=True,
        ), patch.object(window, "refresh_all"), patch.object(window, "_set_sale_feedback"), patch.object(
            window,
            "show",
        ), patch.object(window, "raise_"), patch.object(window, "activateWindow"):
            window._handle_logout()

        for attr_name in dialog_attr_names:
            self.assertIsNone(getattr(window, attr_name))

    def test_cashier_view_hides_sale_context_band(self) -> None:
        window = MainWindow(user_id=1)

        self.assertFalse(window.sale_context_label.isVisible())

    def test_cashier_view_places_manual_line_button_in_header(self) -> None:
        window = MainWindow(user_id=1)

        self.assertFalse(window.sale_add_button.isHidden())
        self.assertEqual(window.sale_add_button.text(), "Agregar sin codigo")

    def test_handle_add_sale_manual_line_appends_manual_cart_line(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.ADMIN
        window.active_cash_session_id = 10

        with patch.object(window, "_ensure_cash_session_current_day_for_operation", return_value=True), patch.object(
            window,
            "_prompt_sale_manual_line",
            return_value={"descripcion": "Venta manual", "precio_unitario": Decimal("75.00")},
        ), patch.object(window, "_refresh_sale_cart_table"), patch.object(window, "_set_sale_feedback"):
            window._handle_add_sale_manual_line()

        self.assertEqual(len(window.sale_cart), 1)
        self.assertEqual(window.sale_cart[0]["line_type"], "MANUAL")
        self.assertEqual(window.sale_cart[0]["producto_nombre"], "Venta manual")
        self.assertEqual(window.sale_cart[0]["precio_unitario"], Decimal("75.00"))

    def test_sale_origin_defaults_to_unassigned_after_reset(self) -> None:
        window = MainWindow(user_id=1)

        window._reset_sale_form()

        self.assertEqual(window.sale_credit_mode, ModoOrigenVenta.UNASSIGNED)
        self.assertEqual(window.sale_origin_value_label.text(), "Sin asignar")

    def test_sale_origin_direct_and_release_update_visible_label(self) -> None:
        window = MainWindow(user_id=1)

        window._handle_sale_origin_direct()
        self.assertEqual(window.sale_credit_mode, ModoOrigenVenta.OPERATOR_DIRECT)
        self.assertEqual(window.sale_origin_value_label.text(), "Directa")

        window._handle_sale_origin_release()
        self.assertEqual(window.sale_credit_mode, ModoOrigenVenta.UNASSIGNED)
        self.assertEqual(window.sale_origin_value_label.text(), "Sin asignar")

    def test_sale_origin_buttons_stay_available_without_open_cash_session(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.ADMIN
        window.active_cash_session_id = None
        window.cash_session_requires_cut = False

        window._refresh_permissions()

        self.assertTrue(window.sale_origin_direct_button.isEnabled())
        self.assertFalse(window.sale_origin_release_button.isEnabled())

    def test_sale_origin_identify_button_is_not_visible_in_cashier_ui(self) -> None:
        window = MainWindow(user_id=1)

        self.assertFalse(window.sale_origin_identify_button.isVisible())

    def test_sale_origin_identify_assigns_employee_from_emp_qr(self) -> None:
        window = MainWindow(user_id=1)
        fake_employee = SimpleNamespace(codigo="VEND-1", nombre_completo="Guadalupe Gomez Ruiz", activo=True)

        with patch("pos_uniformes.ui.main_window.get_session") as get_session_mock, patch(
            "pos_uniformes.ui.main_window.EmployeeIdentityService.resolve_employee_by_qr_code",
            return_value=fake_employee,
        ):
            session = Mock()
            context = Mock()
            context.__enter__ = Mock(return_value=session)
            context.__exit__ = Mock(return_value=False)
            get_session_mock.return_value = context

            window._handle_sale_origin_identify(scanned_code="EMP:VEND-1")

        self.assertEqual(window.sale_credit_mode, ModoOrigenVenta.EMPLOYEE)
        self.assertEqual(window.sale_seller_employee_code, "VEND-1")
        self.assertEqual(window.sale_origin_value_label.text(), "Guadalupe Ruiz")

    def test_sale_origin_identify_keeps_state_when_employee_qr_is_invalid(self) -> None:
        window = MainWindow(user_id=1)
        window._handle_sale_origin_direct()

        with patch("pos_uniformes.ui.main_window.get_session") as get_session_mock, patch(
            "pos_uniformes.ui.main_window.EmployeeIdentityService.resolve_employee_by_qr_code",
            return_value=None,
        ):
            session = Mock()
            context = Mock()
            context.__enter__ = Mock(return_value=session)
            context.__exit__ = Mock(return_value=False)
            get_session_mock.return_value = context

            window._handle_sale_origin_identify(scanned_code="EMP:VEND-404")

        self.assertEqual(window.sale_credit_mode, ModoOrigenVenta.OPERATOR_DIRECT)
        self.assertEqual(window.sale_origin_value_label.text(), "Directa")

    def test_handle_add_sale_item_routes_scanner_layout_variant_to_employee_origin(self) -> None:
        window = MainWindow(user_id=1)
        window.sale_sku_input.setText("EMPÑVEND´1")

        with patch.object(window, "_handle_sale_origin_identify") as identify_mock:
            window._handle_add_sale_item()

        identify_mock.assert_called_once_with(scanned_code="EMPÑVEND´1")
        self.assertEqual(window.sale_sku_input.text(), "")

    def test_settings_employee_detail_panel_formats_recent_activity(self) -> None:
        window = MainWindow(user_id=1)
        window.settings_employee_period_combo.addItems(["Hoy", "7 dias", "30 dias"])
        window.settings_employees_table.setColumnCount(1)
        window.settings_employees_table.setRowCount(1)
        item = QTableWidgetItem("VEND-1")
        item.setData(Qt.ItemDataRole.UserRole, 4)
        window.settings_employees_table.setItem(0, 0, item)
        window.settings_employees_table.setCurrentCell(0, 0)
        snapshot = SimpleNamespace(
            visible_name="Lupita Gomez",
            full_name="Guadalupe Gomez Ruiz",
            employee_code="VEND-1",
            active_label="ACTIVA",
            pin_label="Listo",
            qr_label="Listo",
            card_label="Lista",
            period_days=1,
            period_label="Hoy",
            period_pieces=8,
            period_tickets=3,
            period_amount=Decimal("1250.00"),
            today_pieces=8,
            today_tickets=3,
            today_amount=Decimal("1250.00"),
            last_sale_at=datetime(2026, 4, 9, 18, 45),
            day_rows=(
                SimpleNamespace(day=date(2026, 4, 9), day_label="09/04/2026", pieces=8, tickets=3, amount=Decimal("1250.00")),
            ),
        )

        with patch("pos_uniformes.ui.main_window.get_session") as get_session_mock, patch(
            "pos_uniformes.ui.main_window.load_employee_activity_snapshot",
            return_value=snapshot,
        ):
            session = Mock()
            context = Mock()
            context.__enter__ = Mock(return_value=session)
            context.__exit__ = Mock(return_value=False)
            get_session_mock.return_value = context

            window._refresh_settings_employee_detail()

        self.assertEqual(window.settings_employee_detail_name_label.text(), "Lupita Gomez")
        self.assertIn("Codigo: VEND-1", window.settings_employee_detail_meta_label.text())
        self.assertIn("PIN: Listo", window.settings_employee_detail_assets_label.text())
        self.assertIn("8 piezas", window.settings_employee_detail_today_label.text())
        self.assertNotIn("$1,250.00", window.settings_employee_detail_today_label.text())
        self.assertEqual(window.settings_employee_activity_table.rowCount(), 1)
        self.assertTrue(window.settings_employee_activity_table.isColumnHidden(3))
        self.assertEqual(window.settings_employee_toggle_amounts_button.text(), "Mostrar monto")

    def test_settings_employee_detail_can_show_amounts_after_password(self) -> None:
        window = MainWindow(user_id=1)
        window.settings_employee_period_combo.addItems(["Hoy", "7 dias", "30 dias"])
        window.settings_employees_table.setColumnCount(1)
        window.settings_employees_table.setRowCount(1)
        item = QTableWidgetItem("VEND-1")
        item.setData(Qt.ItemDataRole.UserRole, 4)
        window.settings_employees_table.setItem(0, 0, item)
        window.settings_employees_table.setCurrentCell(0, 0)
        snapshot = SimpleNamespace(
            visible_name="Lupita Gomez",
            full_name="Guadalupe Gomez Ruiz",
            employee_code="VEND-1",
            active_label="ACTIVA",
            pin_label="Listo",
            qr_label="Listo",
            card_label="Lista",
            period_days=1,
            period_label="Hoy",
            period_pieces=8,
            period_tickets=3,
            period_amount=Decimal("1250.00"),
            today_pieces=8,
            today_tickets=3,
            today_amount=Decimal("1250.00"),
            last_sale_at=datetime(2026, 4, 9, 18, 45),
            day_rows=(
                SimpleNamespace(day=date(2026, 4, 9), day_label="09/04/2026", pieces=8, tickets=3, amount=Decimal("1250.00")),
            ),
        )

        with patch("pos_uniformes.ui.main_window.get_session") as get_session_mock, patch(
            "pos_uniformes.ui.main_window.load_employee_activity_snapshot",
            return_value=snapshot,
        ):
            session = Mock()
            context = Mock()
            context.__enter__ = Mock(return_value=session)
            context.__exit__ = Mock(return_value=False)
            get_session_mock.return_value = context

            window._refresh_settings_employee_detail()
            self.assertTrue(window.settings_employee_activity_table.isColumnHidden(3))
            self.assertNotIn("$1,250.00", window.settings_employee_detail_today_label.text())

            with patch.object(window, "_prompt_settings_employee_amount_access", return_value=True):
                window._handle_toggle_settings_employee_amounts()

        self.assertFalse(window.settings_employee_activity_table.isColumnHidden(3))
        self.assertIn("$1,250.00", window.settings_employee_detail_today_label.text())
        self.assertEqual(window.settings_employee_toggle_amounts_button.text(), "Ocultar monto")

    def test_settings_employee_detail_keeps_amounts_hidden_when_password_fails(self) -> None:
        window = MainWindow(user_id=1)
        window.settings_employee_period_combo.addItems(["Hoy", "7 dias", "30 dias"])
        window.settings_employees_table.setColumnCount(1)
        window.settings_employees_table.setRowCount(1)
        item = QTableWidgetItem("VEND-1")
        item.setData(Qt.ItemDataRole.UserRole, 4)
        window.settings_employees_table.setItem(0, 0, item)
        window.settings_employees_table.setCurrentCell(0, 0)
        snapshot = SimpleNamespace(
            visible_name="Lupita Gomez",
            full_name="Guadalupe Gomez Ruiz",
            employee_code="VEND-1",
            active_label="ACTIVA",
            pin_label="Listo",
            qr_label="Listo",
            card_label="Lista",
            period_days=1,
            period_label="Hoy",
            period_pieces=8,
            period_tickets=3,
            period_amount=Decimal("1250.00"),
            today_pieces=8,
            today_tickets=3,
            today_amount=Decimal("1250.00"),
            last_sale_at=datetime(2026, 4, 9, 18, 45),
            day_rows=(
                SimpleNamespace(day=date(2026, 4, 9), day_label="09/04/2026", pieces=8, tickets=3, amount=Decimal("1250.00")),
            ),
        )

        with patch("pos_uniformes.ui.main_window.get_session") as get_session_mock, patch(
            "pos_uniformes.ui.main_window.load_employee_activity_snapshot",
            return_value=snapshot,
        ):
            session = Mock()
            context = Mock()
            context.__enter__ = Mock(return_value=session)
            context.__exit__ = Mock(return_value=False)
            get_session_mock.return_value = context
            window._refresh_settings_employee_detail()

            with patch.object(window, "_prompt_settings_employee_amount_access", return_value=False):
                window._handle_toggle_settings_employee_amounts()

    def test_settings_employee_detail_updates_summary_when_period_changes(self) -> None:
        window = MainWindow(user_id=1)
        window.settings_employee_period_combo.addItems(["Hoy", "7 dias", "30 dias"])
        window.settings_employee_period_combo.setCurrentText("7 dias")
        window.settings_employees_table.setColumnCount(1)
        window.settings_employees_table.setRowCount(1)
        item = QTableWidgetItem("VEND-1")
        item.setData(Qt.ItemDataRole.UserRole, 4)
        window.settings_employees_table.setItem(0, 0, item)
        window.settings_employees_table.setCurrentCell(0, 0)
        snapshot = SimpleNamespace(
            visible_name="Lupita Gomez",
            full_name="Guadalupe Gomez Ruiz",
            employee_code="VEND-1",
            active_label="ACTIVA",
            pin_label="Listo",
            qr_label="Listo",
            card_label="Lista",
            period_days=7,
            period_label="7 dias",
            period_pieces=12,
            period_tickets=4,
            period_amount=Decimal("1800.00"),
            today_pieces=8,
            today_tickets=3,
            today_amount=Decimal("1250.00"),
            last_sale_at=datetime(2026, 4, 9, 18, 45),
            day_rows=(
                SimpleNamespace(day=date(2026, 4, 9), day_label="09/04/2026", pieces=8, tickets=3, amount=Decimal("1250.00")),
            ),
        )

        with patch("pos_uniformes.ui.main_window.get_session") as get_session_mock, patch(
            "pos_uniformes.ui.main_window.load_employee_activity_snapshot",
            return_value=snapshot,
        ):
            session = Mock()
            context = Mock()
            context.__enter__ = Mock(return_value=session)
            context.__exit__ = Mock(return_value=False)
            get_session_mock.return_value = context

            window._refresh_settings_employee_detail()

        self.assertIn("7 dias: 12 piezas | 4 tickets", window.settings_employee_detail_today_label.text())

    def test_refresh_settings_employees_shows_recent_activity_badge(self) -> None:
        window = MainWindow(user_id=1)
        window.settings_employees_table.setColumnCount(9)
        window.settings_employees_activity_filter_combo.addItems(["Todas", "Activa hoy", "Activa 7d", "Sin actividad"])
        employee_today = SimpleNamespace(
            id=4,
            codigo="VEND-1",
            nombre_completo="Guadalupe Gomez Ruiz",
            activo=True,
            updated_at=datetime(2026, 4, 9, 9, 0),
        )
        employee_recent = SimpleNamespace(
            id=5,
            codigo="VEND-2",
            nombre_completo="Andrea Lopez",
            activo=True,
            updated_at=datetime(2026, 4, 8, 17, 30),
        )
        today_snapshot = SimpleNamespace(
            today_pieces=3,
            today_tickets=1,
            day_rows=(
                SimpleNamespace(pieces=3, tickets=1),
                SimpleNamespace(pieces=0, tickets=0),
            ),
        )
        recent_snapshot = SimpleNamespace(
            today_pieces=0,
            today_tickets=0,
            day_rows=(
                SimpleNamespace(pieces=0, tickets=0),
                SimpleNamespace(pieces=2, tickets=1),
            ),
        )

        with patch("pos_uniformes.ui.main_window.get_session") as get_session_mock, patch(
            "pos_uniformes.ui.main_window.EmployeeIdentityService.list_employees",
            return_value=[employee_today, employee_recent],
        ), patch(
            "pos_uniformes.ui.main_window.load_employee_activity_snapshot",
            side_effect=[today_snapshot, recent_snapshot],
        ), patch(
            "pos_uniformes.ui.main_window.EmployeeIdentityService.has_pin",
            side_effect=[True, False],
        ), patch(
            "pos_uniformes.ui.main_window.QrGenerator.exists_for_employee",
            return_value=False,
        ), patch(
            "pos_uniformes.ui.main_window.EmployeeCardService.exists_for_employee",
            return_value=False,
        ):
            session = Mock()
            context = Mock()
            context.__enter__ = Mock(return_value=session)
            context.__exit__ = Mock(return_value=False)
            get_session_mock.return_value = context

            window._refresh_settings_employees()

        self.assertEqual(window.settings_employees_table.item(0, 3).text(), "Activa hoy")
        self.assertEqual(window.settings_employees_table.item(1, 3).text(), "Activa 7d")

    def test_refresh_settings_employees_filters_by_activity_label(self) -> None:
        window = MainWindow(user_id=1)
        window.settings_employees_table.setColumnCount(9)
        window.settings_employees_activity_filter_combo.addItems(["Todas", "Activa hoy", "Activa 7d", "Sin actividad"])
        window.settings_employees_activity_filter_combo.setCurrentText("Sin actividad")
        employee_today = SimpleNamespace(
            id=4,
            codigo="VEND-1",
            nombre_completo="Guadalupe Gomez Ruiz",
            activo=True,
            updated_at=datetime(2026, 4, 9, 9, 0),
        )
        employee_inactive = SimpleNamespace(
            id=5,
            codigo="VEND-2",
            nombre_completo="Andrea Lopez",
            activo=True,
            updated_at=datetime(2026, 4, 8, 17, 30),
        )
        today_snapshot = SimpleNamespace(
            today_pieces=3,
            today_tickets=1,
            day_rows=(
                SimpleNamespace(pieces=3, tickets=1),
                SimpleNamespace(pieces=0, tickets=0),
            ),
        )
        inactive_snapshot = SimpleNamespace(
            today_pieces=0,
            today_tickets=0,
            day_rows=(
                SimpleNamespace(pieces=0, tickets=0),
                SimpleNamespace(pieces=0, tickets=0),
            ),
        )

        with patch("pos_uniformes.ui.main_window.get_session") as get_session_mock, patch(
            "pos_uniformes.ui.main_window.EmployeeIdentityService.list_employees",
            return_value=[employee_today, employee_inactive],
        ), patch(
            "pos_uniformes.ui.main_window.load_employee_activity_snapshot",
            side_effect=[today_snapshot, inactive_snapshot],
        ), patch(
            "pos_uniformes.ui.main_window.EmployeeIdentityService.has_pin",
            side_effect=[True, False],
        ), patch(
            "pos_uniformes.ui.main_window.QrGenerator.exists_for_employee",
            return_value=False,
        ), patch(
            "pos_uniformes.ui.main_window.EmployeeCardService.exists_for_employee",
            return_value=False,
        ):
            session = Mock()
            context = Mock()
            context.__enter__ = Mock(return_value=session)
            context.__exit__ = Mock(return_value=False)
            get_session_mock.return_value = context

            window._refresh_settings_employees()

        self.assertEqual(window.settings_employees_table.rowCount(), 1)
        self.assertEqual(window.settings_employees_table.item(0, 0).text(), "VEND-2")
        self.assertIn("filtro: Sin actividad", window.settings_employees_status_label.text())

    def test_refresh_settings_employees_orders_by_activity_priority_and_today_pieces(self) -> None:
        window = MainWindow(user_id=1)
        window.settings_employees_table.setColumnCount(9)
        window.settings_employees_activity_filter_combo.addItems(["Todas", "Activa hoy", "Activa 7d", "Sin actividad"])
        employee_inactive = SimpleNamespace(
            id=6,
            codigo="VEND-3",
            nombre_completo="Berenice Cruz",
            activo=True,
            updated_at=datetime(2026, 4, 7, 17, 30),
        )
        employee_recent = SimpleNamespace(
            id=5,
            codigo="VEND-2",
            nombre_completo="Andrea Lopez",
            activo=True,
            updated_at=datetime(2026, 4, 8, 17, 30),
        )
        employee_today = SimpleNamespace(
            id=4,
            codigo="VEND-1",
            nombre_completo="Guadalupe Gomez Ruiz",
            activo=True,
            updated_at=datetime(2026, 4, 9, 9, 0),
        )
        inactive_snapshot = SimpleNamespace(
            visible_name="Berenice Cruz",
            full_name="Berenice Cruz",
            today_pieces=0,
            today_tickets=0,
            last_sale_at=None,
            day_rows=(
                SimpleNamespace(pieces=0, tickets=0),
                SimpleNamespace(pieces=0, tickets=0),
            ),
        )
        recent_snapshot = SimpleNamespace(
            visible_name="Andrea Lopez",
            full_name="Andrea Lopez",
            today_pieces=0,
            today_tickets=0,
            last_sale_at=datetime(2026, 4, 8, 10, 0),
            day_rows=(
                SimpleNamespace(pieces=0, tickets=0),
                SimpleNamespace(pieces=2, tickets=1),
            ),
        )
        today_snapshot = SimpleNamespace(
            visible_name="Guadalupe Ruiz",
            full_name="Guadalupe Gomez Ruiz",
            today_pieces=3,
            today_tickets=1,
            last_sale_at=datetime(2026, 4, 9, 11, 0),
            day_rows=(
                SimpleNamespace(pieces=3, tickets=1),
                SimpleNamespace(pieces=0, tickets=0),
            ),
        )

        with patch("pos_uniformes.ui.main_window.get_session") as get_session_mock, patch(
            "pos_uniformes.ui.main_window.EmployeeIdentityService.list_employees",
            return_value=[employee_inactive, employee_recent, employee_today],
        ), patch(
            "pos_uniformes.ui.main_window.load_employee_activity_snapshot",
            side_effect=[inactive_snapshot, recent_snapshot, today_snapshot],
        ), patch(
            "pos_uniformes.ui.main_window.EmployeeIdentityService.has_pin",
            return_value=False,
        ), patch(
            "pos_uniformes.ui.main_window.QrGenerator.exists_for_employee",
            return_value=False,
        ), patch(
            "pos_uniformes.ui.main_window.EmployeeCardService.exists_for_employee",
            return_value=False,
        ):
            session = Mock()
            context = Mock()
            context.__enter__ = Mock(return_value=session)
            context.__exit__ = Mock(return_value=False)
            get_session_mock.return_value = context

            window._refresh_settings_employees()

        self.assertEqual(window.settings_employees_table.item(0, 0).text(), "VEND-1")
        self.assertEqual(window.settings_employees_table.item(1, 0).text(), "VEND-2")
        self.assertEqual(window.settings_employees_table.item(2, 0).text(), "VEND-3")

        self.assertTrue(window.settings_employee_activity_table.isColumnHidden(3))
        self.assertNotIn("$1,250.00", window.settings_employee_detail_today_label.text())
        self.assertEqual(window.settings_employee_toggle_amounts_button.text(), "Mostrar monto")

    def test_open_settings_employee_day_sales_dialog_loads_rows_for_selected_day(self) -> None:
        window = MainWindow(user_id=1)
        window.settings_employees_table.setColumnCount(1)
        window.settings_employees_table.setRowCount(1)
        employee_item = QTableWidgetItem("VEND-1")
        employee_item.setData(Qt.ItemDataRole.UserRole, 4)
        window.settings_employees_table.setItem(0, 0, employee_item)
        window.settings_employees_table.setCurrentCell(0, 0)
        window.settings_employee_activity_table.setColumnCount(4)
        window.settings_employee_activity_table.setRowCount(1)
        day_item = QTableWidgetItem("09/04/2026")
        day_item.setData(Qt.ItemDataRole.UserRole, date(2026, 4, 9))
        window.settings_employee_activity_table.setItem(0, 0, day_item)
        window.settings_employee_activity_table.setCurrentCell(0, 0)

        employee = SimpleNamespace(codigo="VEND-1", nombre_completo="Guadalupe Gomez Ruiz")
        rows = (
            SimpleNamespace(sale_id=10, values=("10:30", "VTA-010", "Maria", 2, Decimal("199.00"))),
        )

        with patch("pos_uniformes.ui.main_window.get_session") as get_session_mock, patch(
            "pos_uniformes.ui.main_window.list_employee_day_sale_rows",
            return_value=rows,
        ):
            session = Mock()
            session.get.return_value = employee
            context = Mock()
            context.__enter__ = Mock(return_value=session)
            context.__exit__ = Mock(return_value=False)
            get_session_mock.return_value = context

            window._open_settings_employee_day_sales_dialog()

        self.assertIsNotNone(window.settings_employee_day_sales_dialog)
        self.assertEqual(window.settings_employee_day_sales_table.rowCount(), 1)
        self.assertEqual(window.settings_employee_day_sales_status_label.text(), "Tickets confirmados del dia: 1")
        self.assertEqual(window.settings_employee_day_sales_table.item(0, 1).text(), "VTA-010")
        self.assertTrue(window.settings_employee_view_ticket_button.isEnabled())

    def test_view_settings_employee_day_sale_ticket_opens_detail_with_products(self) -> None:
        window = MainWindow(user_id=1)
        window.settings_employee_day_sales_table.setColumnCount(5)
        window.settings_employee_day_sales_table.setRowCount(1)
        item = QTableWidgetItem("10:30")
        item.setData(Qt.ItemDataRole.UserRole, 10)
        window.settings_employee_day_sales_table.setItem(0, 0, item)
        window.settings_employee_day_sales_table.setCurrentCell(0, 0)
        snapshot = SimpleNamespace(
            folio="VTA-010",
            time_label="10:30",
            client_name="Maria",
            pieces=2,
            total=Decimal("199.00"),
            rows=(
                SimpleNamespace(values=("SKU-001", "Playera Polo", 2, Decimal("99.50"), Decimal("199.00"))),
            ),
        )

        with patch("pos_uniformes.ui.main_window.get_session") as get_session_mock, patch(
            "pos_uniformes.ui.main_window.load_employee_sale_detail_snapshot",
            return_value=snapshot,
        ):
            session = Mock()
            context = Mock()
            context.__enter__ = Mock(return_value=session)
            context.__exit__ = Mock(return_value=False)
            get_session_mock.return_value = context

            window._handle_view_settings_employee_day_sale_ticket()

        self.assertIsNotNone(window.settings_employee_sale_detail_dialog)
        self.assertEqual(
            window.settings_employee_sale_detail_status_label.text(),
            "Cliente: Maria | Piezas: 2 | Total: $199.00",
        )
        self.assertEqual(window.settings_employee_sale_detail_table.rowCount(), 1)
        self.assertEqual(window.settings_employee_sale_detail_table.item(0, 0).text(), "SKU-001")
        self.assertEqual(window.settings_employee_sale_detail_table.item(0, 1).text(), "Playera Polo")

    def test_admin_role_keeps_manual_discount_controls_visible(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.ADMIN

        window._apply_role_navigation()
        window._refresh_permissions()

        self.assertFalse(window.sale_discount_field_label.isHidden())
        self.assertFalse(window.sale_discount_combo.isHidden())

    def test_cashier_role_hides_admin_cash_cut_action(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.CAJERO
        window.active_cash_session_id = 10

        window._refresh_permissions()

        self.assertFalse(window.cash_admin_cut_action.isVisible())
        self.assertFalse(window.cash_admin_cut_action.isEnabled())

    def test_admin_role_shows_admin_cash_cut_action(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.ADMIN
        window.active_cash_session_id = 10

        window._refresh_permissions()

        self.assertTrue(window.cash_admin_cut_action.isVisible())
        self.assertTrue(window.cash_admin_cut_action.isEnabled())

    def test_handle_admin_cash_cut_registers_retiro_with_fixed_concept(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.ADMIN
        window.active_cash_session_id = 9
        window.refresh_all = Mock()
        window._prompt_admin_cash_authorization = Mock(return_value=True)
        window._prompt_admin_cash_cut_data = Mock(
            return_value={
                "monto": Decimal("150.00"),
                "concepto": "Corte administrativo | mantenimiento",
                "nota": "mantenimiento",
            }
        )

        with patch("pos_uniformes.ui.main_window.get_session") as get_session_mock, patch(
            "pos_uniformes.ui.main_window.register_cash_movement_action"
        ) as register_movement, patch("pos_uniformes.ui.main_window.QMessageBox.information"):
            session = Mock()
            context = Mock()
            context.__enter__ = Mock(return_value=session)
            context.__exit__ = Mock(return_value=False)
            get_session_mock.return_value = context

            window._handle_admin_cash_cut()

        register_movement.assert_called_once()
        self.assertEqual(register_movement.call_args.kwargs["movement_type"], TipoMovimientoCaja.RETIRO)
        self.assertEqual(register_movement.call_args.kwargs["amount"], Decimal("150.00"))
        self.assertEqual(register_movement.call_args.kwargs["concept"], "Corte administrativo | mantenimiento")

    def test_quote_cart_table_keeps_cashier_breathing_in_main_window(self) -> None:
        window = MainWindow(user_id=1)

        self.assertEqual(window.quote_cart_table.columnCount(), 7)
        self.assertEqual(window.quote_cart_table.horizontalHeaderItem(2).text(), "Talla")
        self.assertEqual(window.quote_cart_table.objectName(), "cashierCartTable")
        self.assertEqual(window.quote_cart_table.verticalHeader().defaultSectionSize(), 48)
        self.assertEqual(window.quote_cart_table.minimumHeight(), 260)

    def test_create_quote_client_avoids_generating_assets_and_shows_promotion(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.ADMIN
        window._prompt_quick_quote_client_data = Mock(return_value={"nombre": "Ana", "telefono": "5551234567"})
        window._render_client_card_safe = Mock(side_effect=AssertionError("No debe generar credencial aqui"))
        window._prepare_client_qr_delivery = Mock(side_effect=AssertionError("No debe generar QR aqui"))
        window._prepare_client_card_delivery = Mock(side_effect=AssertionError("No debe preparar envio aqui"))

        fake_user = SimpleNamespace(id=1)
        fake_client = SimpleNamespace(id=12, nombre="Ana", codigo_cliente="CLI-012", telefono="5551234567")
        fake_session = Mock()
        fake_session.get.return_value = fake_user

        def _fake_refresh() -> None:
            window.quote_client_combo.clear()
            window.quote_client_combo.addItem("Sin cliente asignado", None)
            window.quote_client_combo.addItem(
                "CLI-012 · Ana",
                {"id": 12, "nombre": "Ana", "telefono": "5551234567"},
            )

        window.refresh_all = Mock(side_effect=_fake_refresh)

        with patch("pos_uniformes.ui.main_window.get_session") as get_session, patch(
            "pos_uniformes.ui.main_window.ClientService.create_client_quick",
            return_value=fake_client,
        ), patch(
            "pos_uniformes.ui.main_window.build_quote_client_created_feedback",
            return_value="Promo lista",
        ), patch(
            "pos_uniformes.ui.main_window.QMessageBox.information",
        ) as info:
            get_session.return_value.__enter__.return_value = fake_session

            window._handle_create_quote_client()

        self.assertEqual(window.quote_client_combo.currentText(), "CLI-012 · Ana")
        self.assertEqual(info.call_args.args[2], "Promo lista")

    def test_cashier_role_hides_dashboard_tab(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.CAJERO

        window._apply_role_navigation()

        self.assertFalse(window.tabs.isTabVisible(0))
        self.assertTrue(window.tabs.isTabVisible(1))

    def test_cashier_role_redirects_from_hidden_dashboard_to_cashier(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.CAJERO
        window.tabs.setCurrentIndex(0)

        window._apply_role_navigation()

        self.assertEqual(window.tabs.currentIndex(), 1)

    def test_restore_catalog_selection_after_mutation_clears_stale_selection_when_row_disappears(self) -> None:
        window = MainWindow(user_id=1)
        window.catalog_table.setRowCount(1)
        window.catalog_table.setColumnCount(1)
        window.catalog_table.setCurrentCell(0, 0)
        window.catalog_table.selectRow(0)
        window.inventory_table.setRowCount(1)
        window.inventory_table.setColumnCount(1)
        first_item = QTableWidgetItem("SKU-001")
        first_item.setData(0x0100, 101)
        window.inventory_table.setItem(0, 0, first_item)
        window.inventory_table.setCurrentCell(0, 0)
        window.inventory_table.selectRow(0)

        with patch.object(window, "_select_catalog_variant", return_value=False):
            window._restore_catalog_selection_after_mutation(101)

        self.assertEqual(window.catalog_table.currentRow(), -1)
        self.assertEqual(window.inventory_table.currentRow(), -1)
        self.assertIn("Selecciona una presentacion", window.catalog_selection_label.text())

    def test_selected_catalog_row_falls_back_to_snapshot_when_variant_is_hidden_in_catalog(self) -> None:
        window = MainWindow(user_id=1)
        hidden_row = {
            "variante_id": 101,
            "producto_id": 15,
            "producto_nombre": "Pants Deportivo",
            "producto_activo": False,
            "variante_activo": False,
            "sku": "SKU-101",
        }
        window.catalog_filtered_rows = []
        window.catalog_rows = []
        window.inventory_table.setRowCount(1)
        window.inventory_table.setColumnCount(1)
        first_item = QTableWidgetItem("SKU-101")
        first_item.setData(0x0100, 101)
        window.inventory_table.setItem(0, 0, first_item)
        window.inventory_table.setCurrentCell(0, 0)

        with patch.object(window, "_load_catalog_snapshot_rows", return_value=[hidden_row]):
            selected = window._selected_catalog_row()

        self.assertEqual(selected, hidden_row)

    def test_clear_inventory_table_selection_resets_panel_state(self) -> None:
        window = MainWindow(user_id=1)
        window.inventory_table.setRowCount(1)
        window.inventory_table.setColumnCount(1)
        first_item = QTableWidgetItem("SKU-101")
        first_item.setData(0x0100, 101)
        window.inventory_table.setItem(0, 0, first_item)
        window.inventory_table.setCurrentCell(0, 0)
        window.inventory_table.selectRow(0)
        window.inventory_overview_label.setText("SKU-101")
        window.inventory_product_label.setText("Pants Deportivo")
        window.catalog_selection_label.setText("SKU-101 | contexto")
        window.qr_preview_label.setText("SKU-101")
        window.qr_preview_info_label.setText("SKU-101 | Pants Deportivo")
        window.qr_status_label.setText("QR disponible: SKU-101.png")

        window._clear_inventory_table_selection()

        self.assertEqual(window.inventory_table.currentRow(), -1)
        self.assertEqual(window.inventory_variant_combo.currentIndex(), -1)
        self.assertEqual(window.inventory_overview_label.text(), "Selecciona una presentacion")
        self.assertEqual(window.catalog_selection_label.text(), "Selecciona una presentacion en inventario para gestionar cambios.")
        self.assertEqual(window.qr_preview_label.text(), "QR pendiente")
        self.assertEqual(window.qr_preview_info_label.text(), "")
        self.assertEqual(window.qr_status_label.text(), "Sin seleccion")

    def test_clear_inventory_filters_also_clears_table_selection(self) -> None:
        window = MainWindow(user_id=1)
        window.inventory_table.setRowCount(1)
        window.inventory_table.setColumnCount(1)
        first_item = QTableWidgetItem("SKU-101")
        first_item.setData(0x0100, 101)
        window.inventory_table.setItem(0, 0, first_item)
        window.inventory_table.setCurrentCell(0, 0)
        window.inventory_table.selectRow(0)
        window.inventory_search_input.setText("pants")
        window.inventory_overview_label.setText("SKU-101")
        window.catalog_selection_label.setText("SKU-101 | contexto")
        window.qr_preview_label.setText("SKU-101")
        window.qr_preview_info_label.setText("SKU-101 | Pants Deportivo")
        window.qr_status_label.setText("QR disponible: SKU-101.png")

        with patch.object(window, "_handle_inventory_filters_changed") as refresh_filters:
            window._handle_clear_inventory_filters()

        self.assertEqual(window.inventory_table.currentRow(), -1)
        self.assertEqual(window.inventory_variant_combo.currentIndex(), -1)
        self.assertEqual(window.inventory_overview_label.text(), "Selecciona una presentacion")
        self.assertEqual(window.catalog_selection_label.text(), "Selecciona una presentacion en inventario para gestionar cambios.")
        self.assertEqual(window.qr_preview_label.text(), "QR pendiente")
        self.assertEqual(window.qr_preview_info_label.text(), "")
        self.assertEqual(window.qr_status_label.text(), "Sin seleccion")
        self.assertEqual(window.inventory_search_input.text(), "")
        refresh_filters.assert_called_once_with()

    def test_inventory_hides_catalog_selection_summary_line(self) -> None:
        window = MainWindow(user_id=1)

        self.assertFalse(window.catalog_selection_label.isVisible())

    def test_inventory_starts_without_selected_variant(self) -> None:
        window = MainWindow(user_id=1)

        self.assertEqual(window.inventory_variant_combo.currentIndex(), -1)
        self.assertEqual(window.inventory_table.currentRow(), -1)
        self.assertEqual(window.inventory_overview_label.text(), "Selecciona una presentacion")
        self.assertEqual(window.qr_preview_label.text(), "QR pendiente")

    def test_inventory_print_label_uses_batch_dialog_for_multiple_selected_rows(self) -> None:
        window = MainWindow(user_id=1)
        window._selected_inventory_variant_ids = Mock(return_value=[7, 8])
        window._handle_inventory_print_label_batch = Mock()

        window._handle_inventory_print_label()

        window._handle_inventory_print_label_batch.assert_called_once_with([7, 8])

    def test_inventory_count_prefills_selected_rows_from_inventory(self) -> None:
        window = MainWindow(user_id=1)
        window.inventory_filtered_rows = [
            {
                "variante_id": 11,
                "sku": "SKU000011",
                "producto_nombre_base": "Bata",
                "talla": "12",
                "color": "Blanca",
                "escuela_nombre": "General",
                "stock_actual": 9,
            },
            {
                "variante_id": 12,
                "sku": "SKU000012",
                "producto_nombre_base": "Playera",
                "talla": "14",
                "color": "Azul",
                "escuela_nombre": "General",
                "stock_actual": 4,
            },
        ]
        window._selected_inventory_variant_ids = Mock(return_value=[12])

        with patch("pos_uniformes.ui.main_window.prompt_inventory_count_data", return_value=None) as prompt_mock:
            result = window._prompt_inventory_count_data()

        self.assertIsNone(result)
        prompt_mock.assert_called_once()
        self.assertIn("print_labels_callback", prompt_mock.call_args.kwargs)
        self.assertTrue(callable(prompt_mock.call_args.kwargs["print_labels_callback"]))

    def test_table_spin_tab_navigator_moves_between_bulk_adjust_inputs(self) -> None:
        host = MainWindow(user_id=1)
        anchor_before = QPushButton("Restablecer", host)
        first_spin = QSpinBox(host)
        second_spin = QSpinBox(host)
        anchor_after = QPushButton("Cancelar", host)
        navigator = _TableSpinTabNavigator(anchor_before=anchor_before, anchor_after=anchor_after)
        navigator.set_inputs([first_spin, second_spin])

        forward_calls: list[tuple[str, Qt.FocusReason]] = []
        original_second_focus = second_spin.setFocus
        second_spin.setFocus = lambda reason=Qt.FocusReason.OtherFocusReason: forward_calls.append(("second", reason))
        original_second_select_all = second_spin.lineEdit().selectAll if second_spin.lineEdit() is not None else None
        if second_spin.lineEdit() is not None:
            second_spin.lineEdit().selectAll = lambda: forward_calls.append(("second_select_all", Qt.FocusReason.OtherFocusReason))
        handled_forward = navigator.eventFilter(
            first_spin.lineEdit(),
            QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Tab), Qt.KeyboardModifier.NoModifier),
        )
        second_spin.setFocus = original_second_focus
        if second_spin.lineEdit() is not None and original_second_select_all is not None:
            second_spin.lineEdit().selectAll = original_second_select_all

        self.assertTrue(handled_forward)
        self.assertIn(("second", Qt.FocusReason.TabFocusReason), forward_calls)
        self.assertIn(("second_select_all", Qt.FocusReason.OtherFocusReason), forward_calls)

        backward_calls: list[tuple[str, Qt.FocusReason]] = []
        original_anchor_focus = anchor_before.setFocus
        anchor_before.setFocus = lambda reason=Qt.FocusReason.OtherFocusReason: backward_calls.append(("anchor_before", reason))
        handled_backward = navigator.eventFilter(
            first_spin.lineEdit(),
            QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Backtab), Qt.KeyboardModifier.ShiftModifier),
        )
        anchor_before.setFocus = original_anchor_focus

        self.assertTrue(handled_backward)
        self.assertIn(("anchor_before", Qt.FocusReason.TabFocusReason), backward_calls)

    def test_table_spin_tab_navigator_supports_double_spin_boxes(self) -> None:
        host = MainWindow(user_id=1)
        first_spin = QDoubleSpinBox(host)
        second_spin = QDoubleSpinBox(host)
        anchor_after = QPushButton("Cancelar", host)
        navigator = _TableSpinTabNavigator(anchor_after=anchor_after)
        navigator.set_inputs([first_spin, second_spin])

        forward_calls: list[tuple[str, Qt.FocusReason]] = []
        original_second_focus = second_spin.setFocus
        second_spin.setFocus = lambda reason=Qt.FocusReason.OtherFocusReason: forward_calls.append(("second", reason))
        original_second_select_all = second_spin.lineEdit().selectAll if second_spin.lineEdit() is not None else None
        if second_spin.lineEdit() is not None:
            second_spin.lineEdit().selectAll = lambda: forward_calls.append(("second_select_all", Qt.FocusReason.OtherFocusReason))
        handled_forward = navigator.eventFilter(
            first_spin.lineEdit(),
            QKeyEvent(QEvent.Type.KeyPress, int(Qt.Key.Key_Tab), Qt.KeyboardModifier.NoModifier),
        )
        second_spin.setFocus = original_second_focus
        if second_spin.lineEdit() is not None and original_second_select_all is not None:
            second_spin.lineEdit().selectAll = original_second_select_all

        self.assertTrue(handled_forward)
        self.assertIn(("second", Qt.FocusReason.TabFocusReason), forward_calls)
        self.assertIn(("second_select_all", Qt.FocusReason.OtherFocusReason), forward_calls)

    def test_catalog_search_refresh_uses_single_debounce_timer(self) -> None:
        window = MainWindow(user_id=1)
        callback = Mock()
        window._run_catalog_filter_refresh = callback

        window._schedule_catalog_filter_refresh()
        window._schedule_catalog_filter_refresh()
        QTest.qWait(window.catalog_filter_debounce_timer.interval() + 80)

        self.assertEqual(callback.call_count, 1)

    def test_inventory_search_refresh_uses_single_debounce_timer(self) -> None:
        window = MainWindow(user_id=1)
        callback = Mock()
        window._run_inventory_filter_refresh = callback

        window._schedule_inventory_filter_refresh()
        window._schedule_inventory_filter_refresh()
        QTest.qWait(window.inventory_filter_debounce_timer.interval() + 80)

        self.assertEqual(callback.call_count, 1)

    def test_catalog_immediate_refresh_cancels_pending_debounce(self) -> None:
        window = MainWindow(user_id=1)
        callback = Mock()
        window._run_catalog_filter_refresh = callback

        window._schedule_catalog_filter_refresh()
        window._handle_catalog_filters_changed()
        QTest.qWait(window.catalog_filter_debounce_timer.interval() + 80)

        self.assertEqual(callback.call_count, 1)

    def test_inventory_immediate_refresh_cancels_pending_debounce(self) -> None:
        window = MainWindow(user_id=1)
        callback = Mock()
        window._run_inventory_filter_refresh = callback

        window._schedule_inventory_filter_refresh()
        window._handle_inventory_filters_changed()
        QTest.qWait(window.inventory_filter_debounce_timer.interval() + 80)

        self.assertEqual(callback.call_count, 1)

    def test_catalog_type_filter_accepts_macro_value_without_accent(self) -> None:
        window = MainWindow(user_id=1)
        window.catalog_type_filter_combo.set_items(
            [
                ("Básico", "Básico"),
                ("Deportivo", "Deportivo"),
            ]
        )

        window.catalog_type_filter_combo.set_selected_values(["Basico"])

        self.assertEqual(window.catalog_type_filter_combo.selected_values(), {"Básico"})

    def test_catalog_active_filter_chips_show_search_and_linea_tokens(self) -> None:
        window = MainWindow(user_id=1)
        window._handle_catalog_filters_changed = Mock()
        window.catalog_search_input.blockSignals(True)
        window.catalog_search_input.setText("pants")
        window.catalog_search_input.blockSignals(False)
        window.catalog_type_filter_combo.set_items(
            [
                ("Deportivo", "Deportivo"),
                ("Oficial", "Oficial"),
            ]
        )
        window.catalog_type_filter_combo.set_selected_values(["Deportivo"])

        window._refresh_catalog_active_filter_chips()

        layout = window.catalog_active_filters_flow_layout
        texts = [layout.itemAt(index).widget().text() for index in range(layout.count())]
        self.assertFalse(window.catalog_active_filters_wrap.isHidden())
        self.assertEqual(
            texts,
            ['Texto: "pants"  ×', "Linea: Deportivo  ×"],
        )

    def test_catalog_and_inventory_hide_category_filters(self) -> None:
        window = MainWindow(user_id=1)

        self.assertTrue(window.catalog_category_filter_combo.isHidden())
        self.assertTrue(window.inventory_category_filter_combo.isHidden())
        self.assertFalse(window.catalog_type_filter_combo.isHidden())
        self.assertFalse(window.inventory_type_filter_combo.isHidden())

    def test_hidden_category_filter_does_not_generate_active_chips(self) -> None:
        window = MainWindow(user_id=1)
        window.catalog_category_filter_combo.set_items([("Básico", "Básico")])
        window.catalog_category_filter_combo.set_selected_values(["Básico"])
        window.inventory_category_filter_combo.set_items([("Básico", "Básico")])
        window.inventory_category_filter_combo.set_selected_values(["Básico"])

        self.assertEqual(window._catalog_active_filter_tokens(), [])
        self.assertEqual(window._inventory_active_filter_tokens(), [])

    def test_catalog_hides_status_filter_and_forces_active_rows(self) -> None:
        window = MainWindow(user_id=1)
        snapshot_rows = [{"variante_id": 1, "sku": "SKU-001"}]
        summary_view = SimpleNamespace(results_summary="1 resultado", active_filters_summary="Sin filtros")

        with patch.object(window, "_load_catalog_snapshot_rows", return_value=snapshot_rows), patch(
            "pos_uniformes.ui.main_window.filter_visible_catalog_rows",
            return_value=snapshot_rows,
        ) as filter_mock, patch(
            "pos_uniformes.ui.main_window.build_catalog_table_row_views",
            return_value=[],
        ), patch(
            "pos_uniformes.ui.main_window.build_catalog_summary_view",
            return_value=summary_view,
        ):
            window._refresh_catalog()

        self.assertTrue(window.catalog_status_filter_combo.isHidden())
        self.assertEqual(filter_mock.call_args.kwargs["filters"].status_filter, "active")

    def test_remove_catalog_multi_filter_chip_keeps_other_selected_values(self) -> None:
        window = MainWindow(user_id=1)
        window.catalog_page_index = 3
        window._handle_catalog_filters_changed = Mock()
        window.catalog_type_filter_combo.set_items(
            [
                ("Deportivo", "Deportivo"),
                ("Oficial", "Oficial"),
            ]
        )
        window.catalog_type_filter_combo.set_selected_values(["Deportivo", "Oficial"])

        window._handle_remove_catalog_filter_token(
            ActiveFilterToken(
                key="linea",
                display_text="Linea: Deportivo",
                value="Deportivo",
            )
        )

        self.assertEqual(window.catalog_type_filter_combo.selected_values(), {"Oficial"})
        self.assertEqual(window.catalog_page_index, 0)

    def test_refresh_catalog_does_not_force_explicit_column_resize(self) -> None:
        window = MainWindow(user_id=1)
        catalog_row = {"variante_id": 1, "sku": "SKU-001"}
        table_row_view = SimpleNamespace(
            values=[
                "SKU-001",
                "General",
                "Deportivo",
                "Pants",
                "Marca Norte",
                "Pants Deportivo",
                "16",
                "Azul",
                "$219.00",
                "6",
                "2",
                "Activa",
            ],
            row_tone=None,
            stock_tone="positive",
            layaway_tone="warning",
            status_tone="positive",
        )
        summary_view = SimpleNamespace(results_summary="1 resultado", active_filters_summary="Sin filtros")

        with patch.object(window, "_load_catalog_snapshot_rows", return_value=[catalog_row]), patch(
            "pos_uniformes.ui.main_window.filter_visible_catalog_rows",
            return_value=[catalog_row],
        ), patch(
            "pos_uniformes.ui.main_window.build_catalog_table_row_views",
            return_value=[table_row_view],
        ), patch(
            "pos_uniformes.ui.main_window.build_catalog_summary_view",
            return_value=summary_view,
        ), patch("PyQt6.QtWidgets.QTableWidget.resizeColumnsToContents") as resize_mock:
            window._refresh_catalog()

        resize_mock.assert_not_called()

    def test_refresh_inventory_does_not_force_explicit_column_resize(self) -> None:
        window = MainWindow(user_id=1)
        inventory_row = {"variante_id": 2, "sku": "SKU-002"}
        table_row_view = SimpleNamespace(
            values=[
                "SKU-002",
                "Pants Deportivo",
                "16",
                "Azul",
                "6",
                "2",
                "Activa",
                "OK",
            ],
            row_tone=None,
            variant_id=2,
            stock_tone="positive",
            committed_tone="warning",
            status_tone="positive",
            qr_tone="positive",
        )
        summary_view = SimpleNamespace(
            out_counter=SimpleNamespace(text="0", tone="positive"),
            low_counter=SimpleNamespace(text="0", tone="positive"),
            qr_pending_counter=SimpleNamespace(text="0", tone="positive"),
            inactive_counter=SimpleNamespace(text="0", tone="positive"),
            results_summary="1 resultado",
        )

        with patch.object(window, "_load_inventory_snapshot_rows", return_value=[inventory_row]), patch(
            "pos_uniformes.ui.main_window.filter_visible_inventory_rows",
            return_value=[inventory_row],
        ), patch(
            "pos_uniformes.ui.main_window.build_inventory_table_row_views",
            return_value=[table_row_view],
        ), patch(
            "pos_uniformes.ui.main_window.build_inventory_summary_view",
            return_value=summary_view,
        ), patch.object(window, "_build_inventory_active_filters_summary", return_value="Sin filtros"), patch.object(
            window, "_sync_inventory_table_selection"
        ) as sync_mock, patch.object(window, "_refresh_inventory_overview") as overview_mock, patch(
            "PyQt6.QtWidgets.QTableWidget.resizeColumnsToContents"
        ) as resize_mock:
            window._refresh_inventory_table()

        resize_mock.assert_not_called()
        sync_mock.assert_called_once()
        overview_mock.assert_called_once()

    def test_refresh_inventory_limits_visible_rows_to_single_page(self) -> None:
        window = MainWindow(user_id=1)
        filtered_rows = [{"variante_id": index, "sku": f"SKU-{index:03d}"} for index in range(60)]
        table_row_view = SimpleNamespace(
            values=[
                "SKU-000",
                "Pants Deportivo",
                "16",
                "Azul",
                "6",
                "2",
                "Activa",
                "OK",
            ],
            row_tone=None,
            variant_id=0,
            stock_tone="positive",
            committed_tone="warning",
            status_tone="positive",
            qr_tone="positive",
        )
        summary_view = SimpleNamespace(
            out_counter=SimpleNamespace(text="0", tone="positive"),
            low_counter=SimpleNamespace(text="0", tone="positive"),
            qr_pending_counter=SimpleNamespace(text="0", tone="positive"),
            inactive_counter=SimpleNamespace(text="0", tone="positive"),
            results_summary="60 resultados",
        )

        with patch.object(window, "_load_inventory_snapshot_rows", return_value=filtered_rows), patch(
            "pos_uniformes.ui.main_window.filter_visible_inventory_rows",
            return_value=filtered_rows,
        ), patch(
            "pos_uniformes.ui.main_window.build_inventory_table_row_views",
            return_value=[table_row_view] * INVENTORY_PAGE_SIZE,
        ), patch(
            "pos_uniformes.ui.main_window.build_inventory_summary_view",
            return_value=summary_view,
        ), patch.object(window, "_build_inventory_active_filters_summary", return_value="Sin filtros"), patch.object(
            window, "_sync_inventory_table_selection"
        ), patch.object(window, "_refresh_inventory_overview"):
            window._refresh_inventory_table()

        self.assertEqual(len(window.inventory_filtered_rows), 60)
        self.assertEqual(len(window.inventory_rows), INVENTORY_PAGE_SIZE)
        self.assertEqual(window.inventory_pagination_label.text(), "1-25 de 60 | p. 1/3")
        self.assertFalse(window.inventory_previous_page_button.isEnabled())
        self.assertTrue(window.inventory_next_page_button.isEnabled())

    def test_inventory_filter_reset_page_methods_return_to_first_page(self) -> None:
        window = MainWindow(user_id=1)
        window.inventory_page_index = 3
        handle_callback = Mock()
        schedule_callback = Mock()
        window._handle_inventory_filters_changed = handle_callback
        window._schedule_inventory_filter_refresh = schedule_callback

        window._handle_inventory_filters_changed_reset_page()
        self.assertEqual(window.inventory_page_index, 0)
        handle_callback.assert_called_once()

        window.inventory_page_index = 4
        window._schedule_inventory_filter_refresh_reset_page()
        self.assertEqual(window.inventory_page_index, 0)
        schedule_callback.assert_called_once()

    def test_clear_inventory_filters_batches_refresh_into_single_pass(self) -> None:
        window = MainWindow(user_id=1)
        window.inventory_search_input.setText("pants")
        window.inventory_brand_filter_combo.set_items([("Marca Norte", "Marca Norte")])
        window.inventory_school_filter_combo.set_items([("General", "General")])
        window.inventory_type_filter_combo.set_items([("Deportivo", "Deportivo")])
        window.inventory_brand_filter_combo.set_selected_values(["Marca Norte"])
        window.inventory_school_filter_combo.set_selected_values(["General"])
        window.inventory_type_filter_combo.set_selected_values(["Deportivo"])
        window.inventory_use_filter_combo.addItem("Solo escolar", "school_only")
        window.inventory_use_filter_combo.setCurrentIndex(window.inventory_use_filter_combo.count() - 1)
        window._run_inventory_filter_refresh = Mock()

        window._handle_clear_inventory_filters()

        self.assertEqual(window._run_inventory_filter_refresh.call_count, 1)
        self.assertEqual(window.inventory_search_input.text(), "")
        self.assertEqual(window.inventory_brand_filter_combo.selected_values(), set())
        self.assertEqual(window.inventory_school_filter_combo.selected_values(), set())
        self.assertEqual(window.inventory_type_filter_combo.selected_values(), set())
        self.assertEqual(window.inventory_use_filter_combo.currentIndex(), 0)

    def test_reload_table_widget_restores_updates_and_signals(self) -> None:
        window = MainWindow(user_id=1)
        table = window.catalog_table

        self.assertTrue(table.updatesEnabled())
        self.assertFalse(table.signalsBlocked())

        window._reload_table_widget(
            table,
            row_count=1,
            populate_rows=lambda: table.setItem(0, 0, QTableWidgetItem("SKU-001")),
        )

        self.assertTrue(table.updatesEnabled())
        self.assertFalse(table.signalsBlocked())

    def test_refresh_catalog_limits_visible_rows_to_single_page(self) -> None:
        window = MainWindow(user_id=1)
        filtered_rows = [{"variante_id": index, "sku": f"SKU-{index:03d}"} for index in range(60)]
        summary_view = SimpleNamespace(results_summary="60 resultados", active_filters_summary="Sin filtros")

        def build_row_views(rows: list[dict[str, object]]) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(
                    values=[
                        row["sku"],
                        "General",
                        "Deportivo",
                        "Pants",
                        "Marca Norte",
                        "Pants Deportivo",
                        "16",
                        "Azul",
                        "$219.00",
                        "6",
                        "2",
                        "Activa",
                    ],
                    row_tone=None,
                    stock_tone="positive",
                    layaway_tone="warning",
                    status_tone="positive",
                )
                for row in rows
            ]

        with patch.object(window, "_load_catalog_snapshot_rows", return_value=filtered_rows), patch(
            "pos_uniformes.ui.main_window.filter_visible_catalog_rows",
            return_value=filtered_rows,
        ), patch(
            "pos_uniformes.ui.main_window.build_catalog_table_row_views",
            side_effect=build_row_views,
        ), patch(
            "pos_uniformes.ui.main_window.build_catalog_summary_view",
            return_value=summary_view,
        ):
            window._refresh_catalog()

        self.assertEqual(len(window.catalog_filtered_rows), 60)
        self.assertEqual(len(window.catalog_rows), CATALOG_PAGE_SIZE)
        self.assertEqual(window.catalog_rows[0]["variante_id"], 0)
        self.assertEqual(window.catalog_rows[-1]["variante_id"], CATALOG_PAGE_SIZE - 1)
        self.assertEqual(
            window.catalog_pagination_label.text(),
            "1-25 de 60 | p. 1/3",
        )
        self.assertFalse(window.catalog_previous_page_button.isEnabled())
        self.assertTrue(window.catalog_next_page_button.isEnabled())

    def test_catalog_page_navigation_changes_page_without_resetting_to_selection(self) -> None:
        window = MainWindow(user_id=1)
        window.catalog_page_index = 0
        window.catalog_preserve_selection_on_refresh = True
        callback = Mock()
        window._handle_catalog_filters_changed = callback

        window._handle_catalog_next_page()

        self.assertEqual(window.catalog_page_index, 1)
        self.assertFalse(window.catalog_preserve_selection_on_refresh)
        callback.assert_called_once()

    def test_catalog_filter_reset_page_methods_return_to_first_page(self) -> None:
        window = MainWindow(user_id=1)
        window.catalog_page_index = 3
        handle_callback = Mock()
        schedule_callback = Mock()
        window._handle_catalog_filters_changed = handle_callback
        window._schedule_catalog_filter_refresh = schedule_callback

        window._handle_catalog_filters_changed_reset_page()
        self.assertEqual(window.catalog_page_index, 0)
        handle_callback.assert_called_once()

        window.catalog_page_index = 4
        window._schedule_catalog_filter_refresh_reset_page()
        self.assertEqual(window.catalog_page_index, 0)
        schedule_callback.assert_called_once()


    def test_dialog_prefill_variant_id_reads_from_inventory_table_not_combo(self) -> None:
        window = MainWindow(user_id=1)
        window.inventory_table.setRowCount(1)
        window.inventory_table.setColumnCount(1)
        item = QTableWidgetItem("SKU-007")
        item.setData(Qt.ItemDataRole.UserRole, 7)
        window.inventory_table.setItem(0, 0, item)
        window.inventory_table.blockSignals(True)
        window.inventory_table.setCurrentCell(0, 0)
        window.inventory_table.blockSignals(False)

        result = window._dialog_prefill_variant_id()

        self.assertEqual(result, 7)

    def test_dialog_prefill_variant_id_returns_none_when_no_row_selected(self) -> None:
        window = MainWindow(user_id=1)

        result = window._dialog_prefill_variant_id()

        self.assertIsNone(result)

    def test_create_or_edit_presentation_raises_when_initial_and_prefill_both_set(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.ADMIN
        dummy = {"variante_id": 1, "producto_id": 1}

        with self.assertRaises(ValueError):
            window._create_or_edit_presentation(
                initial=dummy,
                prefill=dummy,
                include_stock=True,
            )

    def test_context_menu_syncs_combo_to_right_clicked_row(self) -> None:
        from PyQt6.QtCore import QPoint
        window = MainWindow(user_id=1)
        window.inventory_table.setRowCount(2)
        window.inventory_table.setColumnCount(1)
        for row_idx, variant_id in [(0, 11), (1, 22)]:
            item = QTableWidgetItem(f"SKU-{variant_id:03d}")
            item.setData(Qt.ItemDataRole.UserRole, variant_id)
            window.inventory_table.setItem(row_idx, 0, item)
        window.inventory_variant_combo.addItem("SKU-011", 11)
        window.inventory_variant_combo.addItem("SKU-022", 22)
        window.inventory_variant_combo.setCurrentIndex(0)

        with patch("pos_uniformes.ui.main_window.prompt_inventory_context_action", return_value=None):
            pos = QPoint(0, window.inventory_table.rowViewportPosition(1))
            window._show_inventory_context_menu(pos)

        self.assertEqual(window.inventory_variant_combo.currentData(), 22)

    def test_build_bulk_selection_label_shows_count_when_all_match(self) -> None:
        rows = [{"variante_id": 1}, {"variante_id": 2}]
        label = _build_bulk_selection_label([1, 2], rows)
        self.assertEqual(label, "Filas seleccionadas (2)")

    def test_build_bulk_selection_label_warns_when_some_filtered_out(self) -> None:
        rows = [{"variante_id": 1}]
        label = _build_bulk_selection_label([1, 2, 3], rows)
        self.assertIn("1 de 3", label)
        self.assertIn("2 no coinciden", label)

    def test_build_bulk_selection_label_single_match_no_warning(self) -> None:
        rows = [{"variante_id": 5}]
        label = _build_bulk_selection_label([5], rows)
        self.assertEqual(label, "Filas seleccionadas (1)")

    def test_duplicate_variant_warns_when_inventory_table_has_no_selection(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.ADMIN

        with patch("pos_uniformes.ui.main_window.QMessageBox.warning") as warn_mock, \
             patch.object(window, "_create_or_edit_presentation") as create_mock:
            window._handle_duplicate_variant()

        warn_mock.assert_called_once()
        self.assertIn("inventario", warn_mock.call_args[0][2].lower())
        create_mock.assert_not_called()

    def test_duplicate_variant_warns_when_only_catalog_table_has_selection(self) -> None:
        window = MainWindow(user_id=1)
        window.current_role = RolUsuario.ADMIN
        window.catalog_rows = [{"variante_id": 7, "sku": "SKU-007", "producto_id": 1}]
        window.catalog_table.setRowCount(1)
        window.catalog_table.setColumnCount(1)
        window.catalog_table.blockSignals(True)
        window.catalog_table.setCurrentCell(0, 0)
        window.catalog_table.blockSignals(False)

        with patch("pos_uniformes.ui.main_window.QMessageBox.warning") as warn_mock, \
             patch.object(window, "_create_or_edit_presentation") as create_mock:
            window._handle_duplicate_variant()

        warn_mock.assert_called_once()
        create_mock.assert_not_called()

    def test_set_combo_value_selects_matching_item(self) -> None:
        from PyQt6.QtWidgets import QComboBox
        combo = QComboBox()
        combo.addItem("Alfa", 1)
        combo.addItem("Beta", 2)
        combo.addItem("Gamma", 3)
        combo.setCurrentIndex(0)

        MainWindow._set_combo_value(combo, 2)

        self.assertEqual(combo.currentData(), 2)

    def test_set_combo_value_clears_when_value_not_found(self) -> None:
        from PyQt6.QtWidgets import QComboBox
        combo = QComboBox()
        combo.addItem("Alfa", 1)
        combo.addItem("Beta", 2)
        combo.setCurrentIndex(0)

        MainWindow._set_combo_value(combo, 99)

        self.assertEqual(combo.currentIndex(), -1)

    def test_set_combo_value_leaves_combo_unchanged_when_value_is_none(self) -> None:
        from PyQt6.QtWidgets import QComboBox
        combo = QComboBox()
        combo.addItem("Alfa", 1)
        combo.addItem("Beta", 2)
        combo.setCurrentIndex(1)

        MainWindow._set_combo_value(combo, None)

        self.assertEqual(combo.currentIndex(), 1)

    def test_refresh_inventory_jumps_to_page_of_selected_variant(self) -> None:
        window = MainWindow(user_id=1)
        filtered_rows = [{"variante_id": i, "sku": f"SKU-{i:03d}"} for i in range(30)]
        variant_on_page1 = 27
        window.inventory_variant_combo.addItem("SKU-027", variant_on_page1)
        window.inventory_variant_combo.setCurrentIndex(
            window.inventory_variant_combo.findData(variant_on_page1)
        )
        window.inventory_page_index = 0

        table_row_view = SimpleNamespace(
            values=["SKU-027", "P", "M", "Rojo", "3", "0", "Activa", "OK"],
            row_tone=None,
            variant_id=variant_on_page1,
            stock_tone="positive",
            committed_tone=None,
            status_tone="positive",
            qr_tone="positive",
        )
        summary_view = SimpleNamespace(
            out_counter=SimpleNamespace(text="0", tone="positive"),
            low_counter=SimpleNamespace(text="0", tone="positive"),
            qr_pending_counter=SimpleNamespace(text="0", tone="positive"),
            inactive_counter=SimpleNamespace(text="0", tone="positive"),
            results_summary="30 resultados",
        )

        with patch.object(window, "_load_inventory_snapshot_rows", return_value=filtered_rows), patch(
            "pos_uniformes.ui.main_window.filter_visible_inventory_rows",
            return_value=filtered_rows,
        ), patch(
            "pos_uniformes.ui.main_window.build_inventory_table_row_views",
            return_value=[table_row_view] * INVENTORY_PAGE_SIZE,
        ), patch(
            "pos_uniformes.ui.main_window.build_inventory_summary_view",
            return_value=summary_view,
        ), patch.object(window, "_build_inventory_active_filters_summary", return_value="Sin filtros"), patch.object(
            window, "_sync_inventory_table_selection"
        ), patch.object(window, "_refresh_inventory_overview"):
            window._refresh_inventory_table()

        self.assertEqual(window.inventory_page_index, 1)

    def test_refresh_inventory_stays_on_page_when_selected_variant_not_in_filtered_rows(self) -> None:
        window = MainWindow(user_id=1)
        filtered_rows = [{"variante_id": i, "sku": f"SKU-{i:03d}"} for i in range(30)]
        window.inventory_variant_combo.addItem("SKU-999", 999)
        window.inventory_variant_combo.setCurrentIndex(
            window.inventory_variant_combo.findData(999)
        )
        window.inventory_page_index = 0

        table_row_view = SimpleNamespace(
            values=["SKU-000", "P", "M", "Rojo", "3", "0", "Activa", "OK"],
            row_tone=None,
            variant_id=0,
            stock_tone="positive",
            committed_tone=None,
            status_tone="positive",
            qr_tone="positive",
        )
        summary_view = SimpleNamespace(
            out_counter=SimpleNamespace(text="0", tone="positive"),
            low_counter=SimpleNamespace(text="0", tone="positive"),
            qr_pending_counter=SimpleNamespace(text="0", tone="positive"),
            inactive_counter=SimpleNamespace(text="0", tone="positive"),
            results_summary="30 resultados",
        )

        with patch.object(window, "_load_inventory_snapshot_rows", return_value=filtered_rows), patch(
            "pos_uniformes.ui.main_window.filter_visible_inventory_rows",
            return_value=filtered_rows,
        ), patch(
            "pos_uniformes.ui.main_window.build_inventory_table_row_views",
            return_value=[table_row_view] * INVENTORY_PAGE_SIZE,
        ), patch(
            "pos_uniformes.ui.main_window.build_inventory_summary_view",
            return_value=summary_view,
        ), patch.object(window, "_build_inventory_active_filters_summary", return_value="Sin filtros"), patch.object(
            window, "_sync_inventory_table_selection"
        ), patch.object(window, "_refresh_inventory_overview"):
            window._refresh_inventory_table()

        self.assertEqual(window.inventory_page_index, 0)

    def test_sync_inventory_table_selection_none_does_not_fire_selection_handler(self) -> None:
        window = MainWindow(user_id=1)
        window.inventory_table.setRowCount(3)
        window.inventory_table.setColumnCount(1)
        for row in range(3):
            item = QTableWidgetItem(f"SKU-{row:03d}")
            item.setData(Qt.ItemDataRole.UserRole, row + 1)
            window.inventory_table.setItem(row, 0, item)
        window.inventory_variant_combo.addItem("SKU-001", 1)
        window.inventory_variant_combo.addItem("SKU-002", 2)
        window.inventory_variant_combo.addItem("SKU-003", 3)
        window.inventory_variant_combo.setCurrentIndex(-1)

        handler_calls: list[object] = []
        original = window._handle_inventory_table_selection
        window._handle_inventory_table_selection = lambda: handler_calls.append(True) or original()  # type: ignore[method-assign]

        window._sync_inventory_table_selection(None)

        self.assertEqual(handler_calls, [], "_handle_inventory_table_selection no debe dispararse")
        self.assertEqual(window.inventory_variant_combo.currentIndex(), -1)


if __name__ == "__main__":
    unittest.main()
