"""Diálogo del calendario de conteos (POS "Mas" y admin del satélite).

Envoltorio delgado sobre `ConteoCalendarioPanel` (el contenido embebible que
también usa la página "Conteos" del kiosko).
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QWidget
from sqlalchemy.orm import Session

from pos_uniformes.ui.dialogs.conteo_calendario_panel import ConteoCalendarioPanel


class ConteoCalendarioDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calendario de conteos")
        self.setStyleSheet("QDialog { background: #faf6f0; }")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 12)
        self.panel = ConteoCalendarioPanel(self, session_factory=session_factory)
        layout.addWidget(self.panel)
        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        layout.addWidget(close_buttons)
        self.setLayout(layout)
        self.resize(820, 560)
