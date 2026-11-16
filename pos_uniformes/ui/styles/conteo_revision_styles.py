"""Estética de «Revisar conteo» (tanda 3, 2026-11-15).

La paleta del kiosko (terracota, como la Libreta y los clientes del kiosko,
`kiosko_clientes_styles`): fondo crema, tarjeta clara, terracota como único
acento de acción y los tonos de semáforo de siempre (`inventario_styles.TONOS`).
Sin el azul que traían las tarjetas viejas.

- Un solo botón lleno (Corregir inventario); «No usar este conteo» sin
  relleno y en rojo; lo de consultar en un menú «Consultar ▾».
- Los chips son píldoras con su tono; en 0, grises y sin relleno.
- La tabla sin rejilla, una línea por fila; el tono va en la letra.

Todos los nombres de objeto empiezan con `cr` para no pisar otras ventanas
(los diálogos hijos — historia, comparativo, hoja de pedido — traen los suyos).
"""

from __future__ import annotations

# ── Tokens del kiosko (kiosko_clientes_styles) ──────────────────────────────
FONDO = "#f4ede2"
TARJETA = "#fffdf8"
BORDE = "#ddd0c0"
BORDE_SUAVE = "#ebe1d3"
TEXTO = "#2c2a27"
TENUE = "#8a7a68"
TERRACOTA = "#a84f2d"
TERRACOTA_HOVER = "#bb613c"
TERRACOTA_OSCURO = "#73341c"
SELECCION = "#f4d4bb"
GRUPO = "#f3e6d6"
NOTA = "#f5ebe0"
ROJO = "#b3261e"
VERDE = "#1c7c54"
AMBAR = "#a35a00"
GRIS = "#9a8f84"
CAJITA_BORDE = "#c9b49b"
FUENTE = '"Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif'

#: Tonos de chip: (fondo, letra, borde). Semáforo de clientes_styles + el ajuste en terracota.
TONOS_CHIP = {
    "ajuste": ("#f9e6d8", TERRACOTA_OSCURO, "#e9c2a6"),
    "peligro": ("#f8dfd9", "#9a2f22", "#efc4ba"),
    "advertencia": ("#fbf0cf", "#8a5a00", "#efd98f"),
    "neutro": ("#ece8e1", "#6e675f", "#ddd4c8"),
    "cero": ("transparent", "#b4a898", "#e3d9cc"),
}

#: Letra de las celdas según su tono (`conteo_revision_pantalla_service`).
COLOR_DIF = {"faltan": ROJO, "sobran": VERDE, "cuadra": "#b4a898"}
COLOR_QUE = {"urgente": ROJO, "pedir": "#8a5a00", "gris": GRIS, "ojo": AMBAR}

# ── Medidas: 1280×700 como mucho, y que quepa a 1366×768 (100 % y 125 %) ────
ANCHO = 1280
ALTO = 700
#: Lo que suman la barra de título y los bordes de Windows (31 + 2×4 aprox.).
MARCO_ANCHO = 16
MARCO_ALTO = 40
MIN_ANCHO = 900
MIN_ALTO = 460
ALTO_FILA = 28


def medidas_ventana(disponible_ancho: int, disponible_alto: int) -> tuple[int, int, int, int]:
    """(ancho, alto, ancho mínimo, alto mínimo) por dentro para que, con su
    marco, quepa en el área libre (sin la barra de tareas). 1366×768 al 100 %
    deja 1366×728 → 1280×688; al 125 % deja 1093×574 → 1077×534."""
    ancho = max(1, min(ANCHO, int(disponible_ancho) - MARCO_ANCHO))
    alto = max(1, min(ALTO, int(disponible_alto) - MARCO_ALTO))
    return ancho, alto, min(MIN_ANCHO, ancho), min(MIN_ALTO, alto)


def _chips() -> str:
    reglas = []
    for tono, (fondo, letra, borde) in TONOS_CHIP.items():
        reglas.append(
            f'QPushButton#crChip[tono="{tono}"] {{ background: {fondo}; color: {letra}; border: 1px solid {borde}; }}\n'
            f'QPushButton#crChip[tono="{tono}"][activo="si"] {{ border: 2px solid {letra}; padding: 3px 13px; }}'
        )
    fondo, letra, borde = TONOS_CHIP["cero"]
    reglas.append(f"QPushButton#crChip:disabled {{ background: {fondo}; color: {letra}; border: 1px solid {borde}; }}")
    return "\n".join(reglas)


def build_conteo_revision_stylesheet() -> str:
    return f"""
QDialog#crDialogo {{ background: {FONDO}; }}
QWidget#crPagina {{ background: transparent; }}
/* Sin color aquí: cada etiqueta trae el suyo (una regla «QDialog QLabel» le ganaría a todas). */
QWidget#crPagina QLabel {{ background: transparent; font-family: {FUENTE}; }}

/* ── Encabezado ── */
QWidget#crPagina QLabel#crTitulo {{ font-size: 20px; font-weight: 800; color: {TEXTO}; }}
QWidget#crPagina QLabel#crSub {{ font-size: 13px; color: {TENUE}; }}
QWidget#crPagina QLabel#crAviso {{
    background: #fdf1d8; color: #7a4d00; border: 1px solid #f0d49a; border-radius: 10px;
    padding: 5px 12px; font-size: 13px; font-weight: 700;
}}
QWidget#crPagina QLabel#crRevisada {{
    background: #eef3ea; color: #2f5130; border: 1px solid #cfdcc8; border-radius: 10px;
    padding: 5px 12px; font-size: 13px; font-weight: 700;
}}
QWidget#crPagina QLabel#crResumen {{ font-size: 13px; color: {TENUE}; }}

/* ── Franja de chips ── */
QPushButton#crChip {{
    border-radius: 14px; padding: 4px 14px; font-family: {FUENTE}; font-size: 13px; font-weight: 800;
    min-height: 18px;
}}
{_chips()}
QWidget#crPagina QLabel#crNotaCajas {{ font-size: 12px; color: {GRIS}; }}
QPushButton#crOrden {{
    background: transparent; color: {TERRACOTA_OSCURO}; border: none; padding: 6px 8px;
    font-family: {FUENTE}; font-size: 13px; font-weight: 700;
}}
QPushButton#crOrden:hover {{ text-decoration: underline; }}

/* ── Tabla ── */
QTableWidget#crTabla {{
    background: {TARJETA}; color: {TEXTO}; border: 1px solid {BORDE_SUAVE}; border-radius: 14px;
    gridline-color: transparent; font-family: {FUENTE}; font-size: 14px;
    selection-background-color: {SELECCION}; selection-color: {TEXTO};
}}
QTableWidget#crTabla::item {{ border-bottom: 1px solid #f1e9de; padding: 0 6px; }}
QTableWidget#crTabla::item:selected {{ background: {SELECCION}; color: {TEXTO}; }}
QTableWidget#crTabla QHeaderView::section {{
    background: {TARJETA}; color: {TENUE}; border: none; border-bottom: 1px solid {BORDE};
    padding: 6px 6px; font-family: {FUENTE}; font-size: 11px; font-weight: 800;
}}
QTableWidget#crTabla QTableCornerButton::section {{ background: {TARJETA}; border: none; }}
QTableWidget#crTabla QLineEdit {{
    background: #ffffff; color: {TEXTO}; border: 2px solid {TERRACOTA}; border-radius: 8px;
    font-size: 14px; font-weight: 800; padding: 0 4px;
}}

QWidget#crPagina QLabel#crPorQue {{
    background: {NOTA}; color: {TEXTO}; border-radius: 10px; padding: 6px 12px; font-size: 13px;
}}
QWidget#crPagina QLabel#crPorQue[vacio="si"] {{ color: {TENUE}; background: transparent; }}

/* ── Botones ── */
QDialog#crDialogo QPushButton, QDialog#crDialogo QToolButton {{ font-family: {FUENTE}; }}
QPushButton#crPrimario {{
    background: {TERRACOTA}; color: #fffaf3; border: 1px solid {TERRACOTA}; border-radius: 14px;
    padding: 8px 22px; font-size: 15px; font-weight: 800;
}}
QPushButton#crPrimario:hover {{ background: {TERRACOTA_HOVER}; }}
QPushButton#crSecundario, QToolButton#crConsultar {{
    background: {TARJETA}; color: {TERRACOTA_OSCURO}; border: 1px solid #d9c3a5; border-radius: 14px;
    padding: 7px 16px; font-size: 14px; font-weight: 700;
}}
QPushButton#crSecundario:hover, QToolButton#crConsultar:hover {{ background: #fbf3e8; }}
QToolButton#crConsultar::menu-indicator {{ image: none; width: 0; }}
QPushButton#crNoUsar {{
    background: transparent; color: {ROJO}; border: 1px solid transparent; border-radius: 14px;
    padding: 7px 12px; font-size: 14px; font-weight: 700;
}}
QPushButton#crNoUsar:hover {{ background: #fbeae8; border-color: #e8c7c3; }}
QPushButton#crPrimario:disabled, QPushButton#crSecundario:disabled {{
    background: #f0ebe4; color: #b4aba0; border-color: #e6ddd2;
}}
QMenu#crMenu {{
    background: #ffffff; color: {TEXTO}; border: 1px solid {BORDE_SUAVE}; border-radius: 12px; padding: 6px;
    font-family: {FUENTE}; font-size: 14px;
}}
QMenu#crMenu::item {{ padding: 9px 22px 9px 12px; border-radius: 8px; }}
QMenu#crMenu::item:selected {{ background: #f6eee4; }}
QMenu#crMenu::separator {{ height: 1px; background: {BORDE_SUAVE}; margin: 4px 8px; }}

/* ── ✓ Listo ── */
QFrame#crListo {{ background: {TARJETA}; border: 1px solid {BORDE_SUAVE}; border-radius: 22px; }}
QWidget#crPagina QLabel#crListoIcono {{ font-size: 44px; color: {VERDE}; font-weight: 800; }}
QWidget#crPagina QLabel#crListoTitulo {{ font-size: 26px; font-weight: 800; color: {TEXTO}; }}
QWidget#crPagina QLabel#crListoTexto {{ font-size: 15px; color: {TEXTO}; }}
QWidget#crPagina QLabel#crListoQuedan {{ font-size: 13px; color: {TENUE}; }}
"""
