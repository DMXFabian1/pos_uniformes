"""Dialogo unificado de configuracion de Meilisearch."""

from __future__ import annotations

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


def open_meilisearch_settings_dialog(parent: QWidget) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Meilisearch (busqueda rapida)")
    dialog.setMinimumWidth(460)
    layout = QVBoxLayout()
    layout.setSpacing(12)

    # — Estado —
    status_label = QLabel("")
    status_label.setWordWrap(True)

    try:
        from pos_uniformes.services.meilisearch_service import is_available
        if is_available():
            status_label.setText("✓ Meilisearch conectado")
            status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            status_label.setText("✗ Meilisearch no disponible")
            status_label.setStyleSheet("color: red; font-weight: bold;")
    except Exception:
        status_label.setText("✗ Meilisearch no disponible")
        status_label.setStyleSheet("color: red; font-weight: bold;")

    # — Botones —
    install_btn = QPushButton("Instalar / iniciar")
    reindex_btn = QPushButton("Re-indexar catalogo")
    result_label = QLabel("")
    result_label.setWordWrap(True)

    def _set_busy(busy: bool) -> None:
        install_btn.setEnabled(not busy)
        reindex_btn.setEnabled(not busy)

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
                status_label.setText("✓ Meilisearch conectado")
                status_label.setStyleSheet("color: green; font-weight: bold;")
                handle_reindex()
                return
            else:
                result_label.setStyleSheet("color: orange;")
        except Exception as exc:
            result_label.setText(f"✗ Error: {exc}")
            result_label.setStyleSheet("color: red;")
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
            status_label.setText("✓ Meilisearch conectado")
            status_label.setStyleSheet("color: green; font-weight: bold;")
        except Exception as exc:
            result_label.setText(f"✗ Error: {exc}")
            result_label.setStyleSheet("color: red;")
        _set_busy(False)

    install_btn.clicked.connect(handle_install)
    reindex_btn.clicked.connect(handle_reindex)

    btn_row = QHBoxLayout()
    btn_row.addWidget(install_btn)
    btn_row.addWidget(reindex_btn)

    # — Cerrar —
    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)

    layout.addWidget(status_label)
    layout.addLayout(btn_row)
    layout.addWidget(result_label)
    layout.addWidget(close_buttons)
    dialog.setLayout(layout)
    dialog.exec()
