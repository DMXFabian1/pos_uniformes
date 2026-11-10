"""Estética de las pantallas de clientes: lista, ficha, Fidelización y Programas.

Usa la misma paleta que el resto del POS (crema, tarjetas claras y vino).
Cada diálogo se la pone con `setStyleSheet`. Así se ven igual dentro de la
ventana principal, que ya trae el tema, y cuando se abren solos, como en las
pruebas y las capturas. Todos los nombres empiezan con `cli` o `prg`, para
no pisar estilos de otras pantallas.
"""

from __future__ import annotations

VINO = "#6b1f3a"
VINO_SUAVE = "#f4e7ec"
CREMA = "#f3efe8"
TARJETA = "#fdfcf9"
BORDE = "#ddd4c8"
TEXTO = "#1f1f1b"
TENUE = "#6d665e"

#: Iniciales del avatar: fondo y letra.
AVATAR = (VINO, "#f7f1e8")

#: Tonos de los chips: (fondo, letra, borde).
CHIP_TONOS = {
    "programa": ("#f6ead2", "#7a4b00", "#e8cf9c"),
    "tipo": ("#ece8e1", "#4a3728", "#ddd4c8"),
    "activo": ("#e5f2eb", "#245241", "#c5e0d2"),
    "inactivo": ("#ece8e1", "#6e675f", "#ddd4c8"),
    "archivado": ("#f8dfd9", "#9a2f22", "#efc4ba"),
    "pendiente": ("#fbf0cf", "#8a5a00", "#efd98f"),
}


def _chips() -> str:
    reglas = []
    for tono, (fondo, letra, borde) in CHIP_TONOS.items():
        reglas.append(
            f'QLabel#cliChip[tono="{tono}"] {{ background: {fondo}; color: {letra}; border: 1px solid {borde}; }}'
        )
    return "\n".join(reglas)


def build_clientes_stylesheet() -> str:
    return f"""
        QDialog#cliDialog, QWidget#cliFondo {{
            background: {CREMA};
            color: {TEXTO};
            font-family: "Avenir Next", "Helvetica Neue", sans-serif;
            font-size: 14px;
        }}

        /* El tema de la ventana principal le pone fondo a todo QWidget; aquí
           los textos van sobre su tarjeta. Los QLabel con nombre lo ganan. */
        QLabel {{ background: transparent; }}

        /* Encabezado de la ficha y de las ventanas */
        QFrame#cliHeaderCard {{
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 {TARJETA}, stop: 1 #f5ede5);
            border: 1px solid {BORDE};
            border-radius: 18px;
        }}
        QLabel#cliAvatar {{
            background: {AVATAR[0]};
            color: {AVATAR[1]};
            border-radius: 28px;
            font-size: 20px;
            font-weight: 700;
        }}
        QLabel#cliTitulo {{ font-size: 22px; font-weight: 700; color: {TEXTO}; }}
        QLabel#cliSubtitulo {{ font-size: 13px; color: {TENUE}; }}
        QLabel#cliChip {{
            border-radius: 10px;
            padding: 3px 10px;
            font-size: 12px;
            font-weight: 600;
        }}
        {_chips()}
        QLabel#cliContador {{
            background: {VINO_SUAVE};
            color: {VINO};
            border-radius: 12px;
            padding: 5px 12px;
            font-weight: 700;
        }}

        /* Tarjetas de datos */
        QFrame#cliCampo {{
            background: {TARJETA};
            border: 1px solid {BORDE};
            border-radius: 14px;
        }}
        QLabel#cliCampoEtiqueta {{
            color: {TENUE};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        QLabel#cliCampoValor {{ color: {TEXTO}; font-size: 15px; font-weight: 600; }}
        QLabel#cliSeccion {{
            color: {VINO};
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.5px;
            padding-top: 4px;
        }}
        QLabel#cliVacio {{
            background: {TARJETA};
            border: 1px dashed {BORDE};
            border-radius: 14px;
            color: {TENUE};
            padding: 18px;
        }}
        QLabel#cliNota {{
            background: #f5f0ea;
            border: 1px solid #e6ddd1;
            border-radius: 12px;
            color: {TENUE};
            padding: 8px 12px;
            font-size: 13px;
        }}

        /* Programa y propuesta (Fidelización) */
        QFrame#cliProgramaCard {{
            background: {TARJETA};
            border: 1px solid {BORDE};
            border-radius: 16px;
        }}
        QFrame#cliProgramaCard[activo="true"] {{
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #fbf3e2, stop: 1 #f6ead2);
            border: 1px solid #e8cf9c;
        }}
        QFrame#cliPropuestaCard {{
            background: {TARJETA};
            border: 1px solid {BORDE};
            border-radius: 16px;
        }}
        QFrame#cliPropuestaCard[pendiente="true"] {{
            background: #fffaf0;
            border: 1px solid #efd98f;
        }}
        QLabel#cliEstrella {{ color: #b7862b; font-size: 26px; }}
        QLabel#cliProgramaNombre {{ font-size: 18px; font-weight: 700; color: {TEXTO}; }}

        /* Filtros de la lista */
        QFrame#cliFiltros {{
            background: {TARJETA};
            border: 1px solid {BORDE};
            border-radius: 16px;
        }}
        QLabel#cliFiltroEtiqueta {{ color: {TENUE}; font-size: 12px; font-weight: 600; }}
        QLineEdit#cliBuscar {{
            background: {TARJETA};
            border: 1px solid {BORDE};
            border-radius: 14px;
            padding: 9px 14px;
            font-size: 15px;
        }}
        QLineEdit#cliBuscar:focus {{ border: 1px solid {VINO}; }}

        /* Tablas */
        QTableWidget#cliTabla {{
            background: {TARJETA};
            alternate-background-color: #f8f4ee;
            border: 1px solid {BORDE};
            border-radius: 14px;
            gridline-color: transparent;
            selection-background-color: {VINO_SUAVE};
            selection-color: {TEXTO};
            outline: 0;
        }}
        QTableWidget#cliTabla::item {{ padding: 4px 8px; border-bottom: 1px solid #eee7dd; }}
        QTableWidget#cliTabla QHeaderView::section {{
            background: #f5f0ea;
            color: {TENUE};
            border: none;
            border-bottom: 1px solid {BORDE};
            padding: 8px;
            font-size: 12px;
            font-weight: 700;
        }}

        /* Pestañas de la ficha */
        QTabWidget#fichaPestanas::pane {{
            border: 1px solid {BORDE};
            border-radius: 18px;
            background: {CREMA};
            top: -1px;
            padding: 12px;
        }}
        QTabWidget#fichaPestanas QTabBar::tab {{
            background: transparent;
            color: {TENUE};
            padding: 9px 16px;
            margin-right: 6px;
            border-radius: 12px;
            font-weight: 600;
        }}
        QTabWidget#fichaPestanas QTabBar::tab:selected {{ background: {VINO}; color: #f7f1e8; }}
        QTabWidget#fichaPestanas QTabBar::tab:hover:!selected {{ background: #f0ebe4; color: #4a3728; }}

        /* Botones (los mismos nombres que usa el resto del POS) */
        QDialog#cliDialog QPushButton {{
            border-radius: 12px;
            padding: 8px 16px;
            font-weight: 600;
            font-size: 13px;
            min-height: 20px;
        }}
        QDialog#cliDialog QPushButton#toolbarPrimaryButton {{
            background: {VINO}; color: #f7f1e8; border: 1px solid {VINO};
        }}
        QDialog#cliDialog QPushButton#toolbarPrimaryButton:hover {{ background: #84284a; }}
        QDialog#cliDialog QPushButton#toolbarSecondaryButton {{
            background: {TARJETA}; color: {VINO}; border: 1px solid #d9c3cb;
        }}
        QDialog#cliDialog QPushButton#toolbarSecondaryButton:hover {{ background: {VINO_SUAVE}; }}
        QDialog#cliDialog QPushButton#toolbarGhostButton {{
            background: transparent; color: #4a3728; border: 1px solid {BORDE};
        }}
        QDialog#cliDialog QPushButton#toolbarGhostButton:hover {{ background: #f0ebe4; }}
        QDialog#cliDialog QPushButton#cliPeligro {{
            background: transparent; color: #9a2f22; border: 1px solid #efc4ba;
        }}
        QDialog#cliDialog QPushButton#cliPeligro:hover {{ background: #fbeeea; }}
        QDialog#cliDialog QPushButton:disabled,
        QDialog#cliDialog QPushButton#toolbarPrimaryButton:disabled,
        QDialog#cliDialog QPushButton#toolbarSecondaryButton:disabled,
        QDialog#cliDialog QPushButton#toolbarGhostButton:disabled,
        QDialog#cliDialog QPushButton#cliPeligro:disabled {{
            background: #f0ebe4; color: #b4aba0; border: 1px solid #e6ddd1;
        }}
        QDialog#cliDialog QComboBox {{
            background: {TARJETA};
            border: 1px solid {BORDE};
            border-radius: 10px;
            padding: 6px 10px;
            min-width: 120px;
        }}
    """


def aplicar(widget) -> None:
    """Pone el estilo de clientes a un diálogo y lo marca como `cliDialog`."""
    widget.setObjectName("cliDialog")
    widget.setStyleSheet(build_clientes_stylesheet())


def iniciales(nombre: str) -> str:
    """«María López Hernández» → «ML». Sin nombre, «?»."""
    partes = [p for p in (nombre or "").replace(".", " ").split() if p[:1].isalpha()]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[1][0]).upper()
