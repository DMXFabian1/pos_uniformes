"""Estética de la pestaña Inventario (tanda 3, «Cara nueva»).

Misma paleta que Clientes, Analítica y Venta rápida: fondo crema, tarjetas
blancas con sombra suave y esquinas redondas, vino como único acento de
acción y tonos de semáforo en el texto (nunca de fondo en la tabla).

La hoja se le pone a la raíz de la pestaña (`invRaiz`) con `setStyleSheet`,
así gana sobre el tema de la ventana principal solo aquí. Todos los nombres
de objeto empiezan con `inv` para no pisar otras pantallas.
"""

from __future__ import annotations

# ── Tokens (normas del POS: clientes_styles, quick_sale_view) ────────────
VINO = "#6b1f3a"
VINO_HOVER = "#84284a"
VINO_OSCURO = "#5a1830"
VINO_SUAVE = "#f4e7ec"
CREMA = "#f3efe8"
TARJETA = "#ffffff"  # tarjetas blancas como Venta rápida
TARJETA_BORDE = "#efe6db"
BORDE = "#ddd4c8"
TEXTO = "#1f1f1b"
TENUE = "#6d665e"
TENUE_CLARO = "#9a8a7c"
HOVER = "#f0ebe4"
LINEA = "#eee7dd"
CAFE = "#4a3728"

#: Tonos de semáforo: (fondo, letra, borde). Los de clientes_styles.CHIP_TONOS.
TONOS = {
    "danger": ("#f8dfd9", "#9a2f22", "#efc4ba"),
    "warning": ("#fbf0cf", "#8a5a00", "#efd98f"),
    "positive": ("#e5f2eb", "#245241", "#c5e0d2"),
    "muted": ("#ece8e1", "#6e675f", "#ddd4c8"),
    "neutral": ("#ece8e1", "#6e675f", "#ddd4c8"),
}

#: Color del número «Hay» en la tabla según su tono (solo letra).
COLOR_CIFRA = {
    "danger": "#b3261e",
    "warning": "#a35a00",
    "muted": "#8a8177",
}
#: Letra de la fila de una talla desactivada.
COLOR_FILA_APAGADA = "#9a8f84"

FUENTE = '"Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif'

#: Sombra de tarjeta (la de Venta rápida): blur, desplazamiento y alfa.
SOMBRA = (26, 4, 26)


def sombra(widget, *, fuerte: bool = False) -> None:
    """Sombra suave bajo la tarjeta: la hace ver moderna sin bordes duros."""
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect

    blur, dy, alfa = (34, 6, 60) if fuerte else SOMBRA
    efecto = QGraphicsDropShadowEffect(widget)
    efecto.setBlurRadius(blur)
    efecto.setOffset(0, dy)
    efecto.setColor(QColor(90, 40, 30, alfa))
    widget.setGraphicsEffect(efecto)


def _tonos_tarjeta() -> str:
    reglas = []
    for tono, (fondo, letra, borde) in TONOS.items():
        reglas.append(
            f'QLabel#invTarjetaValor[tono="{tono}"] {{ color: {letra}; }}\n'
            f'QFrame#invTarjeta[tono="{tono}"][prendida="si"] {{ background: {fondo}; border: 2px solid {letra}; }}\n'
            f'QLabel#invChip[tono="{tono}"] {{ background: {fondo}; color: {letra}; border: 1px solid {borde}; }}'
        )
    return "\n".join(reglas)


def build_inventario_stylesheet() -> str:
    return f"""
QWidget#invRaiz {{
    background: {CREMA};
    color: {TEXTO};
    font-family: {FUENTE};
    font-size: 14px;
}}
QWidget#invRaiz QLabel {{ background: transparent; }}
QScrollArea#invScroll, QWidget#invContenido {{ background: {CREMA}; border: none; }}

/* ── Encabezado ── */
QLabel#invTitulo {{ font-size: 22px; font-weight: 800; color: {TEXTO}; }}
QLabel#invSub {{ font-size: 13px; color: {TENUE}; }}
QToolButton#invNueva {{
    background: {VINO}; color: white; border: none; border-radius: 14px;
    padding: 0 18px; min-height: 44px; font-size: 15px; font-weight: 800;
}}
QToolButton#invNueva:hover {{ background: {VINO_HOVER}; }}
QToolButton#invNueva:disabled {{ background: {HOVER}; color: #b4aba0; }}
QToolButton#invMas, QToolButton#invFichaMas {{
    font-size: 20px; font-weight: 900; color: {TEXTO}; background: {TARJETA};
    border: 1px solid {TARJETA_BORDE}; border-radius: 20px; min-width: 40px; max-width: 40px;
    min-height: 40px; max-height: 40px; padding: 0;
}}
QToolButton#invMas::menu-indicator, QToolButton#invFichaMas::menu-indicator {{ image: none; width: 0; }}
QToolButton#invMas:pressed, QToolButton#invFichaMas:pressed {{ background: #f1e8dc; }}
QToolButton#invMas:disabled {{ color: #b4aba0; }}
QMenu#invMenu {{
    background: {TARJETA}; border: 1px solid {TARJETA_BORDE}; border-radius: 12px; padding: 6px;
    font-size: 14px; color: {TEXTO};
}}
QMenu#invMenu::item {{ padding: 9px 22px 9px 14px; border-radius: 8px; }}
QMenu#invMenu::item:selected {{ background: #f6eee4; color: {TEXTO}; }}
QMenu#invMenu::item:disabled {{ color: #b4aba0; }}
QMenu#invMenu::separator {{ height: 1px; background: {LINEA}; margin: 4px 8px; }}

/* ── Buscador grande sin bordes ── */
QFrame#invBuscador {{ background: {TARJETA}; border: 1px solid {TARJETA_BORDE}; border-radius: 20px; }}
QLabel#invBuscadorIcono {{ font-size: 24px; color: #b9a58f; }}
QLineEdit#invBuscar {{
    font-size: 18px; padding: 8px 4px; border: none; background: transparent; color: {TEXTO};
}}

/* ── Tarjetas que filtran ── */
QFrame#invTarjeta {{ background: {TARJETA}; border: 2px solid {TARJETA}; border-radius: 16px; }}
QFrame#invTarjeta:hover {{ border: 2px solid {BORDE}; }}
QLabel#invTarjetaTitulo {{ font-size: 11px; font-weight: 800; color: {TENUE}; letter-spacing: 1px; }}
QLabel#invTarjetaValor {{ font-size: 26px; font-weight: 800; color: {TEXTO}; }}
QLabel#invTarjetaNota {{ font-size: 12px; color: {TENUE}; }}
{_tonos_tarjeta()}

/* ── Filtros ── */
QToolButton#invFiltro, QToolButton#invMasFiltros {{
    background: {TARJETA}; color: {CAFE}; border: 1px solid {TARJETA_BORDE}; border-radius: 12px;
    padding: 0 12px; min-height: 34px; font-size: 13px; font-weight: 700;
}}
QToolButton#invFiltro::menu-indicator {{ subcontrol-position: right center; right: 6px; }}
QToolButton#invFiltro {{ padding-right: 22px; }}
QToolButton#invMasFiltros:checked {{ background: {VINO_SUAVE}; color: {VINO}; border-color: #e3c6d1; }}
QWidget#invChips {{ background: transparent; }}
QWidget#invRaiz QPushButton#chipButton {{
    background: {VINO_SUAVE}; color: {VINO}; border: 1px solid #e3c6d1; border-radius: 12px;
    padding: 4px 10px; font-size: 12px; font-weight: 700;
}}
QPushButton#invQuitar {{
    background: transparent; color: {VINO}; border: none; padding: 0 8px; min-height: 34px;
    font-size: 13px; font-weight: 700; text-decoration: underline;
}}
QFrame#invMasFiltrosPanel {{ background: {TARJETA}; border: 1px solid {TARJETA_BORDE}; border-radius: 14px; }}
QComboBox#invCombo, QLineEdit#invPrecioExacto {{
    background: #faf6f0; color: {CAFE}; border: 1px solid {TARJETA_BORDE}; border-radius: 10px;
    padding: 0 10px; min-height: 32px; font-size: 13px;
}}
QToolButton#invFiltroMas {{
    background: #faf6f0; color: {CAFE}; border: 1px solid {TARJETA_BORDE}; border-radius: 10px;
    padding: 0 22px 0 10px; min-height: 32px; font-size: 13px;
}}

/* ── Tabla ── */
QFrame#invTablaCard {{ background: {TARJETA}; border: 1px solid {TARJETA_BORDE}; border-radius: 20px; }}
QTableWidget#invTabla {{
    background: {TARJETA}; alternate-background-color: {TARJETA}; border: none;
    gridline-color: transparent; font-size: 13px; color: {TEXTO};
    selection-background-color: {VINO_SUAVE}; selection-color: {TEXTO};
}}
QTableWidget#invTabla::item {{ border-bottom: 1px solid {LINEA}; padding: 0 8px; }}
QTableWidget#invTabla::item:selected {{ background: {VINO_SUAVE}; color: {TEXTO}; }}
QTableWidget#invTabla QHeaderView::section {{
    background: {TARJETA}; color: {TENUE}; border: none; border-bottom: 1px solid {LINEA};
    padding: 8px 8px; font-size: 12px; font-weight: 700;
}}
QTableWidget#invTabla QHeaderView::section:hover {{ color: {VINO}; }}
QTableWidget#invTabla QTableCornerButton::section {{ background: {TARJETA}; border: none; }}
QLabel#invPaginas {{ font-size: 12px; color: {TENUE}; }}
QPushButton#invFlecha {{
    background: transparent; color: {VINO}; border: 1px solid {TARJETA_BORDE}; border-radius: 14px;
    min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px; padding: 0;
    font-size: 12px; font-weight: 800;
}}
QPushButton#invFlecha:disabled {{ color: #cfc5ba; }}
QPushButton#invSegmento {{
    background: transparent; color: {TENUE}; border: 1px solid {TARJETA_BORDE};
    padding: 0 12px; min-height: 28px; font-size: 12px; font-weight: 700;
}}
QPushButton#invSegmento[lado="izq"] {{ border-top-left-radius: 14px; border-bottom-left-radius: 14px; }}
QPushButton#invSegmento[lado="der"] {{ border-top-right-radius: 14px; border-bottom-right-radius: 14px; border-left: none; }}
QPushButton#invSegmento:checked {{ background: {VINO}; color: white; border-color: {VINO}; }}
QPushButton#invSegmento:disabled {{ color: #b4aba0; }}

/* ── Ficha derecha ── */
QFrame#invFicha {{ background: {TARJETA}; border: 1px solid {TARJETA_BORDE}; border-radius: 20px; }}
QStackedWidget#invFichaPaginas, QWidget#invFichaPagina {{ background: transparent; }}
QScrollArea#invFichaScroll, QWidget#invFichaVista {{ background: transparent; border: none; }}
QLabel#invSeccion {{ font-size: 11px; font-weight: 800; color: {VINO}; letter-spacing: 1.5px; }}
QLabel#invVacio {{
    background: #faf6f0; color: {TENUE}; border: 1.5px dashed #d8c6b0; border-radius: 14px;
    padding: 14px; font-size: 14px;
}}
QFrame#invAtender {{ background: transparent; border: none; border-bottom: 1px solid {LINEA}; border-radius: 0; }}
QFrame#invAtender:hover {{ background: #faf6f0; }}
QLabel#invAtenderTitulo {{ font-size: 13px; font-weight: 700; color: {TEXTO}; }}
QLabel#invAtenderMotivo {{ font-size: 12px; color: {TENUE}; }}
QLabel#invAtenderMotivo[tono="danger"] {{ color: #b3261e; font-weight: 700; }}
QLabel#invNota {{ background: #faf6f0; color: {TENUE}; border-radius: 12px; padding: 10px 12px; font-size: 13px; }}
QFrame#invFichaTotal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {VINO_OSCURO}, stop:1 #84304c);
    border: none; border-radius: 18px;
}}
QLabel#invFichaNombre {{ font-size: 19px; font-weight: 800; color: white; }}
QLabel#invFichaSub {{ font-size: 13px; color: #f0d6df; }}
QLabel#invFichaDatoTitulo {{ font-size: 11px; font-weight: 800; color: #e9c6d2; letter-spacing: 1.5px; }}
QLabel#invFichaDatoValor {{ font-size: 30px; font-weight: 900; color: white; }}
QLabel#invFichaDatoNota {{ font-size: 12px; color: #f0d6df; }}
QLabel#invChip {{ border-radius: 10px; padding: 3px 10px; font-size: 12px; font-weight: 700; }}
QLabel#invFichaLinea {{ font-size: 13px; color: {TEXTO}; }}
QLabel#invFichaEtiqueta {{ font-size: 11px; font-weight: 800; color: {TENUE}; letter-spacing: 1px; }}
QPushButton#invAccion {{
    background: {TARJETA}; color: {CAFE}; border: 1px solid {BORDE}; border-radius: 12px;
    min-height: 40px; padding: 0 10px; font-size: 13px; font-weight: 700; text-align: left;
}}
QPushButton#invAccion:hover {{ background: #faf6f0; border-color: #cbbcab; }}
QPushButton#invAccion:disabled {{ color: #b4aba0; background: #faf8f5; }}
"""
