"""Dialogo unificado de configuracion de Meilisearch."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def open_meilisearch_settings_dialog(parent: QWidget) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Meilisearch (busqueda rapida)")
    dialog.setMinimumWidth(520)
    layout = QVBoxLayout()
    layout.setSpacing(12)

    # — Diagnostico —
    diag_form = QFormLayout()
    diag_form.setSpacing(4)
    status_label = QLabel("")
    status_label.setWordWrap(True)
    docs_label = QLabel("")
    docs_label.setObjectName("subtleLine")
    binary_label = QLabel("")
    binary_label.setObjectName("subtleLine")
    task_label = QLabel("")
    task_label.setObjectName("subtleLine")

    def refresh_diagnostics() -> None:
        from pathlib import Path
        # Conexion + docs
        try:
            from pos_uniformes.services.meilisearch_service import is_available, _get_client
            if is_available():
                status_label.setText("✓ Conectado (127.0.0.1:7700)")
                status_label.setStyleSheet("color: green; font-weight: bold;")
                try:
                    client = _get_client()
                    stats = client.index("variantes").get_stats()
                    docs_label.setText(f"{stats.get('numberOfDocuments', '?')} documentos indexados")
                except Exception:
                    docs_label.setText("No se pudo leer stats del indice")
            else:
                status_label.setText("✗ No disponible")
                status_label.setStyleSheet("color: red; font-weight: bold;")
                docs_label.setText("—")
        except Exception:
            status_label.setText("✗ No disponible")
            status_label.setStyleSheet("color: red; font-weight: bold;")
            docs_label.setText("—")
        # Binario
        bin_path = Path(r"C:\Meilisearch\meilisearch.exe")
        binary_label.setText(
            f"✓ Binario: {bin_path}" if bin_path.exists() else "✗ Binario no encontrado"
        )
        # Tarea programada
        try:
            import subprocess
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", "MeilisearchPOS", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0 and "MeilisearchPOS" in result.stdout:
                task_label.setText("✓ Tarea programada 'MeilisearchPOS' activa")
                task_label.setStyleSheet("color: green;")
            else:
                task_label.setText("✗ Sin tarea programada (no arranca al encender PC)")
                task_label.setStyleSheet("color: orange;")
        except Exception:
            task_label.setText("? No se pudo verificar tarea programada")

    refresh_diagnostics()

    diag_form.addRow("Estado:", status_label)
    diag_form.addRow("Indice:", docs_label)
    diag_form.addRow("Binario:", binary_label)
    diag_form.addRow("Autostart:", task_label)

    # — Botones —
    install_btn = QPushButton("Instalar / iniciar")
    reindex_btn = QPushButton("Re-indexar catalogo")
    autostart_btn = QPushButton("Crear tarea programada")
    result_label = QLabel("")
    result_label.setWordWrap(True)

    def _set_busy(busy: bool) -> None:
        install_btn.setEnabled(not busy)
        reindex_btn.setEnabled(not busy)
        autostart_btn.setEnabled(not busy)

    def handle_install() -> None:
        _set_busy(True)
        result_label.setText("Verificando...")
        result_label.setStyleSheet("")
        QApplication.processEvents()
        try:
            from pos_uniformes.services.meilisearch_service import ensure_installed, is_available

            def on_progress(msg: str) -> None:
                result_label.setText(msg)
                QApplication.processEvents()

            result = ensure_installed(on_progress=on_progress)
            result_label.setText(result)
            if is_available():
                result_label.setStyleSheet("color: green;")
                refresh_diagnostics()
                handle_reindex()
                return
            else:
                result_label.setStyleSheet("color: orange;")
        except Exception as exc:
            result_label.setText(f"✗ Error: {exc}")
            result_label.setStyleSheet("color: red;")
        refresh_diagnostics()
        _set_busy(False)

    def handle_reindex() -> None:
        _set_busy(True)
        result_label.setText("Indexando...")
        result_label.setStyleSheet("")
        QApplication.processEvents()
        try:
            from pos_uniformes.services.meilisearch_service import configure_index, index_from_db, _get_client
            if _get_client() is None:
                result_label.setText("✗ No se pudo conectar con Meilisearch en 127.0.0.1:7700")
                result_label.setStyleSheet("color: red;")
                _set_busy(False)
                return
            configure_index()
            from pos_uniformes.database.connection import get_session
            with get_session() as session:
                count = index_from_db(session)
            result_label.setText(f"✓ Indexados: {count} documentos")
            result_label.setStyleSheet("color: green;")
        except Exception as exc:
            result_label.setText(f"✗ Error: {exc}")
            result_label.setStyleSheet("color: red;")
        refresh_diagnostics()
        _set_busy(False)

    def handle_create_scheduled_task() -> None:
        _set_busy(True)
        result_label.setText("Creando tarea programada...")
        result_label.setStyleSheet("")
        QApplication.processEvents()
        try:
            import subprocess
            bin_path = r"C:\Meilisearch\meilisearch.exe"
            args = "--no-analytics --db-path C:\\Meilisearch\\data --http-addr 127.0.0.1:7700"
            proc = subprocess.run(
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
            if proc.returncode == 0:
                result_label.setText("✓ Tarea 'MeilisearchPOS' creada — arrancara al iniciar sesion")
                result_label.setStyleSheet("color: green;")
            else:
                result_label.setText(f"✗ Error: {proc.stderr.strip() or proc.stdout.strip()}")
                result_label.setStyleSheet("color: red;")
        except Exception as exc:
            result_label.setText(f"✗ Error: {exc}")
            result_label.setStyleSheet("color: red;")
        refresh_diagnostics()
        _set_busy(False)

    install_btn.clicked.connect(handle_install)
    reindex_btn.clicked.connect(handle_reindex)
    autostart_btn.clicked.connect(handle_create_scheduled_task)

    btn_row = QHBoxLayout()
    btn_row.addWidget(install_btn)
    btn_row.addWidget(reindex_btn)
    btn_row.addWidget(autostart_btn)

    # — Cerrar —
    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)

    layout.addLayout(diag_form)
    layout.addLayout(btn_row)
    layout.addWidget(result_label)
    layout.addWidget(close_buttons)
    dialog.setLayout(layout)
    dialog.exec()
