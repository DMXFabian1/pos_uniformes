"""Diálogo de búsqueda rápida de producto para el flujo de caja (Ctrl+S)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.database.connection import get_session
from pos_uniformes.services.catalog_snapshot_service import load_catalog_snapshot_rows
from pos_uniformes.ui.helpers.flow_layout import FlowLayout
from pos_uniformes.ui.helpers.quote_guided_catalog_helper import (
    build_guided_catalog_view,
)

if TYPE_CHECKING:
    from pos_uniformes.ui.helpers.quote_guided_catalog_helper import (
        GuidedCatalogOption,
        GuidedCatalogProductCard,
        GuidedCatalogVariantOption,
        GuidedCatalogView,
    )

_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


class _DoubleClickButton(QPushButton):
    double_clicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


@dataclass
class _FlowState:
    mode: str = "school"
    level: str = ""
    school: str = ""
    gender: str = "TODOS"
    profile: str = "TODOS"
    bucket: str = "TODOS"
    piece: str = ""
    product_key: str = ""
    sku: str = ""

    def reset(self, mode_key: str) -> None:
        self.mode = "basics" if mode_key == "basics" else "school"
        self.level = ""
        self.school = ""
        self.gender = "TODOS"
        self.profile = "TODOS"
        self.bucket = "BASICO" if self.mode == "basics" else "TODOS"
        self.piece = ""
        self.product_key = ""
        self.sku = ""


class QuickProductSearchDialog(QDialog):
    sku_selected = pyqtSignal(str, int)

    def __init__(self, parent=None, catalog_rows: list[dict] | None = None, school_links: list[dict] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Buscar producto")
        self.setModal(True)
        self.setMinimumSize(680, 700)
        self.resize(750, 850)

        self._state = _FlowState()
        self._catalog_rows = catalog_rows or []
        self._school_links = school_links
        if not self._catalog_rows:
            self._load_catalog()

        self._mode_buttons: dict[str, QPushButton] = {}
        self._level_buttons: dict[str, QPushButton] = {}
        self._school_buttons: dict[str, QPushButton] = {}
        self._gender_buttons: dict[str, QPushButton] = {}
        self._profile_buttons: dict[str, QPushButton] = {}
        self._bucket_buttons: dict[str, QPushButton] = {}
        self._piece_buttons: dict[str, QPushButton] = {}
        self._product_buttons: dict[str, QPushButton] = {}
        self._variant_buttons: dict[str, QPushButton] = {}

        self._build_ui()
        self._refresh_browser()

    def _load_catalog(self) -> None:
        try:
            with get_session() as session:
                self._catalog_rows = load_catalog_snapshot_rows(session)
        except Exception:
            self._catalog_rows = []
        if self._school_links is None:
            try:
                from pos_uniformes.services.school_product_link_service import list_all_active_links
                with get_session() as session:
                    self._school_links = list_all_active_links(session)
            except Exception:
                self._school_links = []

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(16, 12, 16, 8)
        title = QLabel("Buscar producto")
        title.setObjectName("dialogTitleLabel")
        header.addWidget(title)
        header.addStretch()
        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("toolbarGhostButton")
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(16, 4, 16, 16)
        self._content_layout.setSpacing(10)

        self._build_steps_section()
        self._build_detail_section()
        self._content_layout.addStretch()

        content.setLayout(self._content_layout)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self.setLayout(root)

        QShortcut(QKeySequence("Escape"), self).activated.connect(self.reject)

    def _build_steps_section(self) -> None:
        steps_box = QFrame()
        steps_box.setObjectName("guidedStepsCard")
        steps_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        steps_layout = QVBoxLayout()
        steps_layout.setContentsMargins(12, 10, 12, 8)
        steps_layout.setSpacing(4)

        self._path_label = QLabel("")
        self._path_label.setObjectName("guidedPath")
        steps_layout.addWidget(self._path_label)

        # Step 1 — Mode
        mode_title = QLabel("1. Elige una ruta")
        mode_title.setObjectName("guidedStepTitle")
        mode_hint = QLabel("Uniformes por escuela o piezas generales.")
        mode_hint.setObjectName("guidedStepHint")
        mode_hint.setWordWrap(True)
        self._mode_row = QHBoxLayout()
        self._mode_row.setSpacing(8)
        steps_layout.addWidget(mode_title)
        steps_layout.addWidget(mode_hint)
        steps_layout.addLayout(self._mode_row)

        # Step 2 — Level
        self._level_section = QWidget()
        level_layout = QVBoxLayout()
        level_layout.setContentsMargins(0, 0, 0, 0)
        level_layout.setSpacing(8)
        level_title = QLabel("2. Elige nivel")
        level_title.setObjectName("guidedStepTitle")
        level_hint = QLabel("Solo niveles disponibles.")
        level_hint.setObjectName("guidedStepHint")
        self._level_grid = QGridLayout()
        self._level_grid.setHorizontalSpacing(10)
        self._level_grid.setVerticalSpacing(10)
        level_layout.addWidget(level_title)
        level_layout.addWidget(level_hint)
        level_layout.addLayout(self._level_grid)
        self._level_section.setLayout(level_layout)
        steps_layout.addWidget(self._level_section)

        # Step 3 — School
        self._school_section = QWidget()
        school_layout = QVBoxLayout()
        school_layout.setContentsMargins(0, 0, 0, 0)
        school_layout.setSpacing(8)
        school_title = QLabel("3. Elige escuela")
        school_title.setObjectName("guidedStepTitle")
        school_hint = QLabel("Escuelas del nivel elegido.")
        school_hint.setObjectName("guidedStepHint")
        school_hint.setWordWrap(True)
        school_scroll = QScrollArea()
        school_scroll.setWidgetResizable(True)
        school_scroll.setFrameShape(QFrame.Shape.NoFrame)
        school_scroll.setMinimumHeight(100)
        school_scroll.setObjectName("guidedScrollArea")
        self._school_container = QWidget()
        self._school_container.setObjectName("guidedGridSurface")
        self._school_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._school_grid = QGridLayout()
        self._school_grid.setContentsMargins(0, 0, 0, 0)
        self._school_grid.setHorizontalSpacing(10)
        self._school_grid.setVerticalSpacing(10)
        self._school_container.setLayout(self._school_grid)
        school_scroll.setWidget(self._school_container)
        school_layout.addWidget(school_title)
        school_layout.addWidget(school_hint)
        school_layout.addWidget(school_scroll)
        self._school_section.setLayout(school_layout)
        steps_layout.addWidget(self._school_section, 1)

        # Step 4 — Gender/Line
        self._gender_section = QWidget()
        gender_layout = QVBoxLayout()
        gender_layout.setContentsMargins(0, 0, 0, 0)
        gender_layout.setSpacing(8)
        self._gender_title = QLabel("4. Elige tipo de uniforme")
        self._gender_title.setObjectName("guidedStepTitle")
        self._gender_hint = QLabel("Elige la linea mas cercana a lo que buscan.")
        self._gender_hint.setObjectName("guidedStepHint")
        self._gender_hint.setWordWrap(True)
        self._gender_row = QHBoxLayout()
        self._gender_row.setSpacing(8)
        gender_layout.addWidget(self._gender_title)
        gender_layout.addWidget(self._gender_hint)
        gender_layout.addLayout(self._gender_row)
        self._gender_section.setLayout(gender_layout)
        steps_layout.addWidget(self._gender_section)

        # Step 5a — Official profile
        self._profile_section = QWidget()
        profile_layout = QVBoxLayout()
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(8)
        profile_title = QLabel("5. Elige perfil oficial")
        profile_title.setObjectName("guidedStepTitle")
        profile_hint = QLabel("Usa este paso solo para separar niña, niño o compartido.")
        profile_hint.setObjectName("guidedStepHint")
        profile_hint.setWordWrap(True)
        self._profile_row = QHBoxLayout()
        self._profile_row.setSpacing(8)
        profile_layout.addWidget(profile_title)
        profile_layout.addWidget(profile_hint)
        profile_layout.addLayout(self._profile_row)
        self._profile_section.setLayout(profile_layout)
        steps_layout.addWidget(self._profile_section)

        # Step 5b — Bucket
        self._bucket_section = QWidget()
        bucket_layout = QVBoxLayout()
        bucket_layout.setContentsMargins(0, 0, 0, 0)
        bucket_layout.setSpacing(8)
        bucket_title = QLabel("5. Elige grupo")
        bucket_title.setObjectName("guidedStepTitle")
        bucket_hint = QLabel("Separa basicos y extras para reducir la lista.")
        bucket_hint.setObjectName("guidedStepHint")
        bucket_hint.setWordWrap(True)
        self._bucket_row = QHBoxLayout()
        self._bucket_row.setSpacing(8)
        bucket_layout.addWidget(bucket_title)
        bucket_layout.addWidget(bucket_hint)
        bucket_layout.addLayout(self._bucket_row)
        self._bucket_section.setLayout(bucket_layout)
        steps_layout.addWidget(self._bucket_section)

        # Step 6 — Piece type
        self._piece_section = QWidget()
        piece_layout = QVBoxLayout()
        piece_layout.setContentsMargins(0, 0, 0, 0)
        piece_layout.setSpacing(8)
        piece_title = QLabel("6. Elige tipo de pieza")
        piece_title.setObjectName("guidedStepTitle")
        piece_hint = QLabel("Primero elige la familia de prenda que buscan.")
        piece_hint.setObjectName("guidedStepHint")
        piece_hint.setWordWrap(True)
        self._piece_groups_layout = QVBoxLayout()
        self._piece_groups_layout.setContentsMargins(0, 0, 0, 0)
        self._piece_groups_layout.setSpacing(6)
        piece_layout.addWidget(piece_title)
        piece_layout.addWidget(piece_hint)
        piece_layout.addLayout(self._piece_groups_layout)
        self._piece_section.setLayout(piece_layout)
        steps_layout.addWidget(self._piece_section)

        # Step 7 — Product cards
        self._products_section = QWidget()
        products_layout = QVBoxLayout()
        products_layout.setContentsMargins(0, 0, 0, 0)
        products_layout.setSpacing(8)
        self._products_title = QLabel("7. Modelos sugeridos")
        self._products_title.setObjectName("guidedStepTitle")
        self._products_hint = QLabel("Toca una tarjeta para elegir el modelo.")
        self._products_hint.setObjectName("guidedStepHint")
        self._products_hint.setWordWrap(True)
        self._empty_label = QLabel("Selecciona una ruta para comenzar.")
        self._empty_label.setObjectName("guidedPath")
        product_scroll = QScrollArea()
        product_scroll.setWidgetResizable(True)
        product_scroll.setFrameShape(QFrame.Shape.NoFrame)
        product_scroll.setMinimumHeight(140)
        product_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        product_scroll.setObjectName("guidedScrollArea")
        self._product_container = QWidget()
        self._product_container.setObjectName("guidedGridSurface")
        self._product_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._product_flow = FlowLayout(margin=0, h_spacing=4, v_spacing=8)
        self._product_container.setLayout(self._product_flow)
        product_scroll.setWidget(self._product_container)
        products_layout.addWidget(self._products_title)
        products_layout.addWidget(self._products_hint)
        products_layout.addWidget(self._empty_label)
        products_layout.addWidget(product_scroll, 1)
        self._products_section.setLayout(products_layout)
        steps_layout.addWidget(self._products_section, 1)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addStretch()
        reset_btn = QPushButton("Limpiar pasos")
        reset_btn.setObjectName("ghostButton")
        reset_btn.clicked.connect(lambda: self._reset_route("school"))
        basics_btn = QPushButton("Piezas generales")
        basics_btn.setObjectName("secondaryButton")
        basics_btn.clicked.connect(lambda: self._reset_route("basics"))
        footer.addWidget(reset_btn)
        footer.addWidget(basics_btn)
        steps_layout.addLayout(footer)

        steps_box.setLayout(steps_layout)
        self._content_layout.addWidget(steps_box)

    def _build_detail_section(self) -> None:
        detail_box = QFrame()
        detail_box.setObjectName("guidedStepsCard")
        detail_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        detail_layout = QVBoxLayout()
        detail_layout.setContentsMargins(12, 10, 12, 8)
        detail_layout.setSpacing(8)
        detail_title = QLabel("Producto seleccionado")
        detail_title.setObjectName("guidedGroupBoxTitle")
        detail_layout.addWidget(detail_title)

        detail_header = QHBoxLayout()
        detail_header.setSpacing(10)
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(72, 72)
        detail_header.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignTop)
        text_layout = QVBoxLayout()
        self._detail_title = QLabel("Sin seleccion — toca un modelo para verlo aqui.")
        self._detail_title.setObjectName("satDetailTitle")
        self._detail_meta = QLabel("")
        self._detail_meta.setObjectName("satDetailMeta")
        self._detail_meta.setWordWrap(True)
        text_layout.addWidget(self._detail_title)
        text_layout.addWidget(self._detail_meta)
        detail_header.addLayout(text_layout, 1)

        self._variant_section = QWidget()
        variant_layout = QVBoxLayout()
        variant_layout.setContentsMargins(0, 0, 0, 0)
        variant_layout.setSpacing(6)
        variant_title = QLabel("Variantes disponibles")
        variant_title.setObjectName("guidedStepHint")
        self._variant_groups_layout = QVBoxLayout()
        self._variant_groups_layout.setContentsMargins(0, 0, 0, 0)
        self._variant_groups_layout.setSpacing(6)
        variant_layout.addWidget(variant_title)
        variant_layout.addLayout(self._variant_groups_layout)
        self._variant_section.setLayout(variant_layout)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._qty_spin = QSpinBox()
        self._qty_spin.setRange(1, 100)
        self._qty_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._qty_spin.setValue(1)
        self._add_btn = QPushButton("Agregar a venta")
        self._add_btn.setObjectName("primaryButton")
        self._add_btn.setMinimumHeight(38)
        self._add_btn.clicked.connect(self._handle_add)
        actions.addStretch()
        actions.addWidget(QLabel("Cantidad"))
        actions.addWidget(self._qty_spin)
        actions.addWidget(self._add_btn)

        detail_layout.addLayout(detail_header)
        detail_layout.addWidget(self._variant_section)
        detail_layout.addLayout(actions)
        detail_box.setLayout(detail_layout)
        self._content_layout.addWidget(detail_box)

    # ── Handlers ──

    def _reset_route(self, mode_key: str) -> None:
        self._state.reset(mode_key)
        self._qty_spin.setValue(1)
        self._refresh_browser()

    def _on_mode_change(self, mode_key: str) -> None:
        self._reset_route(mode_key)

    def _on_level_selected(self, level: str) -> None:
        self._state.level = level
        self._state.school = ""
        self._state.profile = "TODOS"
        self._state.product_key = ""
        self._state.sku = ""
        self._refresh_browser()

    def _on_school_selected(self, school: str) -> None:
        self._state.school = school
        self._state.profile = "TODOS"
        self._state.product_key = ""
        self._state.sku = ""
        self._refresh_browser()

    def _on_gender_selected(self, gender: str) -> None:
        self._state.gender = gender
        self._state.profile = "TODOS"
        self._state.piece = ""
        self._state.product_key = ""
        self._state.sku = ""
        self._refresh_browser()

    def _on_profile_selected(self, profile: str) -> None:
        self._state.profile = profile
        self._state.product_key = ""
        self._state.sku = ""
        self._refresh_browser()

    def _on_bucket_selected(self, bucket: str) -> None:
        self._state.bucket = bucket
        self._state.piece = ""
        self._state.product_key = ""
        self._state.sku = ""
        self._refresh_browser()

    def _on_piece_selected(self, piece: str) -> None:
        self._state.piece = piece
        self._state.product_key = ""
        self._state.sku = ""
        self._refresh_browser()

    def _on_product_selected(self, product_key: str) -> None:
        self._state.product_key = product_key
        self._state.sku = ""
        self._refresh_browser()

    def _on_variant_selected(self, sku: str) -> None:
        self._state.sku = sku
        row = next((r for r in self._catalog_rows if str(r.get("sku")) == sku), None)
        self._apply_detail(row)
        self._refresh_product_checks()
        self._refresh_variant_checks()

    def _handle_add(self) -> None:
        if not self._state.sku:
            return
        self.sku_selected.emit(self._state.sku, self._qty_spin.value())
        self._qty_spin.setValue(1)

    # ── Refresh ──

    def _refresh_browser(self) -> None:
        view = build_guided_catalog_view(
            snapshot_rows=self._catalog_rows,
            mode_key=self._state.mode,
            level_filter=self._state.level,
            school_filter=self._state.school,
            gender_filter=self._state.gender,
            profile_filter=self._state.profile,
            bucket_filter=self._state.bucket,
            piece_filter=self._state.piece,
            selected_product_key=self._state.product_key,
            selected_sku=self._state.sku,
            school_links=self._school_links or None,
        )
        if self._correct_state(view):
            return
        self._apply_view(view)

    def _correct_state(self, view: GuidedCatalogView) -> bool:
        corrected = False
        available_levels = {opt.key for opt in view.level_options}
        if self._state.mode == "school" and self._state.level and self._state.level not in available_levels:
            self._state.level = ""
            self._state.school = ""
            self._state.sku = ""
            corrected = True
        available_schools = {opt.key for opt in view.school_options}
        if self._state.mode == "school" and self._state.school and self._state.school not in available_schools:
            self._state.school = ""
            self._state.profile = "TODOS"
            self._state.sku = ""
            corrected = True
        available_profiles = {opt.key for opt in view.profile_options}
        if (
            self._state.mode == "school"
            and self._state.gender == "OFICIAL"
            and self._state.profile not in {"", "TODOS"}
            and self._state.profile not in available_profiles
        ):
            self._state.profile = "TODOS"
            self._state.product_key = ""
            self._state.sku = ""
            corrected = True
        available_buckets = {opt.key for opt in view.bucket_options}
        if self._state.mode == "basics" and self._state.bucket and self._state.bucket not in available_buckets:
            self._state.bucket = "BASICO" if "BASICO" in available_buckets else "TODOS"
            self._state.piece = ""
            self._state.product_key = ""
            self._state.sku = ""
            corrected = True
        available_pieces = {opt.key for opt in view.piece_options}
        if self._state.mode == "basics" and self._state.piece and self._state.piece not in available_pieces:
            self._state.piece = ""
            self._state.product_key = ""
            self._state.sku = ""
            corrected = True
        if corrected:
            self._refresh_browser()
        return corrected

    def _apply_view(self, view: GuidedCatalogView) -> None:
        self._state.product_key = view.selected_product_key
        self._state.sku = view.selected_sku
        self._path_label.setText(view.path_label)
        self._empty_label.setText(view.empty_label or "Toca un producto para ver detalle.")

        self._rebuild_mode_buttons()
        self._rebuild_level_grid(view.level_options)
        self._rebuild_school_grid(view.school_options)
        self._rebuild_hrow(self._gender_row, view.gender_options, self._state.gender, self._on_gender_selected, "_gender_buttons")
        self._rebuild_hrow(self._profile_row, view.profile_options, self._state.profile, self._on_profile_selected, "_profile_buttons")
        self._rebuild_hrow(self._bucket_row, view.bucket_options, self._state.bucket, self._on_bucket_selected, "_bucket_buttons")
        self._rebuild_piece_buttons(view.piece_options)
        self._rebuild_product_buttons(view.product_cards)
        self._rebuild_variant_buttons(view.variant_options)

        self._apply_section_visibility(view)
        self._apply_product_labels(view)

        if self._state.sku:
            row = next((r for r in self._catalog_rows if str(r.get("sku")) == self._state.sku), None)
            self._apply_detail(row)
        else:
            self._apply_detail(None)
        self._refresh_product_checks()
        self._refresh_variant_checks()

    def _apply_section_visibility(self, view: GuidedCatalogView) -> None:
        mode = self._state.mode
        self._level_section.setVisible(mode == "school")
        self._school_section.setVisible(mode == "school" and bool(self._state.level))
        self._gender_section.setVisible(mode == "basics" or bool(self._state.school))
        self._profile_section.setVisible(mode == "school" and self._state.gender == "OFICIAL" and bool(view.profile_options))
        self._bucket_section.setVisible(mode == "basics" and bool(view.bucket_options))
        self._piece_section.setVisible(mode == "basics" and bool(view.piece_options))
        self._products_section.setVisible(
            (mode == "basics" and bool(self._state.piece)) or (mode == "school" and bool(self._state.school))
        )
        if mode == "school":
            self._gender_title.setText("4. Elige linea")
            self._gender_hint.setText("Primero separa deportivo de oficial.")
        else:
            self._gender_title.setText("4. Elige tipo de uniforme")
            self._gender_hint.setText("Elige la linea mas cercana a lo que buscan.")

    def _apply_product_labels(self, view: GuidedCatalogView) -> None:
        mode = self._state.mode
        show_profile = mode == "school" and self._state.gender == "OFICIAL" and bool(view.profile_options)
        show_bucket = mode == "basics" and bool(view.bucket_options)
        show_piece = mode == "basics" and bool(view.piece_options)
        if show_piece:
            self._products_title.setText("7. Modelos sugeridos")
            self._products_hint.setText("Primero elige el tipo de pieza; luego toca un modelo.")
        elif show_bucket:
            self._products_title.setText("6. Modelos sugeridos")
            self._products_hint.setText("Elige Basicos, Extras o Todos; luego toca un modelo.")
        elif show_profile:
            self._products_title.setText("6. Modelos sugeridos")
            self._products_hint.setText("Primero elige el perfil oficial; luego toca un modelo.")
        else:
            self._products_title.setText("5. Modelos sugeridos")
            self._products_hint.setText("Primero toca un modelo; luego elige la variante que quieren.")

    def _apply_detail(self, row: dict[str, object] | None) -> None:
        if row is None:
            self._icon_label.setPixmap(_scaled_asset("qr_icons/default.png", 48))
            self._icon_label.setFixedSize(48, 48)
            self._detail_title.setText("Sin seleccion — toca un modelo para verlo aqui.")
            self._detail_meta.setVisible(False)
            self._variant_section.setVisible(False)
            return
        self._icon_label.setFixedSize(72, 72)
        self._icon_label.setPixmap(_catalog_icon(row))
        self._detail_meta.setVisible(True)
        self._variant_section.setVisible(bool(self._variant_buttons))
        detail_parts = [
            str(row.get("tipo_prenda_nombre", "")),
            str(row.get("tipo_pieza_nombre", "")),
            f"Talla {row.get('talla', '')}",
        ]
        color = str(row.get("color") or "").strip()
        if color and color.lower() not in ("sin color", "ad hoc"):
            detail_parts.append(f"Color {color}")
        price = Decimal(str(row.get("precio_venta") or "0")).quantize(Decimal("0.01"))
        detail_parts.append(f"Precio ${price}")
        title = str(row.get("producto_nombre_base", ""))
        if self._state.mode != "basics":
            title = f"{row.get('sku', '')} | {title}"
        self._detail_title.setText(title)
        self._detail_meta.setText(" | ".join(detail_parts))

    # ── Widget builders ──

    def _choice_button(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("guidedChoiceButton")
        btn.setCheckable(True)
        btn.setMinimumHeight(60)
        return btn

    def _rebuild_mode_buttons(self) -> None:
        definitions = (
            ("school", "Uniformes por escuela\nNivel > Escuela > Genero"),
            ("basics", "Basicos y extras\nSolo piezas generales"),
        )
        if not self._mode_buttons:
            for key, label in definitions:
                btn = self._choice_button(label)
                btn.clicked.connect(lambda checked=False, k=key: self._on_mode_change(k))
                self._mode_row.addWidget(btn)
                self._mode_buttons[key] = btn
        for key, btn in self._mode_buttons.items():
            btn.setChecked(self._state.mode == key)

    def _rebuild_level_grid(self, options: tuple) -> None:
        _clear_layout(self._level_grid)
        self._level_buttons = {}
        for index, option in enumerate(options):
            btn = self._choice_button(option.label)
            btn.setEnabled(option.enabled)
            btn.setChecked(self._state.level == option.key)
            icon = _level_icon(option.label)
            if not icon.isNull():
                btn.setIcon(icon)
                btn.setIconSize(QSize(24, 24))
            btn.clicked.connect(lambda checked=False, k=option.key: self._on_level_selected(k))
            self._level_grid.addWidget(btn, index // 3, index % 3)
            self._level_buttons[option.key] = btn

    def _rebuild_school_grid(self, options: tuple) -> None:
        _clear_layout(self._school_grid)
        self._school_buttons = {}
        for index, option in enumerate(options):
            btn = self._choice_button(option.label)
            btn.setEnabled(option.enabled)
            btn.setChecked(self._state.school == option.key)
            btn.clicked.connect(lambda checked=False, k=option.key: self._on_school_selected(k))
            self._school_grid.addWidget(btn, index // 3, index % 3)
            self._school_buttons[option.key] = btn

    def _rebuild_hrow(self, layout: QHBoxLayout, options: tuple, selected_key: str, handler, attr_name: str) -> None:
        _clear_layout(layout)
        buttons: dict[str, QPushButton] = {}
        for option in options:
            btn = self._choice_button(option.label)
            btn.setEnabled(option.enabled)
            btn.setChecked(selected_key == option.key)
            btn.clicked.connect(lambda checked=False, k=option.key: handler(k))
            layout.addWidget(btn)
            buttons[option.key] = btn
        layout.addStretch()
        setattr(self, attr_name, buttons)

    def _rebuild_piece_buttons(self, options: tuple) -> None:
        _clear_layout(self._piece_groups_layout)
        self._piece_buttons = {}
        grouped: dict[str, list] = {}
        for option in options:
            group = getattr(option, "group_label", "") or "Piezas"
            grouped.setdefault(group, []).append(option)
        for group_label, group_options in grouped.items():
            label = QLabel(group_label)
            label.setObjectName("guidedGroupLabel")
            self._piece_groups_layout.addWidget(label)
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(4)
            grid.setVerticalSpacing(6)
            for idx, option in enumerate(group_options):
                btn = self._choice_button(option.label)
                btn.setProperty("compactChoice", True)
                btn.setEnabled(option.enabled)
                btn.setChecked(self._state.piece == option.key)
                btn.setMinimumHeight(42)
                btn.setMinimumWidth(170)
                btn.setMaximumWidth(170)
                btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.clicked.connect(lambda checked=False, k=option.key: self._on_piece_selected(k))
                grid.addWidget(btn, idx // 3, idx % 3, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                self._piece_buttons[option.key] = btn
            row_layout.addLayout(grid)
            row_layout.addStretch()
            self._piece_groups_layout.addLayout(row_layout)

    def _rebuild_product_buttons(self, product_cards: tuple) -> None:
        _clear_layout(self._product_flow)
        self._product_buttons = {}
        for card in product_cards:
            lines = [card.title]
            if card.subtitle:
                lines.append(card.subtitle)
            btn = QPushButton("\n".join(lines))
            btn.setObjectName("guidedProductButton")
            btn.setCheckable(True)
            compact = (self._state.mode == "basics" and bool(self._state.piece)) or (
                self._state.mode == "school" and bool(self._state.school)
            )
            btn.setProperty("compactCard", compact)
            if compact:
                btn.setMinimumHeight(68)
                btn.setFixedWidth(252)
                btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            else:
                btn.setMinimumHeight(94)
                btn.setMinimumWidth(250)
            row = next((r for r in self._catalog_rows if str(r.get("sku")) == card.sku), None)
            if row is not None:
                btn.setIcon(QIcon(_catalog_icon(row)))
                btn.setIconSize(QSize(24, 24) if compact else QSize(34, 34))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.setChecked(self._state.product_key == card.key)
            btn.clicked.connect(lambda checked=False, k=card.key: self._on_product_selected(k))
            self._product_flow.addWidget(btn)
            self._product_buttons[card.key] = btn

    def _rebuild_variant_buttons(self, variant_options: tuple) -> None:
        _clear_layout(self._variant_groups_layout)
        self._variant_buttons = {}
        if not variant_options:
            self._variant_section.setVisible(False)
            return
        self._variant_section.setVisible(True)
        current_price = None
        current_flow: FlowLayout | None = None
        for option in variant_options:
            price_label = getattr(option, "price_label", "") or str(option.label).split("·")[-1].strip()
            if price_label != current_price or current_flow is None:
                current_price = price_label
                current_flow = FlowLayout(margin=0, h_spacing=6, v_spacing=8)
                self._variant_groups_layout.addLayout(current_flow)
            btn = _DoubleClickButton(option.label)
            btn.setObjectName("guidedChoiceButton")
            btn.setCheckable(True)
            btn.setProperty("compactChoice", True)
            btn.setMinimumHeight(42)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setChecked(self._state.sku == option.sku)
            btn.clicked.connect(lambda checked=False, s=option.sku: self._on_variant_selected(s))

            def _on_dbl(sku=option.sku):
                self._on_variant_selected(sku)
                self._handle_add()

            btn.double_clicked.connect(_on_dbl)
            current_flow.addWidget(btn)
            self._variant_buttons[option.sku] = btn

    def _refresh_product_checks(self) -> None:
        for key, btn in self._product_buttons.items():
            btn.setChecked(key == self._state.product_key)

    def _refresh_variant_checks(self) -> None:
        for sku, btn in self._variant_buttons.items():
            btn.setChecked(sku == self._state.sku)


# ── Module-level helpers ──


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            _clear_layout(child)


def _asset_path(relative: str) -> Path:
    return _ASSETS_DIR / relative


def _scaled_asset(relative: str, size: int) -> QPixmap:
    px = QPixmap(str(_asset_path(relative)))
    if px.isNull():
        return QPixmap()
    return px.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def _icon_from_asset(relative: str) -> QIcon:
    p = _asset_path(relative)
    return QIcon(str(p)) if p.exists() else QIcon()


def _level_icon(level_name: str) -> QIcon:
    normalized = str(level_name).strip().lower()
    name = {
        "preescolar": "kiosk_icons/level_pre.svg",
        "primaria": "kiosk_icons/level_prim.svg",
        "secundaria": "kiosk_icons/level_sec.svg",
        "prepa": "kiosk_icons/level_prepa.svg",
        "preparatoria": "kiosk_icons/level_prepa.svg",
    }.get(normalized, "kiosk_icons/level_prim.svg")
    return _icon_from_asset(name)


def _catalog_icon(row: dict[str, object]) -> QPixmap:
    product_name = str(row.get("producto_nombre_base") or "").lower()
    garment_type = str(row.get("tipo_prenda_nombre") or "").lower()
    piece_type = str(row.get("tipo_pieza_nombre") or "").lower()
    icon_map = {
        "camisa": "qr_icons/camisa.png",
        "playera": "qr_icons/playera.png",
        "falda": "qr_icons/falda.png",
        "pantalon": "qr_icons/pantalon.png",
        "pants": "qr_icons/pants_suelto.png",
        "sueter": "qr_icons/sueter.png",
        "chaleco": "qr_icons/chaleco.png",
        "jumper": "qr_icons/jumper.png",
        "calceta": "qr_icons/calceta.png",
        "corbata": "qr_icons/corbata.png",
        "corbatin": "qr_icons/corbatin.png",
        "bata": "qr_icons/bata.png",
        "boina": "qr_icons/boina.png",
        "malla": "qr_icons/malla.png",
        "guante": "qr_icons/guante.png",
        "chamarra": "qr_icons/chamarra.png",
    }
    for candidate in (garment_type, piece_type, product_name):
        for keyword, asset in icon_map.items():
            if keyword in candidate:
                return _scaled_asset(asset, 72)
    return _scaled_asset("qr_icons/default.png", 72)
