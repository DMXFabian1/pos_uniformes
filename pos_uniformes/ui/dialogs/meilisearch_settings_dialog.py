"""Dialogo unificado de configuracion de Meilisearch."""

from __future__ import annotations

import platform
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


_IS_WINDOWS = platform.system() == "Windows"
_IS_MACOS = platform.system() == "Darwin"


def _status_pill(text: str, tone: str) -> str:
    colors = {
        "ok": "color: #1a7f37; background: #dafbe1;",
        "warn": "color: #7a4f01; background: #fff8c5;",
        "error": "color: #cf222e; background: #ffebe9;",
        "neutral": "color: #57606a; background: #eaeef2;",
    }
    style = colors.get(tone, colors["neutral"])
    return f'<span style="padding: 2px 8px; border-radius: 4px; font-weight: 600; {style}">{text}</span>'


def _row_html(label: str, value: str, tone: str = "neutral") -> str:
    return (
        f'<tr>'
        f'<td style="padding: 4px 12px 4px 0; color: #57606a; font-weight: 500;">{label}</td>'
        f'<td style="padding: 4px 0;">{_status_pill(value, tone)}</td>'
        f'</tr>'
    )


def open_meilisearch_settings_dialog(parent: QWidget) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Meilisearch (busqueda rapida)")
    dialog.setMinimumWidth(480)
    layout = QVBoxLayout()
    layout.setSpacing(16)

    status_label = QLabel("")
    status_label.setWordWrap(True)
    status_label.setTextFormat(status_label.textFormat().RichText)

    def _diagnostics() -> str:
        rows: list[str] = []

        connected = False
        doc_count = "?"
        try:
            from pos_uniformes.services.meilisearch_service import is_available, _get_client
            if is_available():
                connected = True
                try:
                    client = _get_client()
                    stats = client.index("variantes").get_stats()
                    doc_count = str(stats.get("numberOfDocuments", "?"))
                except Exception:
                    pass
        except Exception:
            pass

        if connected:
            rows.append(_row_html("Estado", f"Conectado — 127.0.0.1:7700", "ok"))
            rows.append(_row_html("Indice", f"{doc_count} documentos indexados", "ok"))
        else:
            rows.append(_row_html("Estado", "No disponible", "error"))
            rows.append(_row_html("Indice", "Sin conexion", "neutral"))

        if _IS_WINDOWS:
            bin_path = Path(r"C:\Meilisearch\meilisearch.exe")
            if bin_path.exists():
                rows.append(_row_html("Binario", "Instalado", "ok"))
            else:
                rows.append(_row_html("Binario", "No encontrado", "error"))

            try:
                import subprocess
                result = subprocess.run(
                    ["schtasks", "/Query", "/TN", "MeilisearchPOS", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode == 0 and "MeilisearchPOS" in result.stdout:
                    rows.append(_row_html("Autostart", "Tarea programada activa", "ok"))
                else:
                    rows.append(_row_html("Autostart", "Sin tarea programada", "warn"))
            except Exception:
                rows.append(_row_html("Autostart", "No se pudo verificar", "neutral"))
        elif _IS_MACOS:
            import shutil
            if shutil.which("meilisearch"):
                rows.append(_row_html("Binario", "Instalado (PATH)", "ok"))
            else:
                rows.append(_row_html("Binario", "No en PATH — instalar con: brew install meilisearch", "warn"))

        return f'<table style="font-size: 13px;">{"".join(rows)}</table>'

    def refresh_diagnostics() -> None:
        status_label.setText(_diagnostics())

    refresh_diagnostics()

    result_label = QLabel("")
    result_label.setWordWrap(True)
    result_label.setVisible(False)

    def _show_result(text: str, tone: str) -> None:
        colors = {"ok": "color: #1a7f37;", "error": "color: #cf222e;", "warn": "color: #7a4f01;", "neutral": ""}
        result_label.setText(text)
        result_label.setStyleSheet(colors.get(tone, ""))
        result_label.setVisible(True)

    install_btn = QPushButton("Instalar / iniciar")
    install_btn.setToolTip(
        "Descarga Meilisearch, lo instala y lo inicia en segundo plano"
        if _IS_WINDOWS
        else "Intenta conectar con Meilisearch en 127.0.0.1:7700"
    )
    reindex_btn = QPushButton("Re-indexar catalogo")
    reindex_btn.setToolTip("Reconstruye el indice de busqueda con todas las presentaciones activas de la base de datos")
    autostart_btn = QPushButton("Crear tarea programada")
    autostart_btn.setToolTip("Crea una tarea para que Meilisearch arranque automaticamente al iniciar sesion")

    if _IS_MACOS:
        install_btn.setVisible(False)
        autostart_btn.setVisible(False)

    def _set_busy(busy: bool) -> None:
        install_btn.setEnabled(not busy)
        reindex_btn.setEnabled(not busy)
        autostart_btn.setEnabled(not busy)

    def handle_install() -> None:
        _set_busy(True)
        _show_result("Verificando...", "neutral")
        QApplication.processEvents()
        try:
            from pos_uniformes.services.meilisearch_service import ensure_installed, is_available

            result = ensure_installed(on_progress=lambda msg: (_show_result(msg, "neutral"), QApplication.processEvents()))
            if is_available():
                _show_result(result, "ok")
                refresh_diagnostics()
                handle_reindex()
                return
            else:
                _show_result(result, "warn")
        except Exception as exc:
            _show_result(f"Error: {exc}", "error")
        refresh_diagnostics()
        _set_busy(False)

    def handle_reindex() -> None:
        _set_busy(True)
        _show_result("Indexando catalogo...", "neutral")
        QApplication.processEvents()
        try:
            from pos_uniformes.services.meilisearch_service import configure_index, index_from_db, _get_client
            if _get_client() is None:
                _show_result("No se pudo conectar con Meilisearch en 127.0.0.1:7700", "error")
                _set_busy(False)
                return
            configure_index()
            from pos_uniformes.database.connection import get_session
            with get_session() as session:
                count = index_from_db(session)
            _show_result(f"Listo — {count} documentos indexados", "ok")
        except Exception as exc:
            _show_result(f"Error: {exc}", "error")
        refresh_diagnostics()
        _set_busy(False)

    def handle_create_scheduled_task() -> None:
        _set_busy(True)
        _show_result("Creando tarea programada...", "neutral")
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
                _show_result("Tarea 'MeilisearchPOS' creada — arrancara al iniciar sesion", "ok")
            else:
                _show_result(f"Error: {proc.stderr.strip() or proc.stdout.strip()}", "error")
        except Exception as exc:
            _show_result(f"Error: {exc}", "error")
        refresh_diagnostics()
        _set_busy(False)

    install_btn.clicked.connect(handle_install)
    reindex_btn.clicked.connect(handle_reindex)
    autostart_btn.clicked.connect(handle_create_scheduled_task)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(8)
    if _IS_WINDOWS:
        btn_row.addWidget(install_btn)
    btn_row.addWidget(reindex_btn)
    if _IS_WINDOWS:
        btn_row.addWidget(autostart_btn)

    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
    close_buttons.rejected.connect(dialog.reject)

    layout.addWidget(status_label)
    layout.addLayout(btn_row)
    layout.addWidget(result_label)
    layout.addWidget(close_buttons)
    dialog.setLayout(layout)
    dialog.exec()
