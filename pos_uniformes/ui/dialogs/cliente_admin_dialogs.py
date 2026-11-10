"""Diálogos de la ficha de cliente para el ADMIN (E1-C1).

La ficha solo pide identidad y tipo: nombre, teléfono, tipo del catálogo y
notas. No hay nivel ni descuento (D5): los programas de fidelización llegan
en E4 y se asignan aparte.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QDialog, QFormLayout, QLabel, QLineEdit, QTextEdit, QWidget

from pos_uniformes.ui.dialogs.settings_prompt_dialogs import _build_prompt_buttons, _create_settings_prompt_dialog

NOTA_SIN_BENEFICIOS = "El tipo es solo una etiqueta: no da nivel ni descuento. Los programas se asignan aparte."
MOTIVO_MINIMO = 5


def prompt_cliente_ficha(
    parent: QWidget,
    *,
    title: str,
    helper_text: str,
    tipos: list[tuple[str, str]],
    current_values: dict[str, str] | None = None,
) -> dict[str, str] | None:
    """Devuelve {nombre, telefono, tipo_clave, notas} o None si se cancela.

    `tipos` es la lista (clave, nombre) del catálogo activo, en su orden."""
    dialog, layout = _create_settings_prompt_dialog(parent, title, helper_text, width=520)
    form = QFormLayout()
    nombre = QLineEdit()
    nombre.setPlaceholderText("Nombre completo del cliente")
    telefono = QLineEdit()
    telefono.setPlaceholderText("Telefono a 10 digitos")
    tipo = QComboBox()
    for clave, etiqueta in tipos:
        tipo.addItem(etiqueta, clave)
    notas = QTextEdit()
    notas.setMinimumHeight(80)
    notas.setPlaceholderText("Notas internas")

    actuales = current_values or {}
    nombre.setText(actuales.get("nombre", ""))
    telefono.setText(actuales.get("telefono", ""))
    notas.setPlainText(actuales.get("notas", ""))
    indice = tipo.findData(actuales.get("tipo_clave") or "GENERAL")
    tipo.setCurrentIndex(indice if indice >= 0 else 0)

    form.addRow("Nombre", nombre)
    form.addRow("Telefono", telefono)
    form.addRow("Tipo", tipo)
    nota = QLabel(NOTA_SIN_BENEFICIOS)
    nota.setObjectName("subtleLine")
    nota.setWordWrap(True)
    form.addRow("", nota)
    form.addRow("Notas", notas)
    layout.addLayout(form)
    layout.addWidget(_build_prompt_buttons(dialog))
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return {
        "nombre": nombre.text().strip(),
        "telefono": telefono.text().strip(),
        "tipo_clave": str(tipo.currentData() or "GENERAL"),
        "notas": notas.toPlainText().strip(),
    }


def prompt_motivo(parent: QWidget, *, title: str, helper_text: str) -> str | None:
    """Pide un motivo de al menos 5 caracteres. None si se cancela."""
    dialog, layout = _create_settings_prompt_dialog(parent, title, helper_text, width=460)
    form = QFormLayout()
    motivo = QLineEdit()
    motivo.setPlaceholderText(f"Motivo (minimo {MOTIVO_MINIMO} caracteres)")
    form.addRow("Motivo", motivo)
    layout.addLayout(form)
    botones = _build_prompt_buttons(dialog)
    aceptar = botones.button(botones.StandardButton.Ok)
    aceptar.setEnabled(False)
    motivo.textChanged.connect(lambda texto: aceptar.setEnabled(len(texto.strip()) >= MOTIVO_MINIMO))
    layout.addWidget(botones)
    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    texto = motivo.text().strip()
    return texto if len(texto) >= MOTIVO_MINIMO else None
