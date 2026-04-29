"""Diálogo de administración de ligas producto-escuela para el catálogo guiado."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.database.connection import get_session
from pos_uniformes.services.catalog_school_link_service import (
    add_school_product_link,
    list_all_schools,
    list_general_products,
    list_links_by_school,
    remove_school_product_link,
)

_ADMIN_PIN = "12345"


def prompt_school_product_link_admin(parent=None, *, on_links_changed=None) -> None:
    """Pide PIN y abre el diálogo de administración si es correcto."""
    pin, ok = QInputDialog.getText(
        parent,
        "Acceso restringido",
        "Introduce la contraseña de administrador:",
        QLineEdit.EchoMode.Password,
    )
    if not ok:
        return
    if pin.strip() != _ADMIN_PIN:
        QMessageBox.warning(parent, "Acceso denegado", "Contraseña incorrecta.")
        return
    dialog = SchoolProductLinkDialog(parent, on_links_changed=on_links_changed)
    dialog.exec()


class SchoolProductLinkDialog(QDialog):
    def __init__(self, parent=None, *, on_links_changed=None) -> None:
        super().__init__(parent)
        self._on_links_changed = on_links_changed
        self._selected_school: dict | None = None
        self._all_schools: list[dict] = []
        self._general_products: list[dict] = []
        self._current_links: list[dict] = []
        self._links_changed = False

        self.setWindowTitle("Ligas de catálogo — Admin")
        self.setModal(True)
        self.resize(820, 580)
        self._build_ui()
        self._load_data()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("dialogHeaderCard")
        header.setStyleSheet(
            "QFrame#dialogHeaderCard {"
            "  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "    stop:0 #c0392b, stop:1 #922b21);"
            "  border-bottom: 2px solid #a93226;"
            "}"
        )
        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(24, 16, 24, 14)
        title_label = QLabel("Ligas de productos generales")
        title_label.setStyleSheet("color: #fff; font-size: 18px; font-weight: 800;")
        subtitle_label = QLabel(
            "Liga piezas del catálogo general a escuelas para que aparezcan en el flujo guiado."
        )
        subtitle_label.setStyleSheet("color: rgba(255,255,255,0.82); font-size: 12px;")
        subtitle_label.setWordWrap(True)
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        header.setLayout(header_layout)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(16, 16, 16, 16)
        body.setSpacing(14)

        # LEFT — schools list
        left_panel = QFrame()
        left_panel.setObjectName("infoSubcard")
        left_panel.setFixedWidth(240)
        left_panel.setStyleSheet("QFrame#infoSubcard { border: 1px solid #d9e5ef; border-radius: 10px; }")
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(10, 12, 10, 10)
        left_layout.setSpacing(8)
        left_title = QLabel("Escuelas")
        left_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #294f69;")
        self._school_list = QListWidget()
        self._school_list.setObjectName("dataTable")
        self._school_list.setStyleSheet(
            "QListWidget { border: none; background: transparent; outline: none; }"
            "QListWidget::item { padding: 8px 10px; border-radius: 6px; color: #294f69; }"
            "QListWidget::item:selected { background: #dbeeff; color: #1a3a54; font-weight: 600; }"
            "QListWidget::item:hover:!selected { background: #eef5fb; }"
        )
        self._school_list.currentRowChanged.connect(self._handle_school_selected)
        left_layout.addWidget(left_title)
        left_layout.addWidget(self._school_list, 1)
        left_panel.setLayout(left_layout)
        body.addWidget(left_panel)

        # RIGHT — link management
        right_panel = QVBoxLayout()
        right_panel.setSpacing(12)

        self._right_school_label = QLabel("Selecciona una escuela")
        self._right_school_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #294f69;")

        # Current links
        links_frame = QFrame()
        links_frame.setObjectName("infoSubcard")
        links_frame.setStyleSheet("QFrame#infoSubcard { border: 1px solid #d9e5ef; border-radius: 10px; }")
        links_layout = QVBoxLayout()
        links_layout.setContentsMargins(12, 12, 12, 10)
        links_layout.setSpacing(6)
        links_section_label = QLabel("Productos ligados")
        links_section_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #5f6d78; text-transform: uppercase;")
        self._links_scroll = QScrollArea()
        self._links_scroll.setWidgetResizable(True)
        self._links_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._links_scroll.setMinimumHeight(130)
        self._links_scroll.setMaximumHeight(200)
        self._links_inner = QWidget()
        self._links_inner_layout = QVBoxLayout()
        self._links_inner_layout.setContentsMargins(0, 0, 0, 0)
        self._links_inner_layout.setSpacing(4)
        self._links_inner_layout.addStretch()
        self._links_inner.setLayout(self._links_inner_layout)
        self._links_scroll.setWidget(self._links_inner)
        self._empty_links_label = QLabel("Sin productos ligados aún.")
        self._empty_links_label.setStyleSheet("color: #9aacb8; font-style: italic; padding: 8px 4px;")
        links_layout.addWidget(links_section_label)
        links_layout.addWidget(self._links_scroll)
        links_frame.setLayout(links_layout)

        # Add product
        add_frame = QFrame()
        add_frame.setObjectName("infoSubcard")
        add_frame.setStyleSheet("QFrame#infoSubcard { border: 1px solid #d9e5ef; border-radius: 10px; }")
        add_layout = QVBoxLayout()
        add_layout.setContentsMargins(12, 12, 12, 10)
        add_layout.setSpacing(6)
        add_section_label = QLabel("Agregar liga")
        add_section_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #5f6d78; text-transform: uppercase;")
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Buscar producto general…")
        self._search_input.setStyleSheet(
            "QLineEdit { border: 1.5px solid #d7e4ee; border-radius: 8px; padding: 6px 10px;"
            "  background: #fcfdfd; color: #294f69; font-size: 13px; }"
            "QLineEdit:focus { border-color: #c45425; }"
        )
        self._search_input.textChanged.connect(self._handle_search_changed)
        self._product_list = QListWidget()
        self._product_list.setStyleSheet(
            "QListWidget { border: 1px solid #e0eaf2; border-radius: 8px; background: #fcfdfd; outline: none; }"
            "QListWidget::item { padding: 7px 10px; border-radius: 5px; color: #294f69; }"
            "QListWidget::item:selected { background: #e6f3ff; color: #1a3a54; }"
            "QListWidget::item:hover:!selected { background: #f0f6fc; }"
        )
        self._product_list.setMaximumHeight(160)
        self._product_list.setMinimumHeight(120)
        self._add_button = QPushButton("Ligar producto seleccionado")
        self._add_button.setObjectName("toolbarPrimaryButton")
        self._add_button.setEnabled(False)
        self._add_button.clicked.connect(self._handle_add_link)
        self._product_list.currentRowChanged.connect(
            lambda row: self._add_button.setEnabled(row >= 0 and self._selected_school is not None)
        )
        add_layout.addWidget(add_section_label)
        add_layout.addWidget(self._search_input)
        add_layout.addWidget(self._product_list)
        add_layout.addWidget(self._add_button)
        add_frame.setLayout(add_layout)

        right_panel.addWidget(self._right_school_label)
        right_panel.addWidget(links_frame)
        right_panel.addWidget(add_frame)
        right_panel.addStretch()
        body.addLayout(right_panel, 1)

        body_widget = QWidget()
        body_widget.setLayout(body)
        root.addWidget(body_widget, 1)

        footer = QFrame()
        footer.setStyleSheet("border-top: 1px solid #e0eaf2; background: #f7f9fb;")
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(16, 10, 16, 10)
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #5f6d78; font-size: 12px;")
        close_button = QPushButton("Cerrar")
        close_button.setObjectName("toolbarSecondaryButton")
        close_button.clicked.connect(self.accept)
        footer_layout.addWidget(self._status_label, 1)
        footer_layout.addWidget(close_button)
        footer.setLayout(footer_layout)
        root.addWidget(footer)

        self.setLayout(root)

    def _load_data(self) -> None:
        try:
            with get_session() as session:
                self._all_schools = list_all_schools(session)
                self._general_products = list_general_products(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error al cargar datos", str(exc))
            return

        self._school_list.clear()
        for school in self._all_schools:
            item = QListWidgetItem(str(school["escuela_nombre"]))
            item.setData(Qt.ItemDataRole.UserRole, school["escuela_id"])
            self._school_list.addItem(item)

        self._rebuild_product_list("")

    def _handle_school_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._all_schools):
            self._selected_school = None
            self._right_school_label.setText("Selecciona una escuela")
            self._rebuild_links_panel([])
            return

        self._selected_school = self._all_schools[row]
        self._right_school_label.setText(str(self._selected_school["escuela_nombre"]))
        self._add_button.setEnabled(self._product_list.currentRow() >= 0)
        self._reload_links()

    def _reload_links(self) -> None:
        if self._selected_school is None:
            self._rebuild_links_panel([])
            return
        try:
            with get_session() as session:
                self._current_links = list_links_by_school(session, self._selected_school["escuela_id"])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._rebuild_links_panel(self._current_links)

    def _rebuild_links_panel(self, links: list[dict]) -> None:
        while self._links_inner_layout.count() > 1:
            item = self._links_inner_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        if not links:
            self._links_inner_layout.insertWidget(0, self._empty_links_label)
            self._empty_links_label.setVisible(True)
            return

        self._empty_links_label.setVisible(False)
        for link in links:
            self._links_inner_layout.insertWidget(
                self._links_inner_layout.count() - 1,
                self._build_link_row(link),
            )

    def _build_link_row(self, link: dict) -> QWidget:
        row_widget = QFrame()
        row_widget.setStyleSheet(
            "QFrame { background: #f0f6fc; border: 1px solid #dbeeff;"
            "  border-radius: 7px; }"
        )
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(10, 6, 8, 6)
        row_layout.setSpacing(10)
        name_label = QLabel(str(link["producto_nombre_base"]))
        name_label.setStyleSheet("font-size: 13px; color: #1a3a54; font-weight: 600; border: none; background: none;")
        remove_btn = QPushButton("Quitar")
        remove_btn.setObjectName("toolbarGhostButton")
        remove_btn.setFixedWidth(70)
        remove_btn.setStyleSheet(
            "QPushButton { color: #c0392b; border: 1px solid #e8b4ae; border-radius: 6px;"
            "  background: #fff; padding: 3px 8px; font-size: 12px; }"
            "QPushButton:hover { background: #fdf0ef; }"
        )
        link_id = int(link["link_id"])
        remove_btn.clicked.connect(lambda _checked, lid=link_id: self._handle_remove_link(lid))
        row_layout.addWidget(name_label, 1)
        row_layout.addWidget(remove_btn)
        row_widget.setLayout(row_layout)
        return row_widget

    def _handle_add_link(self) -> None:
        if self._selected_school is None:
            return
        current_item = self._product_list.currentItem()
        if current_item is None:
            return
        producto_id = int(current_item.data(Qt.ItemDataRole.UserRole))
        producto_nombre = str(current_item.text())
        escuela_id = int(self._selected_school["escuela_id"])
        escuela_nombre = str(self._selected_school["escuela_nombre"])
        try:
            with get_session() as session:
                add_school_product_link(session, escuela_id=escuela_id, producto_id=producto_id)
        except ValueError as exc:
            self._set_status(str(exc), tone="warning")
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._links_changed = True
        self._reload_links()
        self._set_status(f"Ligado: {producto_nombre} → {escuela_nombre}")
        if self._on_links_changed:
            self._on_links_changed()

    def _handle_remove_link(self, link_id: int) -> None:
        try:
            with get_session() as session:
                remove_school_product_link(session, link_id=link_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._links_changed = True
        self._reload_links()
        self._set_status("Liga eliminada.")
        if self._on_links_changed:
            self._on_links_changed()

    def _handle_search_changed(self, text: str) -> None:
        self._rebuild_product_list(text)

    def _rebuild_product_list(self, search: str) -> None:
        normalized = search.strip().lower()
        self._product_list.clear()
        for product in self._general_products:
            nombre = str(product["producto_nombre_base"])
            if normalized and normalized not in nombre.lower():
                continue
            item = QListWidgetItem(nombre)
            item.setData(Qt.ItemDataRole.UserRole, int(product["producto_id"]))
            self._product_list.addItem(item)

    def _set_status(self, text: str, *, tone: str = "success") -> None:
        color = {"success": "#1f6a3b", "warning": "#8a5a0a"}.get(tone, "#5f6d78")
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        QTimer.singleShot(4000, lambda: self._status_label.setText(""))
