"""Dialogo de administracion del satelite (Ctrl+Shift+A, PIN admin)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtPrintSupport import QPrinterInfo
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.satellite_startup_service import probe_database_host
from pos_uniformes.services.ticket_print_settings_cache_service import (
    load_ticket_print_settings,
    save_ticket_print_settings,
)
from pos_uniformes.utils.config import settings, _appdata_config_dir, runtime_base_dir

_ADMIN_PIN = "634700"
_ENV_FILENAME = "pos_uniformes.env"


def _find_env_path() -> Path:
    appdata = _appdata_config_dir()
    if appdata is not None:
        candidate = appdata / _ENV_FILENAME
        if candidate.exists():
            return candidate
        return candidate
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
    dialog.setMinimumWidth(480)
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

    # — Conexion —
    config_box = QGroupBox("Cambiar conexion")
    config_form = QFormLayout()
    config_form.setSpacing(8)
    host_input = QLineEdit(settings.db_host)
    host_input.setPlaceholderText("192.168.0.10")
    password_input = QLineEdit(settings.db_password)
    password_input.setEchoMode(QLineEdit.EchoMode.Password)
    password_input.setPlaceholderText("Contrasena de la base de datos")
    config_form.addRow("Host (IP PC principal):", host_input)
    config_form.addRow("Contrasena BD:", password_input)

    test_result_label = QLabel("")
    test_result_label.setWordWrap(True)
    test_btn = QPushButton("Probar conexion")
    save_conn_btn = QPushButton("Guardar y reiniciar")
    save_conn_btn.setObjectName("primaryButton")

    def handle_test() -> None:
        host = host_input.text().strip()
        if not host:
            test_result_label.setText("Ingresa una IP.")
            return
        test_result_label.setText(f"Probando {host}...")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        if probe_database_host(override_host=host):
            test_result_label.setText(f"✓ Conexion exitosa a {host}")
            test_result_label.setStyleSheet("color: green;")
        else:
            test_result_label.setText(f"✗ Sin respuesta en {host}. Verifica IP y que la PC principal este encendida.")
            test_result_label.setStyleSheet("color: red;")

    def handle_save_conn() -> None:
        host = host_input.text().strip()
        password = password_input.text().strip()
        if not host:
            QMessageBox.warning(dialog, "Datos incompletos", "Ingresa el host.")
            return
        try:
            _write_env(host, password)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Error al guardar", f"No se pudo escribir .env:\n{exc}")
            return
        QMessageBox.information(dialog, "Guardado", f"Configuracion guardada. Reiniciando hacia {host}.")
        dialog.accept()
        _restart_app()

    test_btn.clicked.connect(handle_test)
    save_conn_btn.clicked.connect(handle_save_conn)
    conn_btn_row = QHBoxLayout()
    conn_btn_row.addWidget(test_btn)
    conn_btn_row.addWidget(save_conn_btn)

    config_layout = QVBoxLayout()
    config_layout.addLayout(config_form)
    config_layout.addWidget(test_result_label)
    config_layout.addLayout(conn_btn_row)
    config_box.setLayout(config_layout)

    # — Impresora de tickets —
    printer_box = QGroupBox("Impresora de tickets")
    printer_form = QFormLayout()
    printer_form.setSpacing(8)

    cached_printer, cached_copies = load_ticket_print_settings()

    printer_combo = QComboBox()
    printer_combo.addItem("Impresora predeterminada del sistema", "")
    for p in QPrinterInfo.availablePrinters():
        printer_combo.addItem(p.printerName(), p.printerName())

    # Seleccionar la impresora guardada
    idx = printer_combo.findData(cached_printer)
    printer_combo.setCurrentIndex(idx if idx >= 0 else 0)

    copies_spin = QSpinBox()
    copies_spin.setRange(1, 5)
    copies_spin.setValue(cached_copies)

    printer_form.addRow("Impresora:", printer_combo)
    printer_form.addRow("Copias:", copies_spin)

    save_printer_btn = QPushButton("Guardar preferencias de impresion")
    save_printer_btn.setObjectName("primaryButton")

    def handle_save_printer() -> None:
        selected = str(printer_combo.currentData() or "")
        copies = copies_spin.value()
        try:
            save_ticket_print_settings(selected, copies)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Error", f"No se pudo guardar:\n{exc}")
            return
        name = printer_combo.currentText()
        QMessageBox.information(dialog, "Guardado", f"Impresora '{name}' guardada para tickets.")

    save_printer_btn.clicked.connect(handle_save_printer)

    printer_layout = QVBoxLayout()
    printer_layout.addLayout(printer_form)
    printer_layout.addWidget(save_printer_btn)
    printer_box.setLayout(printer_layout)

    # — Meilisearch —
    meili_box = QGroupBox("Meilisearch (busqueda rapida)")
    meili_layout = QVBoxLayout()
    meili_status_label = QLabel("")
    meili_status_label.setWordWrap(True)

    try:
        from pos_uniformes.services.meilisearch_service import is_available
        if is_available():
            meili_status_label.setText("✓ Meilisearch conectado")
            meili_status_label.setStyleSheet("color: green;")
        else:
            meili_status_label.setText("✗ Meilisearch no disponible")
            meili_status_label.setStyleSheet("color: red;")
    except Exception:
        meili_status_label.setText("✗ Meilisearch no disponible")
        meili_status_label.setStyleSheet("color: red;")

    reindex_btn = QPushButton("Re-indexar catalogo")
    install_btn = QPushButton("Instalar / iniciar Meilisearch")
    meili_result_label = QLabel("")
    meili_result_label.setWordWrap(True)

    def handle_reindex() -> None:
        reindex_btn.setEnabled(False)
        install_btn.setEnabled(False)
        meili_result_label.setText("Indexando...")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        try:
            from pos_uniformes.services.meilisearch_service import configure_index, index_from_db, _get_client
            if _get_client() is None:
                meili_result_label.setText("✗ No se pudo conectar con Meilisearch en 127.0.0.1:7700")
                meili_result_label.setStyleSheet("color: red;")
                reindex_btn.setEnabled(True)
                install_btn.setEnabled(True)
                return
            configure_index()
            from pos_uniformes.database.connection import get_session
            with get_session() as session:
                count = index_from_db(session)
            meili_result_label.setText(f"✓ Indexados: {count} documentos")
            meili_result_label.setStyleSheet("color: green;")
            meili_status_label.setText("✓ Meilisearch conectado")
            meili_status_label.setStyleSheet("color: green;")
        except Exception as exc:
            meili_result_label.setText(f"✗ Error: {exc}")
            meili_result_label.setStyleSheet("color: red;")
        reindex_btn.setEnabled(True)
        install_btn.setEnabled(True)

    def handle_install() -> None:
        install_btn.setEnabled(False)
        reindex_btn.setEnabled(False)
        meili_result_label.setText("Verificando...")
        from PyQt6.QtWidgets import QApplication

        def on_progress(msg: str) -> None:
            meili_result_label.setText(msg)
            QApplication.processEvents()

        try:
            from pos_uniformes.services.meilisearch_service import ensure_installed
            result = ensure_installed(on_progress=on_progress)
            meili_result_label.setText(result)
            from pos_uniformes.services.meilisearch_service import is_available
            if is_available():
                meili_result_label.setStyleSheet("color: green;")
                meili_status_label.setText("✓ Meilisearch conectado")
                meili_status_label.setStyleSheet("color: green;")
                handle_reindex()
                return
            else:
                meili_result_label.setStyleSheet("color: orange;")
        except Exception as exc:
            meili_result_label.setText(f"✗ Error: {exc}")
            meili_result_label.setStyleSheet("color: red;")
        install_btn.setEnabled(True)
        reindex_btn.setEnabled(True)

    reindex_btn.clicked.connect(handle_reindex)
    install_btn.clicked.connect(handle_install)
    btn_row = QHBoxLayout()
    btn_row.addWidget(install_btn)
    btn_row.addWidget(reindex_btn)
    meili_layout.addWidget(meili_status_label)
    meili_layout.addLayout(btn_row)
    meili_layout.addWidget(meili_result_label)
    meili_box.setLayout(meili_layout)

    # — Cerrar —
    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)

    layout.addWidget(status_box)
    layout.addWidget(config_box)
    layout.addWidget(printer_box)
    layout.addWidget(meili_box)
    layout.addWidget(close_buttons)
    dialog.setLayout(layout)
    dialog.exec()
