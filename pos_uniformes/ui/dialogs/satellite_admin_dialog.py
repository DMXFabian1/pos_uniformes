"""Dialogo de administracion del satelite (Ctrl+Shift+A, PIN admin)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtPrintSupport import QPrinterInfo
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QScrollArea,
    QTabWidget,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
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


def _release_instance_lock() -> None:
    """Suelta el QLockFile de instancia única antes de reiniciar.

    En Windows os.execv arranca el proceso nuevo mientras el viejo muere: si
    el candado sigue tomado, la instancia nueva ve "Ya está abierto" y la app
    queda cerrada en vez de reiniciada.
    """
    app = QApplication.instance()
    lock = getattr(app, "_instance_lock", None)
    if lock is None:
        return
    try:
        lock.unlock()
    except Exception:  # noqa: BLE001 — reiniciar es mejor que quedarse trabado
        pass


def _restart_app() -> None:
    _release_instance_lock()
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

    # — Impresoras de etiquetas (una por tipo de rollo) —
    from pos_uniformes.services.label_printer_settings_cache_service import (
        load_label_printer_settings,
        save_label_printer_settings,
    )

    label_box = QGroupBox("Impresoras de etiquetas")
    label_form = QFormLayout()
    label_form.setSpacing(8)

    cached_normal, cached_label = load_label_printer_settings()

    def _build_label_combo(selected: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem("Autodetectar (Brother)", "")
        for p in QPrinterInfo.availablePrinters():
            combo.addItem(p.printerName(), p.printerName())
        found = combo.findData(selected)
        combo.setCurrentIndex(found if found >= 0 else 0)
        return combo

    normal_label_combo = _build_label_combo(cached_normal)
    label_label_combo = _build_label_combo(cached_label)

    label_form.addRow("Normal / Split / Continua:", normal_label_combo)
    label_form.addRow("Label (troquelada):", label_label_combo)

    save_label_btn = QPushButton("Guardar impresoras de etiquetas")
    save_label_btn.setObjectName("primaryButton")

    def handle_save_label_printers() -> None:
        normal_sel = str(normal_label_combo.currentData() or "")
        label_sel = str(label_label_combo.currentData() or "")
        try:
            save_label_printer_settings(normal_sel, label_sel)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Error", f"No se pudo guardar:\n{exc}")
            return
        QMessageBox.information(
            dialog,
            "Guardado",
            "Impresoras de etiquetas guardadas.\n"
            f"Normal/Split/Continua: {normal_label_combo.currentText()}\n"
            f"Label: {label_label_combo.currentText()}",
        )

    save_label_btn.clicked.connect(handle_save_label_printers)

    label_layout = QVBoxLayout()
    label_layout.addWidget(
        QLabel("Normal, Split y Continua salen a la primera; Label (rollo troquelado) a la segunda.")
    )
    label_layout.addLayout(label_form)
    label_layout.addWidget(save_label_btn)
    label_box.setLayout(label_layout)

    # — Meilisearch —
    meili_box = QGroupBox("Meilisearch (busqueda rapida)")
    meili_layout = QVBoxLayout()
    meili_layout.setSpacing(8)

    # Diagnostico
    meili_diag_form = QFormLayout()
    meili_diag_form.setSpacing(4)
    meili_status_label = QLabel("")
    meili_status_label.setWordWrap(True)
    meili_docs_label = QLabel("")
    meili_docs_label.setObjectName("subtleLine")
    meili_binary_label = QLabel("")
    meili_binary_label.setObjectName("subtleLine")
    meili_task_label = QLabel("")
    meili_task_label.setObjectName("subtleLine")

    def refresh_meili_diagnostics() -> None:
        import shutil
        from pathlib import Path
        # Conexion
        try:
            from pos_uniformes.services.meilisearch_service import is_available, _get_client
            if is_available():
                meili_status_label.setText("✓ Conectado (127.0.0.1:7700)")
                meili_status_label.setStyleSheet("color: green; font-weight: bold;")
                # Doc count
                try:
                    client = _get_client()
                    stats = client.index("variantes").get_stats()
                    n_docs = getattr(stats, "number_of_documents", None)
                    if n_docs is None:
                        n_docs = stats.get("numberOfDocuments", "?") if isinstance(stats, dict) else "?"
                    meili_docs_label.setText(f"{n_docs} documentos indexados")
                except Exception:
                    meili_docs_label.setText("No se pudo leer stats del indice")
            else:
                meili_status_label.setText("✗ No disponible")
                meili_status_label.setStyleSheet("color: red; font-weight: bold;")
                meili_docs_label.setText("—")
        except Exception:
            meili_status_label.setText("✗ No disponible")
            meili_status_label.setStyleSheet("color: red; font-weight: bold;")
            meili_docs_label.setText("—")
        # Binario — multiplataforma
        if sys.platform == "win32":
            bin_path = Path(r"C:\Meilisearch\meilisearch.exe")
            found = bin_path.exists()
            bin_display = str(bin_path)
        else:
            bin_which = shutil.which("meilisearch")
            found = bin_which is not None
            bin_display = bin_which or "meilisearch"
        meili_binary_label.setText(
            f"✓ Binario: {bin_display}" if found else "✗ Binario no encontrado"
        )
        meili_binary_label.setStyleSheet("color: green;" if found else "color: orange;")
        # Tarea programada / servicio
        if sys.platform == "win32":
            try:
                import subprocess
                result = subprocess.run(
                    ["schtasks", "/Query", "/TN", "MeilisearchPOS", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode == 0 and "MeilisearchPOS" in result.stdout:
                    meili_task_label.setText("✓ Tarea programada 'MeilisearchPOS' activa")
                    meili_task_label.setStyleSheet("color: green;")
                else:
                    meili_task_label.setText("✗ Sin tarea programada (no arranca al encender PC)")
                    meili_task_label.setStyleSheet("color: orange;")
            except Exception:
                meili_task_label.setText("? No se pudo verificar tarea programada")
        elif sys.platform == "darwin":
            try:
                import subprocess
                result = subprocess.run(
                    ["pgrep", "-x", "meilisearch"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    meili_task_label.setText("✓ Proceso meilisearch activo")
                    meili_task_label.setStyleSheet("color: green;")
                else:
                    meili_task_label.setText("— Proceso no detectado (puede estar en otra maquina)")
                    meili_task_label.setStyleSheet("color: orange;")
            except Exception:
                meili_task_label.setText("? No se pudo verificar proceso")
        else:
            meili_task_label.setText("— Verificacion no disponible en esta plataforma")

    refresh_meili_diagnostics()

    meili_diag_form.addRow("Estado:", meili_status_label)
    meili_diag_form.addRow("Indice:", meili_docs_label)
    meili_diag_form.addRow("Binario:", meili_binary_label)
    meili_diag_form.addRow("Autostart:", meili_task_label)

    # Botones de accion
    install_btn = QPushButton("Instalar / iniciar")
    reindex_btn = QPushButton("Re-indexar catalogo")
    autostart_btn = QPushButton("Crear tarea programada")
    meili_result_label = QLabel("")
    meili_result_label.setWordWrap(True)

    def _set_meili_busy(busy: bool) -> None:
        install_btn.setEnabled(not busy)
        reindex_btn.setEnabled(not busy)
        autostart_btn.setEnabled(not busy)

    def handle_reindex() -> None:
        _set_meili_busy(True)
        meili_result_label.setText("Verificando conexion a base de datos...")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        if not probe_database_host():
            meili_result_label.setText(
                "✗ No se puede re-indexar: la PC principal no responde.\n"
                "Enciende la PC principal y vuelve a intentar."
            )
            meili_result_label.setStyleSheet("color: red;")
            _set_meili_busy(False)
            return
        meili_result_label.setText("Indexando...")
        QApplication.processEvents()
        try:
            from pos_uniformes.services.meilisearch_service import configure_index, index_from_db, _get_client
            if _get_client() is None:
                meili_result_label.setText("✗ No se pudo conectar con Meilisearch en 127.0.0.1:7700")
                meili_result_label.setStyleSheet("color: red;")
                _set_meili_busy(False)
                return
            configure_index()
            from pos_uniformes.database.connection import get_session
            with get_session() as session:
                count = index_from_db(session)
            meili_result_label.setText(f"✓ Indexados: {count} documentos")
            meili_result_label.setStyleSheet("color: green;")
        except Exception as exc:
            meili_result_label.setText(f"✗ Error: {exc}")
            meili_result_label.setStyleSheet("color: red;")
        refresh_meili_diagnostics()
        _set_meili_busy(False)

    def handle_install() -> None:
        _set_meili_busy(True)
        meili_result_label.setText("Verificando...")
        from PyQt6.QtWidgets import QApplication

        def on_progress(msg: str) -> None:
            meili_result_label.setText(msg)
            QApplication.processEvents()

        try:
            from pos_uniformes.services.meilisearch_service import ensure_installed, is_available
            result = ensure_installed(on_progress=on_progress)
            meili_result_label.setText(result)
            if is_available():
                meili_result_label.setStyleSheet("color: green;")
                refresh_meili_diagnostics()
                handle_reindex()
                return
            else:
                meili_result_label.setStyleSheet("color: orange;")
        except Exception as exc:
            meili_result_label.setText(f"✗ Error: {exc}")
            meili_result_label.setStyleSheet("color: red;")
        refresh_meili_diagnostics()
        _set_meili_busy(False)

    def handle_create_scheduled_task() -> None:
        _set_meili_busy(True)
        meili_result_label.setText("Creando tarea programada...")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        try:
            import subprocess
            bin_path = r"C:\Meilisearch\meilisearch.exe"
            args = "--no-analytics --db-path C:\\Meilisearch\\data --http-addr 127.0.0.1:7700"
            result = subprocess.run(
                [
                    "schtasks", "/Create",
                    "/TN", "MeilisearchPOS",
                    "/TR", f'"{bin_path}" {args}',
                    "/SC", "ONLOGON",
                    "/RL", "HIGHEST",
                    "/F",
                ],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                meili_result_label.setText("✓ Tarea 'MeilisearchPOS' creada — arrancara al iniciar sesion")
                meili_result_label.setStyleSheet("color: green;")
            else:
                meili_result_label.setText(f"✗ Error: {result.stderr.strip() or result.stdout.strip()}")
                meili_result_label.setStyleSheet("color: red;")
        except Exception as exc:
            meili_result_label.setText(f"✗ Error: {exc}")
            meili_result_label.setStyleSheet("color: red;")
        refresh_meili_diagnostics()
        _set_meili_busy(False)

    install_btn.clicked.connect(handle_install)
    reindex_btn.clicked.connect(handle_reindex)
    autostart_btn.clicked.connect(handle_create_scheduled_task)

    btn_row = QHBoxLayout()
    btn_row.addWidget(install_btn)
    btn_row.addWidget(reindex_btn)
    btn_row.addWidget(autostart_btn)

    meili_layout.addLayout(meili_diag_form)
    meili_layout.addLayout(btn_row)
    meili_layout.addWidget(meili_result_label)
    meili_box.setLayout(meili_layout)

    # — Modo de impresión (ajuste por máquina) —
    from pos_uniformes.services.print_routing_cache_service import (
        MODO_LOCAL,
        MODO_SATELITE,
        load_print_routing,
        save_print_routing,
    )

    routing_box = QGroupBox("Modo de impresión de esta PC")
    routing_layout = QVBoxLayout()
    routing_help = QLabel(
        "Local: imprime en las impresoras conectadas a esta PC.\n"
        "Enviar al satélite: encola los tickets para que los imprima la PC satélite."
    )
    routing_help.setWordWrap(True)

    current_modo, current_origen = load_print_routing()
    radio_local = QRadioButton("Imprimir local (esta PC tiene las impresoras)")
    radio_sat = QRadioButton("Enviar al satélite")
    (radio_sat if current_modo == MODO_SATELITE else radio_local).setChecked(True)

    origen_form = QFormLayout()
    origen_edit = QLineEdit(current_origen)
    origen_edit.setPlaceholderText("principal / kiosko")
    origen_form.addRow("Nombre de esta PC (origen):", origen_edit)

    save_routing_btn = QPushButton("Guardar modo de impresión")
    save_routing_btn.setObjectName("primaryButton")

    def handle_save_routing() -> None:
        modo = MODO_SATELITE if radio_sat.isChecked() else MODO_LOCAL
        origen = origen_edit.text().strip() or "principal"
        try:
            save_print_routing(modo, origen)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Error", f"No se pudo guardar:\n{exc}")
            return
        etiqueta = "enviar al satélite" if modo == MODO_SATELITE else "imprimir local"
        QMessageBox.information(dialog, "Guardado", f"Esta PC ahora va a: {etiqueta}.")

    save_routing_btn.clicked.connect(handle_save_routing)

    routing_layout.addWidget(routing_help)
    routing_layout.addWidget(radio_local)
    routing_layout.addWidget(radio_sat)
    routing_layout.addLayout(origen_form)
    routing_layout.addWidget(save_routing_btn)
    routing_box.setLayout(routing_layout)

    # — Cerrar —
    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)

    # Rediseño en pestañas: antes eran 5 secciones apiladas (saturado en el
    # táctil, Meilisearch quedaba fuera). Ahora se agrupan en 3 pestañas
    # despejadas; cada una con su propio scroll por si la pantalla es chica.
    def _make_tab(*boxes: QWidget) -> QScrollArea:
        page_layout = QVBoxLayout()
        page_layout.setSpacing(16)
        page_layout.setContentsMargins(12, 12, 12, 12)
        for box in boxes:
            page_layout.addWidget(box)
        page_layout.addStretch()
        page = QWidget()
        page.setLayout(page_layout)
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setWidget(page)
        page_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        return page_scroll

    # — Conteos (calendario admin) —
    conteo_box = QGroupBox("Calendario de conteos")
    conteo_layout = QVBoxLayout()
    conteo_hint = QLabel(
        "Configura la frecuencia de conteo por escuela y revisa cuáles ya "
        "requieren conteo (lista y calendario)."
    )
    conteo_hint.setWordWrap(True)
    open_calendario_btn = QPushButton("Abrir calendario de conteos")
    open_calendario_btn.setObjectName("primaryButton")

    def _abrir_calendario_conteos() -> None:
        from pos_uniformes.ui.dialogs.conteo_calendario_dialog import ConteoCalendarioDialog

        ConteoCalendarioDialog(dialog).exec()

    open_calendario_btn.clicked.connect(_abrir_calendario_conteos)

    subir_conteo_btn = QPushButton("Subir conteo (registrar físico)")
    subir_conteo_btn.setObjectName("secondaryButton")

    def _abrir_subir_conteo() -> None:
        from pos_uniformes.ui.dialogs.conteo_subir_dialog import ConteoSubirDialog

        ConteoSubirDialog(dialog).exec()

    subir_conteo_btn.clicked.connect(_abrir_subir_conteo)

    conteo_layout.addWidget(conteo_hint)
    conteo_layout.addWidget(open_calendario_btn)
    conteo_layout.addWidget(subir_conteo_btn)
    conteo_layout.addStretch()
    conteo_box.setLayout(conteo_layout)

    tabs = QTabWidget()
    tabs.addTab(_make_tab(status_box, config_box), "🔌  Conexión")
    tabs.addTab(_make_tab(routing_box, printer_box, label_box), "🖨  Impresoras")
    tabs.addTab(_make_tab(meili_box), "🔍  Búsqueda")
    tabs.addTab(_make_tab(conteo_box), "📋  Conteos")

    outer = QVBoxLayout()
    outer.setContentsMargins(12, 12, 12, 12)
    outer.addWidget(tabs)
    outer.addWidget(close_buttons)
    dialog.setLayout(outer)

    # Tamaño acotado a la pantalla; cada pestaña scrollea si hace falta.
    screen = dialog.screen() or QApplication.primaryScreen()
    if screen is not None:
        avail = screen.availableGeometry()
        dialog.resize(max(560, int(avail.width() * 0.5)), int(avail.height() * 0.8))
        dialog.setMaximumHeight(avail.height())

    dialog.exec()
