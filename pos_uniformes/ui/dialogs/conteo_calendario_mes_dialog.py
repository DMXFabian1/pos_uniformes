"""Diálogo del calendario visual de conteos por mes.

Envoltorio delgado sobre `ConteoCalendarioMesPanel` (el grid embebible que
también usa la página "Calendario" del kiosko).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QWidget
from sqlalchemy.orm import Session

from pos_uniformes.ui.dialogs.conteo_calendario_mes_panel import ConteoCalendarioMesPanel


class ConteoCalendarioMesDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
        hoy: date | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calendario de conteos")
        self.setStyleSheet("QDialog { background: #faf6f0; }")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 12)
        self.panel = ConteoCalendarioMesPanel(self, session_factory=session_factory, hoy=hoy)
        layout.addWidget(self.panel)
        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        layout.addWidget(close_buttons)
        self.setLayout(layout)
        self.resize(880, 660)
