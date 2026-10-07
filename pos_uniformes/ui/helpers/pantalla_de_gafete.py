"""La pantalla de «escanea tu gafete». Una sola, para las tres que había.

Venta rápida, Libreta y Conteos tenían cada una su copia, escrita a mano y
calcada de la primera —el comentario de Libreta decía literalmente «réplica
exacta»—. Compartían la hoja de estilos y nada más, así que todo lo que no
fuera color había que hacerlo tres veces.

Se notó el 07/10: la escena de Halloween y el texto en color de temporada
entraron solo en Venta rápida, y Daniel pidió lo mismo en las otras dos. En
vez de teñir tres copias, se quedó una sola pantalla y las tres la usan. Lo
que se agregue mañana les llega a las tres sin que nadie se acuerde.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass
class GateDeGafete:
    """Lo que el llamador necesita tocar después de construirla."""

    raiz: QWidget        # se mete en la página y se muestra/oculta
    entrada: QLineEdit   # donde cae el escaneo
    error: QLabel        # el renglón rojo, oculto hasta que haga falta


def construir_gate(
    *,
    emoji: str,
    titulo: str,
    ayuda: str,
    hoja: str,
    marcador: str = "Gafete...",
    al_escanear=None,
) -> GateDeGafete:
    """Arma la pantalla de gafete, ya adornada según la temporada.

    `hoja` es la hoja de estilos (`_GATE_STYLE`) y entra por parámetro para no
    invertir la dependencia: esto es un helper y no tiene por qué saber de la
    vista de venta rápida, que es donde viven los colores del kiosko.
    """
    from pos_uniformes.ui.helpers.escena_de_temporada import FondoDeTemporada

    raiz = FondoDeTemporada()
    raiz.setObjectName("gateRoot")
    raiz.setStyleSheet(hoja)
    fuera = QVBoxLayout()
    fuera.setContentsMargins(40, 40, 40, 40)

    tarjeta = QFrame()
    tarjeta.setObjectName("gateCard")
    dentro = QVBoxLayout()
    dentro.setContentsMargins(48, 40, 48, 40)
    dentro.setSpacing(12)
    dentro.setAlignment(Qt.AlignmentFlag.AlignCenter)

    temporada = _temporada()

    # Con la escena detrás ya hay una calabaza del tamaño de la pantalla: el
    # emoji suelto diría lo mismo dos veces.
    if not raiz.tiene_escena:
        icono = QLabel(temporada.emoji if temporada else emoji)
        icono.setObjectName("gateEmoji")
        icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dentro.addWidget(icono)

    etiqueta_titulo = QLabel(titulo)
    etiqueta_titulo.setObjectName("gateTitle")
    etiqueta_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dentro.addWidget(etiqueta_titulo)

    etiqueta_ayuda = QLabel(ayuda)
    etiqueta_ayuda.setObjectName("gateHint")
    etiqueta_ayuda.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dentro.addWidget(etiqueta_ayuda)

    if temporada is not None:
        _tenir(etiqueta_titulo, etiqueta_ayuda, temporada)
        saludo = QLabel(temporada.saludo)
        saludo.setObjectName("gateTemporada")
        saludo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        saludo.setStyleSheet(
            f"color: {temporada.color}; font-size: 13px; font-weight: 700;"
            " background: transparent;"
        )
        dentro.addWidget(saludo)

    dentro.addSpacing(8)

    entrada = QLineEdit()
    entrada.setObjectName("gateInput")
    entrada.setPlaceholderText(marcador)
    entrada.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if al_escanear is not None:
        entrada.returnPressed.connect(al_escanear)
    dentro.addWidget(entrada, 0, Qt.AlignmentFlag.AlignHCenter)

    error = QLabel("")
    error.setObjectName("gateError")
    error.setAlignment(Qt.AlignmentFlag.AlignCenter)
    error.setVisible(False)
    dentro.addWidget(error)

    tarjeta.setLayout(dentro)
    fuera.addStretch()
    fuera.addWidget(tarjeta, 0, Qt.AlignmentFlag.AlignHCenter)
    fuera.addStretch()
    raiz.setLayout(fuera)
    return GateDeGafete(raiz=raiz, entrada=entrada, error=error)


def _temporada():
    try:
        from pos_uniformes.services.temporada_service import actual

        return actual()
    except Exception:  # noqa: BLE001 — un adorno no impide escanear un gafete
        return None


def _tenir(titulo: QLabel, ayuda: QLabel, temporada) -> None:
    """El texto toma el color de la temporada. Solo en esta pantalla.

    En las de venta se leen precios y tallas ocho horas al día; ahí el color
    de un adorno no tiene nada que hacer (Daniel, 07/10).

    La ayuda NO va del mismo color que el título: tres renglones del mismo
    naranja se leen como un bloque y deja de verse cuál manda. Va a medio
    camino, que conserva el orden y de todos modos se nota.
    """
    from pos_uniformes.ui.views.quick_sale_view import _MUTED, mezclar_colores

    titulo.setStyleSheet(f"color: {temporada.color}; background: transparent;")
    ayuda.setStyleSheet(
        f"color: {mezclar_colores(_MUTED, temporada.color, 0.45)};"
        " background: transparent;"
    )
