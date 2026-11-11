"""Estética de los diálogos de clientes del kiosko: «Cliente» (buscar y
registrar) y «Proponer programa».

Va con la paleta del kiosko (crema y terracota) y con TODOS los colores
explícitos. Sin eso, en el modo oscuro del sistema (macOS o Windows) la lista
de resultados salía negra y los textos se perdían (Daniel, 2026-11-10). Los
nombres empiezan con `kc` para no pisar otros estilos del kiosko.
"""

from __future__ import annotations

FONDO = "#f4ede2"
TARJETA = "#fffdf8"
BORDE = "#ddd0c0"
TEXTO = "#2c2a27"
TENUE = "#8a7a68"
TERRACOTA = "#a84f2d"
TERRACOTA_OSCURO = "#73341c"
SELECCION = "#f4d4bb"


def build_kiosko_clientes_stylesheet() -> str:
    return f"""
        QDialog#kcDialog {{
            background: {FONDO};
            color: {TEXTO};
            font-size: 15px;
        }}
        QDialog#kcDialog QLabel {{ color: {TEXTO}; background: transparent; }}
        QDialog#kcDialog QLabel#kcTitulo {{ font-size: 22px; font-weight: 800; color: {TERRACOTA_OSCURO}; }}
        QDialog#kcDialog QLabel#kcSubtitulo {{ font-size: 13px; color: {TENUE}; }}
        QDialog#kcDialog QLabel#kcEstado {{ font-size: 13px; color: {TENUE}; padding: 0 4px; }}
        QDialog#kcDialog QLabel#kcSeccion {{
            font-size: 12px; font-weight: 800; color: {TERRACOTA}; letter-spacing: 0.5px;
        }}
        QDialog#kcDialog QLabel#kcCampo {{ font-size: 12px; font-weight: 700; color: {TENUE}; }}
        QDialog#kcDialog QLabel#kcVacio {{
            background: {TARJETA};
            border: 1px dashed {BORDE};
            border-radius: 16px;
            color: {TENUE};
            font-size: 14px;
            padding: 24px;
        }}
        QDialog#kcDialog QLabel#kcNota {{
            background: #fbf6ee;
            border: 1px solid #eadcc6;
            border-radius: 12px;
            color: {TENUE};
            font-size: 13px;
            padding: 8px 12px;
        }}
        QDialog#kcDialog QLabel#kcAviso {{ color: {TERRACOTA}; font-size: 13px; font-weight: 600; }}

        QDialog#kcDialog QFrame#kcTarjeta {{
            background: {TARJETA};
            border: 1px solid {BORDE};
            border-radius: 18px;
        }}

        QDialog#kcDialog QLineEdit, QDialog#kcDialog QPlainTextEdit {{
            background: {TARJETA};
            color: {TEXTO};
            border: 1px solid {BORDE};
            border-radius: 14px;
            padding: 10px 14px;
            font-size: 16px;
            selection-background-color: {SELECCION};
            selection-color: {TERRACOTA_OSCURO};
        }}
        QDialog#kcDialog QLineEdit:focus, QDialog#kcDialog QPlainTextEdit:focus {{
            border: 2px solid {TERRACOTA};
        }}

        QListWidget#kcResultados {{
            background: {TARJETA};
            color: {TEXTO};
            border: 1px solid {BORDE};
            border-radius: 16px;
            padding: 6px;
            font-size: 15px;
            outline: 0;
        }}
        /* Cada fila es una tarjeta propia (kcFila); el texto del renglón
           queda solo para buscar y leer, sin pintarse debajo. */
        QListWidget#kcResultados::item {{
            padding: 0; margin: 3px 2px; border: none;
            color: transparent; background: transparent;
        }}
        QListWidget#kcResultados::item:hover,
        QListWidget#kcResultados::item:selected {{ background: transparent; color: transparent; }}
        QFrame#kcFila {{
            background: {TARJETA};
            border: 1px solid #eadcc6;
            border-radius: 14px;
        }}
        QFrame#kcFila:hover {{ background: #fbf3e8; }}
        QFrame#kcFila[sel="true"] {{ background: #fbefe6; border: 2px solid {TERRACOTA}; }}
        QDialog#kcDialog QLabel#kcAvatar {{
            background: {SELECCION}; color: {TERRACOTA_OSCURO};
            border-radius: 21px; font-size: 15px; font-weight: 800;
        }}
        QDialog#kcDialog QLabel#kcFilaNombre {{ font-size: 16px; font-weight: 700; color: {TEXTO}; }}
        QDialog#kcDialog QLabel#kcFilaDetalle {{ font-size: 13px; color: {TENUE}; }}
        QDialog#kcDialog QLabel#kcFilaCheck {{ font-size: 18px; font-weight: 800; color: {TERRACOTA}; }}
        QDialog#kcDialog QLabel#kcPista {{ font-size: 12px; color: {TENUE}; padding-left: 4px; }}
        QDialog#kcDialog QLabel#kcPista[ok="true"] {{ color: #3d7a4a; font-weight: 700; }}

        QDialog#kcDialog QRadioButton#kcOpcion {{
            background: {TARJETA};
            color: {TEXTO};
            border: 1px solid {BORDE};
            border-radius: 14px;
            padding: 12px 14px;
            font-size: 15px;
            spacing: 10px;
        }}
        QDialog#kcDialog QRadioButton#kcOpcion:checked {{
            background: #fbefe6;
            border: 2px solid {TERRACOTA};
            color: {TERRACOTA_OSCURO};
        }}

        QDialog#kcDialog QPushButton {{
            border-radius: 14px;
            padding: 10px 18px;
            font-size: 15px;
            font-weight: 700;
            min-height: 22px;
        }}
        QDialog#kcDialog QPushButton#kcPrimario {{
            background: {TERRACOTA}; color: #f9f4ea; border: 1px solid {TERRACOTA};
        }}
        QDialog#kcDialog QPushButton#kcPrimario:hover {{ background: #bb613c; }}
        QDialog#kcDialog QPushButton#kcSecundario {{
            background: {TARJETA}; color: {TERRACOTA_OSCURO}; border: 1px solid #d9c3a5;
        }}
        QDialog#kcDialog QPushButton#kcSecundario:hover {{ background: #fbf3e8; }}
        QDialog#kcDialog QPushButton#kcFantasma {{
            background: transparent; color: {TEXTO}; border: 1px solid {BORDE};
        }}
        QDialog#kcDialog QPushButton#kcFantasma:hover {{ background: #ece3d6; }}
        QDialog#kcDialog QPushButton:disabled,
        QDialog#kcDialog QPushButton#kcPrimario:disabled,
        QDialog#kcDialog QPushButton#kcSecundario:disabled,
        QDialog#kcDialog QPushButton#kcFantasma:disabled {{
            background: #ece3d6; color: #b4a796; border: 1px solid #e2d7c8;
        }}
    """


def aplicar(dialogo) -> None:
    dialogo.setObjectName("kcDialog")
    dialogo.setStyleSheet(build_kiosko_clientes_stylesheet())


#: La franja «Programa» de Venta Rápida, con la misma paleta.
FRANJA_PROGRAMA = (
    f"QFrame#programaBar {{ background: {TARJETA}; border: 1px solid #eadcc6;"
    f" border-left: 4px solid {TERRACOTA}; border-radius: 12px; }}"
    f"QLabel {{ font-size: 14px; font-weight: 700; color: {TERRACOTA_OSCURO}; background: transparent; }}"
    f"QPushButton {{ font-size: 13px; font-weight: 700; padding: 6px 14px; border-radius: 10px;"
    f" border: 1px solid #d9c3a5; background: {TARJETA}; color: {TERRACOTA_OSCURO}; }}"
    f"QPushButton:hover {{ background: #fbf3e8; }}"
    f"QPushButton#kcFranjaClub {{ background: {TERRACOTA}; color: #f9f4ea; border: 1px solid {TERRACOTA}; }}"
    f"QPushButton#kcFranjaClub:hover {{ background: #bb613c; }}"
    f"QPushButton:disabled, QPushButton#kcFranjaClub:disabled"
    f" {{ background: #f3ece2; color: #b9aa98; border: 1px solid #e6dccd; }}"
)
