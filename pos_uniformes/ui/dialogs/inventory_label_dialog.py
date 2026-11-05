"""Dialogo reutilizable para vista previa e impresion de etiquetas de inventario.

Rediseñado el 2026-11-05 (Daniel: «está bien pero le falta para verse mejor»):
el producto arriba como encabezado y no como una línea con barras; los tamaños
con su dibujito y su medida en vez de «Normal / Split / Label»; la etiqueta
mostrada como la calcomanía que va a salir, con su orilla en blanco; y el botón
diciendo cuántas va a imprimir. La lógica (render, copias, precio, navegación)
es la de antes.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QObject, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.ui.helpers.inventory_label_preview_helper import (
    NOMBRES_DE_MODO,
    build_error_inventory_label_preview_view,
    build_inventory_label_mode_hint,
    build_inventory_label_preview_view,
    build_inventory_label_print_confirmation,
    texto_boton_imprimir,
)
from pos_uniformes.ui.helpers.scanner_enter_guard import ScannerEnterGuard

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow
    from pos_uniformes.services.inventory_label_service import InventoryLabelContext
    from pos_uniformes.utils.label_generator import LabelRenderResult

#: Los tamaños, en el orden en que se ofrecen. La cuadrada va primero y es la
#: que sale marcada: se volvió la de todos los días (Daniel, 2026-11-05).
MODOS: tuple[str, ...] = ("dk1221", "standard", "split")
MODO_INICIAL = "dk1221"

#: Cuánto de orilla en blanco tiene la etiqueta física alrededor de lo
#: impreso, como fracción del lado corto de la imagen. La cuadrada mide 23 mm
#: y solo se imprimen 17: 3 mm por lado.
_ORILLA = {"dk1221": 3 / 17, "standard": 0.07, "split": 0.03, "continuous": 0.05}


def icono_de_modo(modo: str, lado: int = 44) -> QIcon:
    """Un dibujito de la etiqueta: su forma, el QR y los renglones de texto."""
    pm = QPixmap(lado, lado)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    papel, tinta = QColor("#ffffff"), QColor("#73341c")
    p.setPen(QPen(QColor("#c9b8a4"), 1.4))
    p.setBrush(papel)

    def qr(x: float, y: float, s: float) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tinta)
        c = s / 3
        for fx, fy in ((0, 0), (2, 0), (0, 2), (1, 1), (2, 2)):
            p.drawRect(QRectF(x + fx * c, y + fy * c, c - 0.6, c - 0.6))

    def renglon(x: float, y: float, w: float, h: float = 2.6) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tinta)
        p.drawRoundedRect(QRectF(x, y, w, h), 1.2, 1.2)

    if modo == "dk1221":
        m = lado * 0.16
        p.drawRoundedRect(QRectF(m, m, lado - 2 * m, lado - 2 * m), 5, 5)
        qr(m + 4, m + 4, lado * 0.26)
        renglon(m + 4 + lado * 0.32, m + 7, lado * 0.16, 5)
        renglon(m + 4, lado - m - 11, lado - 2 * m - 8)
        renglon(m + 4, lado - m - 6.5, (lado - 2 * m - 8) * 0.6)
    elif modo == "split":
        w = (lado - 6) / 4
        for k in range(4):
            x = 3 + k * w
            p.setPen(QPen(QColor("#c9b8a4"), 1.2))
            p.setBrush(papel)
            p.drawRoundedRect(QRectF(x + 0.6, lado * 0.2, w - 1.2, lado * 0.6), 2.5, 2.5)
            qr(x + 2, lado * 0.26, w - 4)
            renglon(x + 2, lado * 0.62, w - 4, 2.2)
    else:
        alto = lado * 0.42
        y = (lado - alto) / 2
        p.drawRoundedRect(QRectF(1.5, y, lado - 3, alto), 4, 4)
        renglon(5, y + 4.5, lado * 0.42, 3.4)
        renglon(5, y + alto - 7.5, lado * 0.26)
        qr(lado - 5 - alto * 0.62, y + alto * 0.19, alto * 0.62)
    p.end()
    return QIcon(pm)


class _AlCambiarDeTamano(QObject):
    """Avisa cuando el widget cambia de tamaño. La calcomanía se dibuja a la
    medida del hueco, y el hueco solo se conoce cuando la ventana ya se acomodó:
    dibujada antes, salía recortada."""

    def __init__(self, vigilado: QWidget, al_cambiar: Callable[[], None]) -> None:
        super().__init__(vigilado)
        self._al_cambiar = al_cambiar
        vigilado.installEventFilter(self)

    def eventFilter(self, _obj, evento) -> bool:  # noqa: N802 — nombre de Qt
        if evento.type() == QEvent.Type.Resize:
            self._al_cambiar()
        return False


def calcomania(etiqueta: QPixmap, modo: str, espacio: QSize) -> QPixmap:
    """La etiqueta como va a quedar en la mano: sobre su papel, con la orilla en
    blanco que la impresora no toca, esquinas redondeadas y una sombra suave."""
    ancho, alto = max(1, etiqueta.width()), max(1, etiqueta.height())
    orilla = _ORILLA.get(modo, 0.05) * min(ancho, alto)
    papel_w, papel_h = ancho + 2 * orilla, alto + 2 * orilla
    libre_w, libre_h = max(40, espacio.width() - 36), max(40, espacio.height() - 36)
    # No se agranda de más: una cuadrada de 23 mm a pantalla completa engaña.
    escala = min(libre_w / papel_w, libre_h / papel_h, 2.4 if modo == "dk1221" else 1.6)
    w, h = papel_w * escala, papel_h * escala
    lienzo = QPixmap(max(1, espacio.width()), max(1, espacio.height()))
    lienzo.fill(Qt.GlobalColor.transparent)
    p = QPainter(lienzo)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, escala < 1)
    x, y = (espacio.width() - w) / 2, (espacio.height() - h) / 2
    radio = min(w, h) * (0.09 if modo == "dk1221" else 0.07)
    p.setPen(Qt.PenStyle.NoPen)
    for k, alfa in enumerate((10, 14, 20)):                     # sombra en tres capas
        p.setBrush(QColor(70, 45, 20, alfa))
        p.drawRoundedRect(QRectF(x - 3 + k, y + 5 - k, w + 6 - 2 * k, h + 6 - 2 * k), radio + 3 - k, radio + 3 - k)
    p.setBrush(QColor("#ffffff"))
    p.setPen(QPen(QColor("#e2d6c5"), 1))
    p.drawRoundedRect(QRectF(x, y, w, h), radio, radio)
    p.drawPixmap(QRectF(x + orilla * escala, y + orilla * escala, ancho * escala, alto * escala), etiqueta, QRectF(0, 0, ancho, alto))
    p.end()
    return lienzo


def _build_inventory_label_dialog_styles() -> str:
    return """
        QWidget#inventoryLabelHeaderCard, QWidget#inventoryLabelControlsCard, QWidget#inventoryLabelPreviewCard {
            background: #fdfaf6;
            border: 1px solid #ddd0c0;
            border-radius: 18px;
        }
        QLabel#inventoryLabelNombre {
            color: #2c2a27;
            font-size: 22px;
            font-weight: 800;
            background: transparent;
            border: none;
        }
        QLabel#inventoryMetaCard {
            color: #7a6d60;
            font-size: 14px;
            font-weight: 600;
            background: transparent;
            border: none;
            padding: 0;
        }
        QLabel#inventoryLabelPosicion {
            color: #a84f2d;
            font-size: 13px;
            font-weight: 800;
            background: #f7e3d8;
            border: none;
            border-radius: 10px;
            padding: 4px 10px;
        }
        QLabel#inventoryLabelSectionTitle {
            color: #7b2d14;
            font-size: 13px;
            font-weight: 800;
            background: transparent;
            border: none;
            padding: 0;
        }
        QLabel#inventoryLabelModeHint {
            color: #7a6d60;
            font-size: 12px;
            background: transparent;
            border: none;
            padding: 0;
        }
        /* El fondo donde se ve la calcomanía: un tono más oscuro que la tarjeta,
           para que el papel blanco de la etiqueta resalte. */
        QLabel#inventoryLabelPreviewImage {
            background: #efe6d8;
            border: none;
            border-radius: 16px;
            color: #7a6d60;
            font-size: 14px;
            padding: 0;
        }
        QLabel#inventoryLabelSummaryCard {
            background: transparent;
            border: none;
            color: #2c2a27;
            padding: 0;
            font-size: 16px;
            font-weight: 800;
        }
        QPushButton#inventoryLabelNavButton {
            min-width: 124px;
            min-height: 50px;
            border-radius: 14px;
            padding: 6px 14px;
            font-size: 15px;
            font-weight: 800;
        }
        /* Tamaño de etiqueta: dibujito + nombre + medida. Marcado = tinte + borde grueso */
        QPushButton#inventoryLabelModo {
            background: #ffffff;
            color: #2c2a27;
            border: 2px solid #ddd0c0;
            border-radius: 14px;
            min-height: 56px;
            padding: 4px 14px;
            font-size: 15px;
            font-weight: 700;
            text-align: left;
        }
        QPushButton#inventoryLabelModo:checked {
            background: #f7e3d8;
            color: #73341c;
            border: 3px solid #a84f2d;
        }
        QPushButton#inventoryLabelToggle {
            background: #ffffff;
            color: #2c2a27;
            border: 2px solid #ddd0c0;
            border-radius: 14px;
            min-height: 52px;
            padding: 0 18px;
            font-size: 15px;
            font-weight: 700;
        }
        QPushButton#inventoryLabelToggle:checked {
            background: #f7e3d8;
            color: #73341c;
            border: 3px solid #a84f2d;
        }
        QPushButton#inventoryLabelStep {
            background: #ffffff;
            color: #2c2a27;
            border: 2px solid #ddd0c0;
            border-radius: 14px;
            min-width: 64px;
            max-width: 64px;
            min-height: 54px;
            font-size: 24px;
            font-weight: 800;
        }
        QPushButton#inventoryLabelStep:pressed { background: #f1e6d6; }
        QPushButton#inventoryLabelChip {
            background: #ffffff;
            color: #73341c;
            border: 1.5px solid #ddd0c0;
            border-radius: 12px;
            min-height: 40px;
            font-size: 15px;
            font-weight: 800;
        }
        QPushButton#inventoryLabelChip:checked {
            background: #f7e3d8;
            border: 2px solid #a84f2d;
        }
        QLabel#inventoryLabelCopies {
            font-size: 30px;
            font-weight: 800;
            color: #73341c;
            min-width: 70px;
            background: transparent;
            border: none;
        }
        QPushButton#primaryButton, QPushButton#secondaryButton {
            min-height: 58px;
            font-size: 17px;
            font-weight: 800;
            border-radius: 14px;
            padding: 0 26px;
        }
        /* Colores explícitos (a prueba de modo oscuro y de hojas de estilo ajenas) */
        QPushButton#primaryButton { background: #a84f2d; color: #ffffff; border: none; min-width: 250px; }
        QPushButton#primaryButton:pressed { background: #8a4326; }
        QPushButton#primaryButton:disabled { background: #c9a996; color: #f4ede2; }
        QPushButton#secondaryButton, QPushButton#inventoryLabelNavButton {
            background: #f8f2e9; color: #73341c; border: 1px solid #ddd0c0;
        }
        QPushButton#secondaryButton:pressed, QPushButton#inventoryLabelNavButton:pressed {
            background: #e8dbc7;
        }
        QPushButton#inventoryLabelNavButton:disabled { color: #b3a794; background: #efe9de; }
    """


def build_inventory_label_dialog(
    window: "MainWindow",
    *,
    initial_context: "InventoryLabelContext",
    variant_ids: list[int],
    current_index: int,
    load_context: Callable[[int], "InventoryLabelContext"],
    render_label: Callable[[str, int, bool | None], "LabelRenderResult"],
    print_label: Callable[[Path, int, str, QDialog | None, str], bool],
) -> None:
    dialog, layout = window._create_modal_dialog(
        "Imprimir etiqueta",
        None,
        width=980,
    )
    dialog.resize(1000, 730)
    dialog.setStyleSheet(_build_inventory_label_dialog_styles())
    ScannerEnterGuard(dialog)
    layout.setSpacing(12)

    # ── Encabezado: de qué prenda es la etiqueta ────────────────────────
    header_card = QWidget()
    header_card.setObjectName("inventoryLabelHeaderCard")
    header_row = QHBoxLayout(header_card)
    header_row.setContentsMargins(18, 12, 12, 12)
    header_row.setSpacing(10)
    titulos = QVBoxLayout()
    titulos.setSpacing(2)
    nombre_label = QLabel("")
    nombre_label.setObjectName("inventoryLabelNombre")
    nombre_label.setWordWrap(True)
    header = QLabel("")
    header.setWordWrap(True)
    header.setObjectName("inventoryMetaCard")
    titulos.addWidget(nombre_label)
    titulos.addWidget(header)
    header_row.addLayout(titulos, 1)
    posicion_label = QLabel("")
    posicion_label.setObjectName("inventoryLabelPosicion")
    header_row.addWidget(posicion_label, 0, Qt.AlignmentFlag.AlignVCenter)
    previous_button = QPushButton("Anterior")
    previous_button.setObjectName("inventoryLabelNavButton")
    previous_button.setAutoDefault(False)
    next_button = QPushButton("Siguiente")
    next_button.setObjectName("inventoryLabelNavButton")
    next_button.setAutoDefault(False)
    header_row.addWidget(previous_button)
    header_row.addWidget(next_button)
    layout.addWidget(header_card)

    estado: dict[str, object] = {"mode": MODO_INICIAL, "copies": 1, "price": True}

    cuerpo = QHBoxLayout()
    cuerpo.setSpacing(12)

    # ── Izquierda: qué etiqueta y cuántas ───────────────────────────────
    controls_card = QWidget()
    controls_card.setObjectName("inventoryLabelControlsCard")
    controls_card.setFixedWidth(340)
    controls_layout = QVBoxLayout(controls_card)
    controls_layout.setContentsMargins(16, 14, 16, 14)
    controls_layout.setSpacing(8)

    modo_title = QLabel("TAMAÑO DE LA ETIQUETA")
    modo_title.setObjectName("inventoryLabelSectionTitle")
    controls_layout.addWidget(modo_title)
    mode_buttons: dict[str, QPushButton] = {}
    for valor in MODOS:
        titulo, medida = NOMBRES_DE_MODO[valor]
        btn = QPushButton(f"{titulo}\n{medida}")
        btn.setObjectName("inventoryLabelModo")
        btn.setIcon(icono_de_modo(valor))
        btn.setIconSize(QSize(44, 44))
        btn.setCheckable(True)
        btn.setAutoDefault(False)
        mode_buttons[valor] = btn
        controls_layout.addWidget(btn)
    mode_buttons[MODO_INICIAL].setChecked(True)

    controls_layout.addSpacing(6)
    copias_title = QLabel("¿CUÁNTAS?")
    copias_title.setObjectName("inventoryLabelSectionTitle")
    controls_layout.addWidget(copias_title)
    copies_row = QHBoxLayout()
    copies_row.setSpacing(8)
    copies_minus = QPushButton("−")
    copies_minus.setObjectName("inventoryLabelStep")
    copies_minus.setAutoDefault(False)
    copies_label = QLabel("1")
    copies_label.setObjectName("inventoryLabelCopies")
    copies_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    copies_plus = QPushButton("+")
    copies_plus.setObjectName("inventoryLabelStep")
    copies_plus.setAutoDefault(False)
    # Mantener presionado cuenta solo (sin 20 taps)
    for btn in (copies_minus, copies_plus):
        btn.setAutoRepeat(True)
        btn.setAutoRepeatDelay(350)
        btn.setAutoRepeatInterval(70)
    copies_row.addWidget(copies_minus)
    copies_row.addWidget(copies_label, 1)
    copies_row.addWidget(copies_plus)
    controls_layout.addLayout(copies_row)
    # Chips rápidos: un toque fija la cantidad
    chips_row = QHBoxLayout()
    chips_row.setSpacing(6)
    chip_buttons: dict[int, QPushButton] = {}
    for n in (5, 10, 20, 50):
        chip = QPushButton(str(n))
        chip.setObjectName("inventoryLabelChip")
        chip.setAutoDefault(False)
        chip.setCheckable(True)
        chip_buttons[n] = chip
        chips_row.addWidget(chip, 1)
    controls_layout.addLayout(chips_row)

    controls_layout.addSpacing(6)
    precio_title = QLabel("PRECIO EN LA ETIQUETA")
    precio_title.setObjectName("inventoryLabelSectionTitle")
    price_button = QPushButton("✓  💲 Mostrar precio")
    price_button.setObjectName("inventoryLabelToggle")
    price_button.setCheckable(True)
    price_button.setChecked(True)
    price_button.setAutoDefault(False)
    price_button.setToolTip("Incluir o quitar el precio de venta en la etiqueta impresa")
    controls_layout.addWidget(precio_title)
    controls_layout.addWidget(price_button)
    controls_layout.addStretch(1)
    cuerpo.addWidget(controls_card)

    # ── Derecha: la etiqueta, como va a quedar ──────────────────────────
    preview_card = QWidget()
    preview_card.setObjectName("inventoryLabelPreviewCard")
    preview_card_layout = QVBoxLayout(preview_card)
    preview_card_layout.setContentsMargins(16, 14, 16, 14)
    preview_card_layout.setSpacing(10)
    preview_section_title = QLabel("ASÍ VA A SALIR")
    preview_section_title.setObjectName("inventoryLabelSectionTitle")
    preview_card_layout.addWidget(preview_section_title)
    preview_label = QLabel("Generando vista previa...")
    preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    preview_label.setMinimumSize(440, 300)
    # Ignored: el tamaño lo manda la ventana, no la imagen que se le ponga.
    preview_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
    preview_label.setObjectName("inventoryLabelPreviewImage")
    preview_card_layout.addWidget(preview_label, 1)
    mode_hint = QLabel(build_inventory_label_mode_hint(MODO_INICIAL))
    mode_hint.setWordWrap(True)
    mode_hint.setObjectName("inventoryLabelModeHint")
    preview_card_layout.addWidget(mode_hint)
    cuerpo.addWidget(preview_card, 1)
    layout.addLayout(cuerpo, 1)

    # ── Abajo: qué va a pasar, y el botón que lo hace ───────────────────
    buttons_layout = QHBoxLayout()
    buttons_layout.setSpacing(10)
    summary_label = QLabel("")
    summary_label.setWordWrap(True)
    summary_label.setObjectName("inventoryLabelSummaryCard")
    buttons_layout.addWidget(summary_label, 1)
    close_button = QPushButton("Cerrar")
    close_button.setObjectName("secondaryButton")
    close_button.setAutoDefault(False)
    close_button.setDefault(False)
    print_button = QPushButton(texto_boton_imprimir(None))
    print_button.setObjectName("primaryButton")
    print_button.setDefault(True)
    print_button.setAutoDefault(True)
    buttons_layout.addWidget(close_button)
    buttons_layout.addWidget(print_button)
    preview_state: dict[str, object] = {"result": None, "pixmap": None}
    dialog_state: dict[str, object] = {
        "variant_ids": [int(variant_id) for variant_id in variant_ids],
        "current_index": max(0, min(int(current_index), max(0, len(variant_ids) - 1))),
        "context": initial_context,
    }

    def apply_context(context: "InventoryLabelContext") -> None:
        nombre_label.setText(str(context.product_name))
        color = str(context.color or "").strip()
        partes = [f"Talla {context.talla}" if str(context.talla or "").strip() else ""]
        if color and color.casefold() not in {"sin color", "none"}:
            partes.append(color)
        partes.append(str(context.sku))
        header.setText("   ·   ".join(parte for parte in partes if parte))
        # En un uniforme el precio no va en la etiqueta (cambia; para eso está
        # el QR), así que la opción ni aparece. Antes salía marcada y no hacía
        # nada (Daniel, 2026-11-05). En la ropa normal vuelve, prendida.
        lleva_precio = bool(getattr(context, "precio_por_defecto", True))
        estado["price"] = lleva_precio
        price_button.blockSignals(True)
        price_button.setChecked(lleva_precio)
        price_button.blockSignals(False)
        price_button.setText("✓  💲 Mostrar precio" if lleva_precio else "💲 Mostrar precio")
        price_button.setVisible(lleva_precio)
        precio_title.setVisible(lleva_precio)

    def refresh_navigation_buttons() -> None:
        current_position = int(dialog_state["current_index"])
        total = len(dialog_state["variant_ids"])
        previous_button.setEnabled(current_position > 0)
        next_button.setEnabled(current_position < total - 1)
        # Con una sola presentación no hay a dónde ir: los botones sobran.
        varias = total > 1
        posicion_label.setText(f"{current_position + 1} de {total}")
        for sobra in (posicion_label, previous_button, next_button):
            sobra.setVisible(varias)

    def pintar_calcomania() -> None:
        pixmap, result = preview_state.get("pixmap"), preview_state.get("result")
        if pixmap is None or result is None:
            return
        preview_label.setText("")
        preview_label.setPixmap(calcomania(pixmap, result.mode, preview_label.contentsRect().size()))

    _AlCambiarDeTamano(preview_label, pintar_calcomania)

    def refresh_preview() -> None:
        mode_hint.setText(build_inventory_label_mode_hint(str(estado["mode"])))
        show_price = bool(estado["price"])
        try:
            result = render_label(
                str(estado["mode"]),
                int(estado["copies"]),
                show_price,
            )
        except Exception as exc:  # noqa: BLE001
            preview_state["result"] = None
            preview_state["pixmap"] = None
            preview_view = build_error_inventory_label_preview_view(str(exc))
            preview_label.clear()
            preview_label.setText(preview_view.preview_text)
            summary_label.setText(preview_view.summary_text)
            print_button.setText(texto_boton_imprimir(None))
            print_button.setEnabled(preview_view.print_enabled)
            return

        preview_state["result"] = result
        preview_state["pixmap"] = None
        preview_view = build_inventory_label_preview_view(result)
        pixmap = QPixmap(str(result.image_path))
        if pixmap.isNull():
            preview_label.clear()
            preview_label.setText(preview_view.preview_text)
        else:
            preview_state["pixmap"] = pixmap
            pintar_calcomania()
        summary_label.setText(preview_view.summary_text)
        print_button.setText(texto_boton_imprimir(result))
        print_button.setEnabled(preview_view.print_enabled)

    def navigate_variant(step: int) -> None:
        target_index = int(dialog_state["current_index"]) + step
        variant_id_list = dialog_state["variant_ids"]
        if target_index < 0 or target_index >= len(variant_id_list):
            return
        try:
            context = load_context(int(variant_id_list[target_index]))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Presentacion no disponible", str(exc))
            return
        dialog_state["current_index"] = target_index
        dialog_state["context"] = context
        apply_context(context)
        refresh_navigation_buttons()
        refresh_preview()

    def handle_print() -> None:
        result = preview_state.get("result")
        if result is None:
            refresh_preview()
            result = preview_state.get("result")
        if result is None:
            return
        context = dialog_state["context"]
        try:
            printed = print_label(
                result.image_path,
                int(result.effective_copies),
                str(context.sku),
                dialog,
                result.mode,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Impresion fallida", str(exc))
            return
        if printed:
            QMessageBox.information(
                dialog,
                "Etiqueta enviada",
                build_inventory_label_print_confirmation(sku=str(context.sku), result=result),
            )

    def set_mode(valor: str) -> None:
        estado["mode"] = valor
        for v, btn in mode_buttons.items():
            btn.setChecked(v == valor)
        refresh_preview()

    # La vista previa se regenera 250 ms después del último cambio de
    # cantidad: mantener + presionado no re-renderiza la etiqueta 20 veces.
    from PyQt6.QtCore import QTimer

    preview_timer = QTimer(dialog)
    preview_timer.setSingleShot(True)
    preview_timer.setInterval(250)
    preview_timer.timeout.connect(refresh_preview)

    def _sync_chips() -> None:
        for n, chip in chip_buttons.items():
            chip.setChecked(int(estado["copies"]) == n)

    def set_copies_abs(valor: int) -> None:
        estado["copies"] = max(1, min(500, int(valor)))
        copies_label.setText(str(estado["copies"]))
        _sync_chips()
        preview_timer.start()

    def set_copies(delta: int) -> None:
        set_copies_abs(int(estado["copies"]) + delta)

    def toggle_price() -> None:
        estado["price"] = price_button.isChecked()
        price_button.setText("✓  💲 Mostrar precio" if estado["price"] else "💲 Mostrar precio")
        refresh_preview()

    for valor, btn in mode_buttons.items():
        btn.clicked.connect(lambda _=False, v=valor: set_mode(v))
    copies_minus.clicked.connect(lambda: set_copies(-1))
    copies_plus.clicked.connect(lambda: set_copies(1))
    for n, chip in chip_buttons.items():
        chip.clicked.connect(lambda _=False, v=n: set_copies_abs(v))
    price_button.clicked.connect(toggle_price)
    previous_button.clicked.connect(lambda: navigate_variant(-1))
    next_button.clicked.connect(lambda: navigate_variant(1))
    print_button.clicked.connect(handle_print)
    close_button.clicked.connect(dialog.reject)
    layout.addLayout(buttons_layout)
    apply_context(initial_context)
    refresh_navigation_buttons()
    refresh_preview()
    dialog.exec()
