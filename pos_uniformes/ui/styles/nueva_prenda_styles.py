"""Estética de la ventana «Nueva prenda» (tanda 3 del alta, 2026-11-13).

Los mismos tokens que la pestaña Inventario (`inventario_styles`): fondo
crema, tarjetas blancas de esquinas redondas, vino como único acento de
acción y los tonos de semáforo en el texto. A la izquierda se trabaja y a la
derecha va la ficha «Así queda» (como la ficha de Inventario).

Todos los nombres de objeto empiezan con `np` para no pisar otras pantallas.
La hoja se le pone a la raíz del diálogo.
"""

from __future__ import annotations

from pos_uniformes.ui.styles.inventario_styles import (
    BORDE,
    CAFE,
    CREMA,
    FUENTE,
    HOVER,
    LINEA,
    TARJETA,
    TARJETA_BORDE,
    TENUE,
    TEXTO,
    VINO,
    VINO_HOVER,
    VINO_OSCURO,
    VINO_SUAVE,
    sombra,
)

AMBAR = "#a35a00"
ROJO = "#b3261e"
VERDE = "#245241"
GRIS_POSIBLE = "#a39a90"

#: Medidas: cabe en 1366×768 con la barra de Windows.
ANCHO = 1240
ALTO = 700
ANCHO_FICHA = 420

__all__ = ["ALTO", "ANCHO", "ANCHO_FICHA", "AMBAR", "GRIS_POSIBLE", "ROJO", "VERDE", "build_nueva_prenda_stylesheet", "sombra"]


def build_nueva_prenda_stylesheet() -> str:
    return f"""
QDialog#npDialogo, QWidget#npRaiz {{
    background: {CREMA}; color: {TEXTO}; font-family: {FUENTE}; font-size: 14px;
}}
/* La ventana principal pinta TODO QWidget de crema: aquí las letras van sin fondo
   (si no, se ven recuadros crema sobre las tarjetas blancas) y con Segoe UI en Windows. */
QWidget {{ font-family: {FUENTE}; }}
QLabel {{ background: transparent; }}
QCheckBox {{ background: {TARJETA}; }}  /* las casillas van siempre sobre tarjeta blanca */
QStackedWidget#npPasos, QWidget#npPaso {{ background: transparent; }}
QScrollArea#npScroll, QWidget#npScrollVista {{ background: transparent; border: none; }}

/* ── Encabezado ── */
QLabel#npTitulo {{ font-size: 22px; font-weight: 800; color: {TEXTO}; }}
QLabel#npSub {{ font-size: 13px; color: {TENUE}; }}
QPushButton#npAtras {{
    background: transparent; color: {VINO}; border: none; padding: 0 4px; min-height: 30px;
    font-size: 13px; font-weight: 700; text-align: left;
}}
QPushButton#npAtras:hover {{ text-decoration: underline; }}
QLabel#npSeccion {{ font-size: 11px; font-weight: 800; color: {VINO}; letter-spacing: 1.5px; }}
QLabel#npEtiqueta {{ font-size: 11px; font-weight: 800; color: {TENUE}; letter-spacing: 1px; }}
QLabel#npNota {{ background: #faf6f0; color: {TENUE}; border-radius: 12px; padding: 10px 12px; font-size: 13px; }}
QLabel#npVacio {{
    background: #faf6f0; color: {TENUE}; border: 1.5px dashed #d8c6b0; border-radius: 14px;
    padding: 14px; font-size: 14px;
}}

/* ── Puerta: tarjetas grandes ── */
QPushButton#npTarjeta {{
    background: {TARJETA}; color: {TEXTO}; border: 2px solid {TARJETA}; border-radius: 20px;
    text-align: left; padding: 20px 22px;
}}
QPushButton#npTarjeta:hover {{ border: 2px solid {VINO}; }}
QPushButton#npTarjeta[pronto="si"]:hover {{ border: 2px solid {BORDE}; }}
QLabel#npTarjetaIcono {{ font-size: 30px; }}
QLabel#npTarjetaTitulo {{ font-size: 18px; font-weight: 800; color: {TEXTO}; }}
QLabel#npTarjetaTexto {{ font-size: 13px; color: {TENUE}; }}
QLabel#npTarjetaPie {{ font-size: 12px; font-weight: 700; color: {VINO}; }}
QLabel#npPronto {{
    background: #ece8e1; color: #6e675f; border: 1px solid {BORDE}; border-radius: 10px;
    padding: 2px 10px; font-size: 11px; font-weight: 800;
}}
QFrame#npUltima {{ background: {TARJETA}; border: 1px solid {TARJETA_BORDE}; border-radius: 14px; }}
QLabel#npUltimaNombre {{ font-size: 13px; font-weight: 700; color: {TEXTO}; }}
QLabel#npUltimaDetalle {{ font-size: 12px; color: {TENUE}; }}

/* ── Buscador grande sin bordes ── */
QFrame#npBuscador {{ background: {TARJETA}; border: 2px solid {TARJETA_BORDE}; border-radius: 20px; }}
QFrame#npBuscador[foco="si"] {{ border: 2px solid {VINO}; }}
QLabel#npBuscadorIcono {{ font-size: 18px; color: #b9a58f; }}
QLineEdit#npBuscar {{
    font-size: 18px; padding: 8px 4px; border: none; background: transparent; color: {TEXTO};
}}
QListWidget#npLista {{
    background: {TARJETA}; border: 1px solid {TARJETA_BORDE}; border-radius: 16px; padding: 6px;
    font-size: 15px; color: {TEXTO}; outline: 0;
}}
QListWidget#npLista::item {{ padding: 10px 12px; border-bottom: 1px solid {LINEA}; border-radius: 0; }}
QListWidget#npLista::item:hover {{ background: #faf6f0; }}
QListWidget#npLista::item:selected {{ background: {VINO_SUAVE}; color: {TEXTO}; }}

/* ── Ya tiene / Le falta ── */
QFrame#npTarjetaBlanca {{ background: {TARJETA}; border: 1px solid {TARJETA_BORDE}; border-radius: 18px; }}
QLabel#npTiene {{ font-size: 14px; color: {TEXTO}; }}
QLabel#npTieneNota {{ font-size: 12px; color: {TENUE}; }}
QPushButton#npFalta {{
    background: {TARJETA}; color: {TEXTO}; border: 1px solid {BORDE}; border-radius: 14px;
    padding: 10px 14px; text-align: left; font-size: 15px; font-weight: 700; min-height: 26px;
}}
QPushButton#npFalta:hover {{ border-color: {VINO}; background: {VINO_SUAVE}; color: {VINO}; }}
QComboBox#npCombo, QLineEdit#npCampo {{
    background: #faf6f0; color: {CAFE}; border: 1px solid {TARJETA_BORDE}; border-radius: 10px;
    padding: 0 10px; min-height: 34px; font-size: 14px;
}}
QComboBox#npCombo:focus, QLineEdit#npCampo:focus {{ border-color: {VINO}; }}
QComboBox#npCombo {{ padding-right: 26px; }}
QComboBox#npCombo::drop-down {{ border: none; width: 24px; }}
QPlainTextEdit#npTexto {{
    background: #faf6f0; color: {CAFE}; border: 1px solid {TARJETA_BORDE}; border-radius: 10px;
    padding: 6px 8px; font-size: 13px;
}}

/* ── Pantalla principal ── */
QLabel#npModelo {{ font-size: 13px; color: {TENUE}; }}
QPushButton#npCambiar {{
    background: transparent; color: {VINO}; border: none; padding: 0 2px; min-height: 26px;
    font-size: 13px; font-weight: 700; text-align: left;
}}
QPushButton#npCambiar:hover {{ text-decoration: underline; }}
QPushButton#npCambiar::menu-indicator {{ image: none; width: 0; }}
QMenu#npMenu {{
    background: {TARJETA}; border: 1px solid {TARJETA_BORDE}; border-radius: 12px; padding: 6px;
    font-size: 13px; color: {TEXTO};
}}
QMenu#npMenu::item {{ padding: 8px 20px 8px 12px; border-radius: 8px; }}
QMenu#npMenu::item:selected {{ background: #f6eee4; }}
QFrame#npTallas {{ background: {TARJETA}; border: 1px solid {TARJETA_BORDE}; border-radius: 18px; }}
QLabel#npColTitulo {{ font-size: 11px; font-weight: 800; color: {TENUE}; letter-spacing: 1px; }}
QFrame#npFila {{ background: transparent; border: none; border-bottom: 1px solid {LINEA}; border-radius: 0; }}
QCheckBox#npTalla {{ font-size: 15px; font-weight: 800; color: {TEXTO}; spacing: 8px; }}
QCheckBox#npTalla[posible="si"] {{ color: {GRIS_POSIBLE}; font-weight: 700; }}
QLineEdit#npPrecio {{
    background: #faf6f0; color: {TEXTO}; border: 1px solid {TARJETA_BORDE}; border-radius: 9px;
    padding: 0 8px; min-height: 28px; max-height: 28px; font-size: 14px; font-weight: 700;
}}
QLineEdit#npPrecio:focus {{ border-color: {VINO}; }}
QLineEdit#npPrecio[estado="error"] {{ border: 2px solid {ROJO}; background: #fdf0ee; }}
QLineEdit#npPrecio[estado="aviso"] {{ border: 1px solid #efd98f; }}
QLineEdit#npPrecio:disabled {{ color: {GRIS_POSIBLE}; background: transparent; border-color: transparent; }}
QLabel#npDonde {{ font-size: 12px; color: {TENUE}; }}
QLabel#npDonde[tono="warning"] {{ color: {AMBAR}; font-weight: 700; }}
QLabel#npDonde[tono="danger"] {{ color: {ROJO}; font-weight: 700; }}
QLabel#npDonde[posible="si"] {{ color: {GRIS_POSIBLE}; }}
QPushButton#npSugerencia {{
    background: #fbf0cf; color: #8a5a00; border: 1px solid #efd98f; border-radius: 10px;
    padding: 0 8px; min-height: 24px; max-height: 24px; font-size: 12px; font-weight: 800;
}}
QPushButton#npSugerencia:hover {{ background: #f6e4ae; }}
QLineEdit#npLlegan {{
    background: #faf6f0; color: {TEXTO}; border: 1px solid {TARJETA_BORDE}; border-radius: 9px;
    padding: 0 8px; min-height: 28px; max-height: 28px; font-size: 14px;
}}
QLineEdit#npLlegan:focus {{ border-color: {VINO}; }}
QLineEdit#npLlegan:disabled {{ background: transparent; border-color: transparent; }}
QToolButton#npPlegable {{
    background: transparent; color: {VINO}; border: none; padding: 4px 0; font-size: 14px; font-weight: 700;
}}
QFrame#npPanel {{ background: {TARJETA}; border: 1px solid {TARJETA_BORDE}; border-radius: 16px; }}
QCheckBox#npOtraEscuela {{ font-size: 13px; color: {TEXTO}; spacing: 8px; padding: 3px 0; }}
QPushButton#npEnlace {{
    background: transparent; color: {VINO}; border: none; padding: 0 2px; min-height: 26px;
    font-size: 13px; font-weight: 700; text-align: left;
}}
QPushButton#npEnlace:hover {{ text-decoration: underline; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #d8ccbd; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #c4b4a1; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QLabel#npFaltaNombre {{ font-size: 15px; font-weight: 800; color: {TEXTO}; }}
QLabel#npFaltaNota {{ font-size: 13px; color: {TENUE}; }}

/* ── Ficha «Así queda» ── */
QFrame#npFicha {{ background: {TARJETA}; border: 1px solid {TARJETA_BORDE}; border-radius: 20px; }}
QFrame#npFichaTotal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {VINO_OSCURO}, stop:1 #84304c);
    border: none; border-radius: 18px;
}}
QLabel#npFichaNombre {{ font-size: 19px; font-weight: 800; color: white; }}
QLabel#npFichaSub {{ font-size: 13px; color: #f0d6df; }}
QLabel#npFichaRango {{ font-size: 22px; font-weight: 900; color: white; }}
QLabel#npFichaLinea {{ font-size: 13px; color: {TEXTO}; }}
QLabel#npFichaLinea[tono="warning"] {{ color: {AMBAR}; font-weight: 700; }}
QLabel#npFichaLinea[tono="danger"] {{ color: {ROJO}; font-weight: 700; }}
QLabel#npFichaLinea[tono="muted"] {{ color: {TENUE}; }}

/* ── Barra de abajo ── */
QFrame#npBarra {{ background: transparent; border: none; border-top: 1px solid {LINEA}; }}
QLabel#npBloqueo {{ font-size: 13px; color: {AMBAR}; font-weight: 700; }}
QPushButton#npCancelar {{
    background: transparent; color: {TENUE}; border: none; padding: 0 8px; min-height: 44px;
    font-size: 14px; font-weight: 700;
}}
QPushButton#npCancelar:hover {{ color: {TEXTO}; text-decoration: underline; }}
QPushButton#npPrincipal {{
    background: {VINO}; color: white; border: none; border-radius: 14px;
    padding: 0 22px; min-height: 46px; font-size: 15px; font-weight: 800;
}}
QPushButton#npPrincipal:hover {{ background: {VINO_HOVER}; }}
QPushButton#npPrincipal:disabled {{ background: {HOVER}; color: #b4aba0; }}
QPushButton#npSecundario {{
    background: {TARJETA}; color: {CAFE}; border: 1px solid {BORDE}; border-radius: 14px;
    padding: 0 18px; min-height: 46px; font-size: 14px; font-weight: 700;
}}
QPushButton#npSecundario:hover {{ background: #faf6f0; border-color: #cbbcab; }}

/* ── Confirmar y Listo ── */
QLabel#npFrase {{ font-size: 20px; font-weight: 700; color: {TEXTO}; }}
QLabel#npListo {{ font-size: 30px; font-weight: 900; color: {VERDE}; }}
QLabel#npError {{ font-size: 14px; color: {ROJO}; font-weight: 700; }}
"""
