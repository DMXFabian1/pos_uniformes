"""Dialogo de administracion del satelite (Ctrl+Shift+A, PIN admin)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.satellite_startup_service import probe_database_host
from pos_uniformes.utils.config import settings, _appdata_config_dir, runtime_base_dir

_ADMIN_PIN = "634700"
_ENV_FILENAME = "pos_uniformes.env"


def _find_env_path() -> Path:
    """Devuelve la ruta del .env que el bundle usa (AppData primero, luego carpeta exe)."""
    appdata = _appdata_config_dir()
    if appdata is not None:
        candidate = appdata / _ENV_FILENAME
        if candidate.exists():
            return candidate
        return candidate  # si no existe, lo creamos ahí
    return runtime_base_dir() / _ENV_FILENAME


def _write_env(host: str, password: str) -> None:
    path = _find_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"POS_UNIFORMES_DB_HOST={host}",
        f"POS_UNIFORMES_DB_PORT={settings.db_port}",
        f"POS_UNIFORMES_DB_NAME={settings.db_name}",
        f"POS_UNIFORMES_DB_USER={settings.db_user}",
        f"POS_UNIFORMES_DB_PASSWORD={password}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _restart_app() -> None:
    os.execv(sys.executable, sys.argv)


def _prompt_pin(parent: QWidget) -> bool:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Acceso administrador")
    dialog.setMinimumWidth(320)
    layout = QVBoxLayout()
    label = QLabel("Ingresa el PIN de administrador:")
    label.setWordWrap(True)
    pin_input = QLineEdit()
    pin_input.setEchoMode(QLineEdit.EchoMode.Password)
    pin_input.setPlaceholderText("PIN")
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(label)
    layout.addWidget(pin_input)
    layout.addWidget(buttons)
    dialog.setLayout(layout)
    pin_input.returnPressed.connect(dialog.accept)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    return pin_input.text().strip() == _ADMIN_PIN


def open_satellite_admin_dialog(parent: QWidget) -> None:
    if not _prompt_pin(parent):
        QMessageBox.warning(parent, "PIN incorrecto", "PIN incorrecto.")
        return

    dialog = QDialog(parent)
    dialog.setWindowTitle("Administracion del satelite")
    dialog.setMinimumWidth(460)
    layout = QVBoxLayout()
    layout.setSpacing(16)

    # — Estado actual —
    status_box = QGroupBox("Estado de conexion")
    status_form = QFormLayout()
    status_form.setSpacing(8)
    current_host_label = QLabel(settings.db_host)
    current_host_label.setObjectName("subtleLine")
    env_path_label = QLabel(str(_find_env_path()))
    env_path_label.setWordWrap(True)
    env_path_label.setObjectName("subtleLine")
    status_form.addRow("Host actual:", current_host_label)
    status_form.addRow("Archivo .env:", env_path_label)
    status_box.setLayout(status_form)

    # — Configurar conexion —
    config_box = QGroupBox("Cambiar conexion")
    config_form = QFormLayout()
    config_form.setSpacing(8)
    host_input = QLineEdit(settings.db_host)
    host_input.setPlaceholderText("192.168.0.10")
    password_input = QLineEdit(settings.db_password)
    password_input.setEchoMode(QLineEdit.EchoMode.Password)
    password_input.setPlaceholderText("Contrasena de la base de datos")
    config_form.addRow("Host (IP de la PC principal):", host_input)
    config_form.addRow("Contrasena BD:", password_input)

    test_result_label = QLabel("")
    test_result_label.setWordWrap(True)

    test_btn = QPushButton("Probar conexion")
    save_btn = QPushButton("Guardar y reiniciar")
    save_btn.setObjectName("primaryButton")

    def handle_test() -> None:
        host = host_input.text().strip()
        if not host:
            test_result_label.setText("Ingresa una IP o nombre de host.")
            return
        test_result_label.setText(f"Probando conexion a {host}...")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        ok = probe_database_host(override_host=host)
        if ok:
            test_result_label.setText(f"✓ Conexion exitosa a {host}")
            test_result_label.setStyleSheet("color: green;")
        else:
            test_result_label.setText(f"✗ No se pudo conectar a {host}. Verifica la IP y que la PC principal este encendida.")
            test_result_label.setStyleSheet("color: red;")

    def handle_save() -> None:
        host = host_input.text().strip()
        password = password_input.text().strip()
        if not host:
            QMessageBox.warning(dialog, "Datos incompletos", "Ingresa el host.")
            return
        try:
            _write_env(host, password)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Error al guardar", f"No se pudo escribir el archivo .env:\n{exc}")
            return
        QMessageBox.information(
            dialog,
            "Guardado",
            f"Configuracion guardada. La app se reiniciara ahora apuntando a {host}.",
        )
        dialog.accept()
        _restart_app()

    test_btn.clicked.connect(handle_test)
    save_btn.clicked.connect(handle_save)

    btn_row = QHBoxLayout()
    btn_row.addWidget(test_btn)
    btn_row.addWidget(save_btn)

    config_layout = QVBoxLayout()
    config_layout.addLayout(config_form)
    config_layout.addWidget(test_result_label)
    config_layout.addLayout(btn_row)
    config_box.setLayout(config_layout)

    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)

    layout.addWidget(status_box)
    layout.addWidget(config_box)
    layout.addWidget(close_buttons)
    dialog.setLayout(layout)
    dialog.exec()
