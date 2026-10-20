"""«Mercancía por nombrar»: la ropa normal que entró con el código del proveedor.

Daniel da de alta la compra el día que llega (con el código que trae) y va
nombrando conforme saca la mercancía (2026-10-20). Esta ventana lista lo que
falta y lo nombra por el mismo servicio que usa el celular: nombre con código,
pieza, detalle, color, género. Desde aquí también se imprimen las etiquetas.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

GENEROS = ("Mujer", "Hombre", "Unisex", "Niña", "Niño")

_ESTILO = """
QDialog { background: #f4ede2; }
QLabel { color: #2c2a27; background: transparent; }
QListWidget { background: #ffffff; border: 1px solid #ddd0c0; border-radius: 10px; font-size: 14px; }
QListWidget::item { padding: 8px; border-bottom: 1px solid #f4ede2; }
QListWidget::item:selected { background: #fbf3e6; color: #2c2a27; }
QLineEdit, QComboBox { background: #ffffff; color: #2c2a27; border: 1px solid #ddd0c0;
                       border-radius: 8px; min-height: 34px; padding: 0 10px; font-size: 14px; }
QFrame#ficha { background: #ffffff; border: 1px solid #ddd0c0; border-radius: 12px; }
QPushButton { background: #f8f2e9; color: #73341c; font-weight: 700; border: 1px solid #ddd0c0;
              border-radius: 10px; min-height: 38px; padding: 0 14px; }
QPushButton#primario { background: #a84f2d; color: #ffffff; border: none; }
QPushButton:disabled { color: #b5aa9c; }
"""


class PorNombrarDialog(QDialog):
    """Los parámetros con nombre son para las pruebas y para el POS que la abre."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory=None,
        user_id: int | None = None,
        on_print_labels=None,
        on_changed=None,
    ) -> None:
        super().__init__(parent)
        if session_factory is None:
            from pos_uniformes.database.connection import get_session

            session_factory = get_session
        self._session_factory = session_factory
        self._user_id = user_id
        self._on_print_labels = on_print_labels
        self._on_changed = on_changed
        self._pendientes: list = []
        self._actual = None

        self.setWindowTitle("Mercancía por nombrar")
        self.setStyleSheet(_ESTILO)
        self.resize(980, 640)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(18, 16, 18, 14)
        raiz.setSpacing(10)
        titulo = QLabel("🏷 Mercancía por nombrar")
        titulo.setStyleSheet("font-size: 19px; font-weight: 800; color: #73341c;")
        raiz.addWidget(titulo)
        self.pista = QLabel("")
        self.pista.setWordWrap(True)
        self.pista.setStyleSheet("font-size: 12px; color: #8a8177;")
        raiz.addWidget(self.pista)

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.setChildrenCollapsible(False)
        raiz.addWidget(divisor, 1)

        izquierda = QWidget()
        izq = QVBoxLayout(izquierda)
        izq.setContentsMargins(0, 0, 0, 0)
        self.lista = QListWidget()
        self.lista.currentRowChanged.connect(self._al_escoger)
        izq.addWidget(self.lista, 1)
        self.etiquetas_todo_btn = QPushButton("🏷 Etiquetas de todo lo pendiente")
        self.etiquetas_todo_btn.clicked.connect(self._imprimir_todo)
        izq.addWidget(self.etiquetas_todo_btn)
        divisor.addWidget(izquierda)

        ficha = QFrame()
        ficha.setObjectName("ficha")
        f = QVBoxLayout(ficha)
        f.setContentsMargins(16, 14, 16, 14)
        f.setSpacing(8)
        self.datos = QLabel("")
        self.datos.setWordWrap(True)
        self.datos.setStyleSheet("font-size: 13px; color: #5a534b;")
        f.addWidget(self.datos)

        def _campo(texto: str, widget) -> None:
            lbl = QLabel(texto)
            lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #73341c; margin-top: 4px;")
            f.addWidget(lbl)
            f.addWidget(widget)

        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Prenda + código del proveedor, por ejemplo «Chamarra YT0572»")
        _campo("Nombre (conserva el código)", self.nombre)
        self.pieza = QComboBox()
        self.pieza.setEditable(True)
        _campo("Pieza (qué prenda es)", self.pieza)
        self.detalle = QComboBox()
        self.detalle.setEditable(True)
        _campo("Detalle (opcional: Invierno, Estampado…)", self.detalle)
        self.color = QLineEdit()
        self.color.setPlaceholderText("Surtido si viene revuelto")
        _campo("Color", self.color)
        self.genero = QComboBox()
        self.genero.addItems(GENEROS)
        _campo("Género", self.genero)
        self.estado = QLabel("")
        self.estado.setWordWrap(True)
        self.estado.setStyleSheet("font-size: 12px; color: #a33b25; font-weight: 600;")
        f.addWidget(self.estado)
        f.addStretch(1)

        botones = QHBoxLayout()
        self.etiquetas_btn = QPushButton("🏷 Etiquetas de esta")
        self.etiquetas_btn.clicked.connect(self._imprimir_actual)
        botones.addWidget(self.etiquetas_btn)
        botones.addStretch(1)
        self.medias_btn = QPushButton("Guardar a medias")
        self.medias_btn.setToolTip("Guarda lo que llevas y la deja en la lista")
        self.medias_btn.clicked.connect(lambda: self.guardar(listo=False))
        botones.addWidget(self.medias_btn)
        self.listo_btn = QPushButton("✅ Guardar y listo")
        self.listo_btn.setObjectName("primario")
        self.listo_btn.clicked.connect(lambda: self.guardar(listo=True))
        botones.addWidget(self.listo_btn)
        f.addLayout(botones)
        divisor.addWidget(ficha)
        divisor.setSizes([380, 600])

        pie = QHBoxLayout()
        pie.addStretch(1)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        pie.addWidget(cerrar)
        raiz.addLayout(pie)

        self.refrescar()

    # ── Datos ───────────────────────────────────────────────────────────

    def refrescar(self, *, conservar: int | None = None) -> None:
        from pos_uniformes.database.models import AtributoProducto, TipoPieza
        from pos_uniformes.services import por_nombrar_service as pn

        try:
            with self._session_factory() as session:
                self._pendientes = pn.listar(session)
                piezas = [t.nombre for t in session.query(TipoPieza).order_by(TipoPieza.nombre).all()]
                detalles = [a.nombre for a in session.query(AtributoProducto).order_by(AtributoProducto.nombre).all()]
        except Exception:  # noqa: BLE001
            logger.exception("Por nombrar: no se pudo leer")
            self._avisar("Sin conexión con la base: no se pudo leer la lista.")
            return
        self._avisar("")
        for combo, opciones in ((self.pieza, piezas), (self.detalle, detalles)):
            texto = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("")
            combo.addItems(opciones)
            combo.setCurrentText(texto)
            combo.blockSignals(False)

        self.lista.blockSignals(True)
        self.lista.clear()
        fila_actual = 0
        for i, p in enumerate(self._pendientes):
            item = QListWidgetItem(f"{p.nombre}\n{p.marca} · {p.existencia} pzas · ${p.precio} · desde {p.desde}")
            self.lista.addItem(item)
            if conservar is not None and p.producto_id == conservar:
                fila_actual = i
        self.lista.blockSignals(False)
        n = len(self._pendientes)
        self.pista.setText(
            f"{n} producto{'s' if n != 1 else ''} esperando nombre. Escoge uno, ponle lo que es y «Guardar y listo»."
            if n else "No hay nada por nombrar. ✅"
        )
        self.etiquetas_todo_btn.setEnabled(n > 0 and self._on_print_labels is not None)
        if n:
            self.lista.setCurrentRow(fila_actual)
            self._al_escoger(fila_actual)
        else:
            self._actual = None
            self._pintar_ficha()

    def _al_escoger(self, fila: int) -> None:
        self._actual = self._pendientes[fila] if 0 <= fila < len(self._pendientes) else None
        self._pintar_ficha()

    def _pintar_ficha(self) -> None:
        p = self._actual
        hay = p is not None
        for w in (self.nombre, self.pieza, self.detalle, self.color, self.genero, self.listo_btn, self.medias_btn):
            w.setEnabled(hay)
        self.etiquetas_btn.setEnabled(hay and self._on_print_labels is not None)
        if not hay:
            self.datos.setText("")
            self.nombre.clear()
            return
        self.datos.setText(
            f"<b>{p.nombre}</b> · {p.marca} · {p.categoria}<br>"
            f"{p.existencia} piezas · ${p.precio} · {', '.join(p.skus)}<br>"
            f"Entró el {p.desde}"
        )
        self.nombre.setText(p.nombre)
        self.pieza.setCurrentText(p.pieza)
        self.detalle.setCurrentText(p.detalle)
        self.color.setText("" if p.color == "Surtido" else p.color)
        self.genero.setCurrentText(p.genero or "Mujer")
        self.nombre.setFocus()
        self.nombre.selectAll()

    # ── Acciones ────────────────────────────────────────────────────────

    def guardar(self, *, listo: bool) -> None:
        from pos_uniformes.database.models import Usuario
        from pos_uniformes.services import por_nombrar_service as pn

        if self._actual is None:
            return
        producto_id = self._actual.producto_id
        try:
            with self._session_factory() as session:
                usuario = session.get(Usuario, int(self._user_id)) if self._user_id else None
                if usuario is None:
                    raise pn.NoSePuede("No se pudo validar tu usuario.")
                pn.nombrar(
                    session, usuario, producto_id,
                    nombre=self.nombre.text(), pieza=self.pieza.currentText(),
                    detalle=self.detalle.currentText(), color=self.color.text(),
                    genero=self.genero.currentText(), listo=listo,
                )
                session.commit()
        except (pn.NoSePuede, PermissionError) as exc:
            self._avisar(str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Por nombrar: no se pudo guardar")
            self._avisar("No se pudo guardar. Revisa la conexión.")
            return
        if self._on_changed is not None:
            try:
                self._on_changed()
            except Exception:  # noqa: BLE001
                logger.exception("Por nombrar: falló el refresco del catálogo")
        self.refrescar(conservar=None if listo else producto_id)

    def _imprimir_actual(self) -> None:
        if self._actual is not None:
            self._imprimir([self._actual.producto_id])

    def _imprimir_todo(self) -> None:
        self._imprimir([p.producto_id for p in self._pendientes])

    def _imprimir(self, producto_ids: list[int]) -> None:
        from pos_uniformes.services import por_nombrar_service as pn

        if self._on_print_labels is None or not producto_ids:
            return
        try:
            with self._session_factory() as session:
                ids = pn.skus_de(session, producto_ids)
        except Exception:  # noqa: BLE001
            logger.exception("Por nombrar: no se pudieron leer las tallas")
            self._avisar("No se pudieron leer las tallas para las etiquetas.")
            return
        if not ids:
            QMessageBox.information(self, "Sin tallas", "Ese producto no tiene tallas activas.")
            return
        self._on_print_labels(ids)

    def _avisar(self, texto: str) -> None:
        self.estado.setText(texto)
        self.estado.setVisible(bool(texto))


def abrir_por_nombrar(parent, *, user_id: int | None, on_print_labels=None, on_changed=None) -> None:
    PorNombrarDialog(parent, user_id=user_id, on_print_labels=on_print_labels, on_changed=on_changed).exec()
