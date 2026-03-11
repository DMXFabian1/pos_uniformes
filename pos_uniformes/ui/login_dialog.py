"""Dialogo de inicio de sesion para el POS."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QColor, QGuiApplication, QPalette
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pos_uniformes.database.connection import get_session
from pos_uniformes.services.auth_service import AuthService


class LoginDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.user_id: int | None = None
        self.setWindowTitle("Iniciar sesion")
        self.setModal(True)
        self.resize(460, 280)
        self._apply_styles()
        self._build_ui()
        self._caps_timer = QTimer(self)
        self._caps_timer.setInterval(250)
        self._caps_timer.timeout.connect(self._update_caps_lock_warning)
        self._caps_timer.start()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background: #f3efe8;
                color: #1f1f1b;
                font-family: "Avenir Next", "Helvetica Neue", sans-serif;
                font-size: 14px;
            }
            QFrame#loginCard {
                background: #fbf8f2;
                border: 1px solid #d7d0c4;
                border-radius: 18px;
            }
            QLabel#loginTitle {
                color: #8f4527;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#loginHint {
                color: #6d665e;
                font-size: 13px;
            }
            QLabel#loginStatus {
                border-radius: 10px;
                padding: 8px 10px;
                font-weight: 700;
            }
            QLineEdit {
                background: #fffaf2;
                color: #1f1f1b;
                border: 1px solid #d2c7b8;
                border-radius: 12px;
                padding: 10px 12px;
                min-height: 22px;
                selection-background-color: #c96a35;
                selection-color: #f9f4ea;
            }
            QLineEdit[echoMode="2"] {
                color: #1f1f1b;
            }
            QLineEdit::placeholder {
                color: #8b8377;
            }
            QLineEdit:focus {
                border: 2px solid #c96a35;
            }
            QLineEdit[state="error"] {
                background: #fff4f1;
                border: 2px solid #c85a4b;
            }
            QLineEdit[state="error"]::placeholder {
                color: #aa8177;
            }
            QFormLayout QLabel {
                color: #2d2b27;
                font-weight: 700;
            }
            QPushButton {
                border-radius: 12px;
                padding: 8px 14px;
                font-weight: 800;
            }
            QPushButton#loginPrimaryButton {
                background: #8f4527;
                color: #f9f4ea;
            }
            QPushButton#loginPrimaryButton:hover {
                background: #bb613c;
            }
            QPushButton#loginGhostButton {
                background: #efe7d9;
                color: #2d2b27;
            }
            QPushButton#loginGhostButton:hover {
                background: #e6dccd;
            }
            QPushButton#loginTinyButton {
                background: #faeadf;
                color: #8f4527;
                min-width: 78px;
            }
            QPushButton#loginTinyButton:hover {
                background: #f8dfcf;
            }
            """
        )

    def _build_ui(self) -> None:
        title = QLabel("Iniciar sesion")
        title.setObjectName("loginTitle")
        hint = QLabel("Captura tu usuario y contrasena para continuar.")
        hint.setObjectName("loginHint")
        self.status_label = QLabel("")
        self.status_label.setObjectName("loginStatus")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        self.caps_lock_label = QLabel("Mayus activado")
        self.caps_lock_label.setObjectName("loginStatus")
        self.caps_lock_label.setWordWrap(True)
        self.caps_lock_label.hide()

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Usuario")
        self.username_input.setStyleSheet("color: #1f1f1b;")
        self._apply_login_input_palette(self.username_input)
        self.username_input.textChanged.connect(self._clear_login_error_state)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Contrasena")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet("color: #1f1f1b;")
        self._apply_login_input_palette(self.password_input)
        self.password_input.textChanged.connect(self._clear_login_error_state)
        self.password_input.installEventFilter(self)
        self.password_toggle_button = QPushButton("Mostrar")
        self.password_toggle_button.setObjectName("loginTinyButton")
        self.password_toggle_button.setCheckable(True)
        self.password_toggle_button.toggled.connect(self._toggle_password_visibility)
        self.username_input.returnPressed.connect(self._handle_login)
        self.password_input.returnPressed.connect(self._handle_login)

        form = QFormLayout()
        form.addRow("Usuario", self.username_input)
        password_row = QHBoxLayout()
        password_row.setSpacing(8)
        password_row.addWidget(self.password_input, 1)
        password_row.addWidget(self.password_toggle_button, 0)
        form.addRow("Contrasena", password_row)
        for index in range(form.rowCount()):
            label_item = form.itemAt(index, QFormLayout.ItemRole.LabelRole)
            if label_item is None:
                continue
            label_widget = label_item.widget()
            if isinstance(label_widget, QLabel):
                label_widget.setStyleSheet("color: #2d2b27; font-weight: 700;")

        login_button = QPushButton("Entrar")
        login_button.setObjectName("loginPrimaryButton")
        login_button.clicked.connect(self._handle_login)
        cancel_button = QPushButton("Salir")
        cancel_button.setObjectName("loginGhostButton")
        cancel_button.clicked.connect(self.reject)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(cancel_button)
        actions.addWidget(login_button)

        card = QFrame()
        card.setObjectName("loginCard")
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(12)
        card_layout.addWidget(title)
        card_layout.addWidget(hint)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.caps_lock_label)
        card_layout.addLayout(form)
        card_layout.addLayout(actions)
        card.setLayout(card_layout)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.addStretch()
        layout.addWidget(card)
        layout.addStretch()
        self.setLayout(layout)
        self.username_input.setFocus()

    def _apply_login_input_palette(self, field: QLineEdit) -> None:
        palette = field.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor("#1f1f1b"))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8b8377"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#fffaf2"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#c96a35"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#f9f4ea"))
        field.setPalette(palette)

    def _set_status(self, text: str, tone: str = "neutral") -> None:
        palette = {
            "neutral": ("#fbf3ec", "#8c6656", "#ecd5c5"),
            "warning": ("#fbf0cf", "#8a5a00", "#e7d49b"),
            "danger": ("#f8dfd9", "#9a2f22", "#dfb3aa"),
        }
        background, foreground, border = palette.get(tone, palette["neutral"])
        self.status_label.setStyleSheet(
            f"background: {background}; color: {foreground}; border: 1px solid {border}; "
            "border-radius: 10px; padding: 8px 10px;"
        )
        self.status_label.setText(text)
        self.status_label.show()

    def _set_caps_warning_visible(self, visible: bool) -> None:
        if visible:
            self.caps_lock_label.setStyleSheet(
                "background: #fbf0cf; color: #8a5a00; border: 1px solid #e7d49b; "
                "border-radius: 10px; padding: 8px 10px; font-weight: 700;"
            )
            self.caps_lock_label.show()
        else:
            self.caps_lock_label.hide()

    def _is_caps_lock_enabled(self) -> bool:
        caps_modifier = getattr(Qt.KeyboardModifier, "CapsLockModifier", None)
        if caps_modifier is None:
            return False
        modifiers = QGuiApplication.queryKeyboardModifiers()
        return bool(modifiers & caps_modifier)

    def _update_caps_lock_warning(self) -> None:
        should_show = self.password_input.hasFocus() and self._is_caps_lock_enabled()
        self._set_caps_warning_visible(should_show)

    def _set_field_error_state(self, username_error: bool = False, password_error: bool = False) -> None:
        self.username_input.setProperty("state", "error" if username_error else "")
        self.password_input.setProperty("state", "error" if password_error else "")
        for field in (self.username_input, self.password_input):
            field.style().unpolish(field)
            field.style().polish(field)
            field.update()

    def _clear_login_error_state(self) -> None:
        self._set_field_error_state(False, False)
        if self.status_label.isVisible():
            self.status_label.hide()

    def _toggle_password_visibility(self, checked: bool) -> None:
        self.password_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.password_toggle_button.setText("Ocultar" if checked else "Mostrar")
        self._update_caps_lock_warning()

    def eventFilter(self, watched, event):  # type: ignore[override]
        if watched is self.password_input and event.type() in {
            QEvent.Type.FocusIn,
            QEvent.Type.FocusOut,
            QEvent.Type.KeyPress,
            QEvent.Type.KeyRelease,
        }:
            self._update_caps_lock_warning()
        return super().eventFilter(watched, event)

    def _handle_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self._set_field_error_state(not bool(username), not bool(password))
            self._set_status("Captura usuario y contrasena.", "warning")
            if not username:
                self.username_input.setFocus()
            else:
                self.password_input.setFocus()
            return

        try:
            with get_session() as session:
                user = AuthService.authenticate(session, username, password)
                if user is None:
                    self._set_field_error_state(True, True)
                    self._set_status("Usuario o contrasena incorrectos.", "warning")
                    self.password_input.setFocus()
                    self.password_input.selectAll()
                    return
                session.commit()
                self.user_id = user.id
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error de autenticacion", str(exc))
            return

        self.accept()
