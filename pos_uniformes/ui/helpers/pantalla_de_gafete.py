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
    QHBoxLayout,
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
    pie: QLabel | None = None        # «Última venta: Fanny, 16:42», chiquito; solo si se pidió
    pie_fila: QWidget | None = None  # las fichas «Fanny 6 · Stayce 4 · …»


def construir_gate(
    *,
    emoji: str,
    titulo: str,
    ayuda: str,
    hoja: str,
    marcador: str = "Gafete...",
    al_escanear=None,
    con_pie: bool = False,
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

    # El emoji de la tarjeta sale SIEMPRE: en temporada el de la temporada
    # (🎃, 🎄…), fuera de ella el de la pantalla (📒, 📋). Se escondía cuando
    # había escena de fondo, y desde que las ocho temporadas tienen escena ya
    # no salía nunca; Daniel lo quiso de vuelta (2026-10-10).
    icono = QLabel("")
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

    saludo = QLabel("")
    saludo.setObjectName("gateTemporada")
    saludo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dentro.addWidget(saludo)

    _vestir(raiz, icono, etiqueta_titulo, etiqueta_ayuda, saludo, emoji)

    # Al cambiar la temporada desde el menú se repinta TODO lo de la tarjeta,
    # no solo el fondo. El color y el saludo se ponían al construirla, así que
    # el fondo cambiaba y el texto se quedaba con la temporada de antes
    # (2026-10-08).
    repintar_fondo = raiz.releer_temporada

    def releer() -> None:
        repintar_fondo()
        _vestir(raiz, icono, etiqueta_titulo, etiqueta_ayuda, saludo, emoji)

    raiz.releer_temporada = releer

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

    # Lo de hoy (operaciones por empleada y quién vendió al último), tenue y
    # al pie de la tarjeta: las empleadas lo pidieron (2026-11-07) y no debe
    # pelear con la escena. Oculto hasta que alguien le ponga texto.
    pie = None
    pie_fila = None
    if con_pie:
        pie_fila = QWidget()
        pie_fila.setObjectName("gatePieFila")
        fila_ly = QHBoxLayout(pie_fila)
        fila_ly.setContentsMargins(0, 0, 0, 0)
        fila_ly.setSpacing(8)
        fila_ly.addStretch(1)
        fila_ly.addStretch(1)
        pie_fila.setVisible(False)
        pie = QLabel("")
        pie.setObjectName("gatePie")
        pie.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pie.setVisible(False)
        dentro.addSpacing(10)
        dentro.addWidget(pie_fila)
        dentro.addWidget(pie)

    tarjeta.setLayout(dentro)
    fuera.addStretch()
    fuera.addWidget(tarjeta, 0, Qt.AlignmentFlag.AlignHCenter)
    fuera.addStretch()
    raiz.setLayout(fuera)
    return GateDeGafete(raiz=raiz, entrada=entrada, error=error, pie=pie, pie_fila=pie_fila)


def pintar_pie(gate: GateDeGafete, resumen) -> None:
    """Las fichas de hoy —una por empleada, la que más lleva resaltada— y
    abajo quién vendió al último. Con `resumen` vacío o None, no se ve nada."""
    if gate.pie is None or gate.pie_fila is None:
        return
    fila = gate.pie_fila.layout()
    # Se quitan las fichas de antes (los dos resortes se quedan).
    for i in reversed(range(fila.count())):
        item = fila.itemAt(i)
        w = item.widget()
        if w is not None:
            fila.removeWidget(w)
            w.setParent(None)        # fuera YA, no cuando el bucle de eventos llegue
            w.deleteLater()
    por_empleada = tuple(getattr(resumen, "por_empleada", ()) or ())
    if not por_empleada:
        gate.pie_fila.setVisible(False)
        gate.pie.setVisible(False)
        return
    tope = max(n for _n, n in por_empleada)
    for posicion, (nombre, n) in enumerate(por_empleada):
        ficha = QLabel(f"{nombre}  <b>{n}</b>")
        ficha.setObjectName("gateChip")
        ficha.setProperty("lider", "true" if n == tope and n > 0 else "false")
        ficha.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fila.insertWidget(fila.count() - 1, ficha)
    gate.pie_fila.setVisible(True)
    ultima = getattr(resumen, "ultima", None)
    if ultima:
        gate.pie.setText(f"Última venta: <b>{ultima[0]}</b>, {ultima[1]}")
        gate.pie.setVisible(True)
    else:
        gate.pie.setVisible(False)


def _temporada():
    try:
        from pos_uniformes.services.temporada_service import actual

        return actual()
    except Exception:  # noqa: BLE001 — un adorno no impide escanear un gafete
        return None


def _tema():
    """El tema de hoy (Maximoda fuera de temporada), o None si algo truena."""
    try:
        from pos_uniformes.services.temporada_service import tema_activo

        return tema_activo()
    except Exception:  # noqa: BLE001
        return None


def _vestir(raiz, icono: QLabel, titulo: QLabel, ayuda: QLabel,
            saludo: QLabel, emoji_fijo: str) -> None:
    """Deja la tarjeta como toca para la temporada de ahora mismo.

    Una sola función para construirla y para repintarla: si fueran dos, un día
    una pondría algo que la otra no quita y la tarjeta quedaría a medio vestir.
    """
    from pos_uniformes.ui.views.quick_sale_view import _MUTED, _TEXT

    temporada = _temporada()
    icono.setText(temporada.emoji if temporada else emoji_fijo)
    icono.setVisible(True)

    if temporada is None:
        titulo.setStyleSheet(f"color: {_TEXT}; background: transparent;")
        ayuda.setStyleSheet(f"color: {_MUTED}; background: transparent;")
        # Fuera de temporada la tarjeta saluda como Maximoda; con los adornos
        # apagados desde el menú, no saluda (apagar es apagar).
        tema = _tema()
        bienvenida = tema.saludo if tema is not None else ""
        if bienvenida:
            saludo.setText(bienvenida)
            saludo.setStyleSheet(
                f"color: {tema.color}; font-size: 13px; font-weight: 700;"
                " background: transparent;"
            )
        saludo.setVisible(bool(bienvenida))
        return

    _tenir(titulo, ayuda, temporada)
    saludo.setText(temporada.saludo)
    saludo.setStyleSheet(
        f"color: {temporada.color}; font-size: 13px; font-weight: 700;"
        " background: transparent;"
    )
    saludo.setVisible(True)


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
