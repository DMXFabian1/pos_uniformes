"""Uniformes por escuela (catálogo, fase 2): qué piezas lleva el uniforme de
cada escuela, en qué grupo (Diario / Deportivo…), en qué orden, si es
obligatoria y en qué color va. Las piezas señalan productos —propios de la
escuela o generales del estante— sin copiarlos. Todo se guarda al momento.
POS: Más → Uniformes por escuela. Ver Obsidian 38."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.database.connection import get_session
from pos_uniformes.services import conjunto_service as cs
from pos_uniformes.services import uniforme_service as us
from pos_uniformes.services.catalog_school_link_service import list_all_schools, list_general_products

COLS = ("Grupo", "Pieza", "Tipo", "Origen", "Color", "Oblig.", "Se arma de", "", "", "")

_INPUT_CSS = (
    "QLineEdit { border: 1.5px solid #d5c9b9; border-radius: 8px; padding: 5px 10px; min-height: 20px;"
    " background: #fffdf8; color: #2f2a24; font-size: 13px; } QLineEdit:focus { border-color: #c45425; }"
)
_CELL_CSS = (
    "QComboBox, QLineEdit { border: 1px solid #d9e5ef; border-radius: 6px; padding: 2px 6px; min-height: 22px;"
    " background: #fff; color: #2f2a24; font-size: 12px; }"
    "QComboBox::drop-down { border: none; width: 18px; } QComboBox QAbstractItemView { background: #fff; color: #2f2a24; }"
)
_ARROW_CSS = (
    "QPushButton { background: #fff; border: 1px solid #d9e5ef; border-radius: 6px; color: #294f69;"
    " padding: 0; font-size: 11px; min-width: 0; } QPushButton:hover { background: #eef5fb; }"
)
(_COL_GRUPO, _COL_PIEZA, _COL_TIPO, _COL_ORIGEN, _COL_COLOR, _COL_OBLIG, _COL_RECETA,
 _COL_UP, _COL_DOWN, _COL_QUITAR) = range(10)


def prompt_uniforme_escuela_admin(parent=None, *, on_changed=None) -> None:
    dialog = UniformeEscuelaDialog(parent, on_changed=on_changed)
    dialog.exec()


class UniformeEscuelaDialog(QDialog):
    def __init__(self, parent=None, *, on_changed=None, session_factory=get_session) -> None:
        super().__init__(parent)
        self._on_changed = on_changed
        self._session_factory = session_factory
        self._escuelas: list[dict] = []
        self._generales: list[dict] = []
        self._escuela: dict | None = None
        self._uniforme_id: int | None = None
        self._piezas: list[dict] = []
        self._pintando = False
        self.setWindowTitle("Uniformes por escuela")
        self.setModal(True)
        self.resize(1040, 640)
        self._build_ui()
        self._load()

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("dialogHeaderCard")
        header.setStyleSheet(
            "QFrame#dialogHeaderCard { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 #1f5f8b, stop:1 #163f5c); border-bottom: 2px solid #1a4d70; }"
        )
        hl = QVBoxLayout()
        hl.setContentsMargins(24, 16, 24, 14)
        t = QLabel("Uniformes por escuela")
        t.setStyleSheet("color: #fff; font-size: 18px; font-weight: 800; background: transparent; border: none;")
        st = QLabel(
            "De qué se compone el uniforme de cada escuela: sus prendas con escudo y las "
            "generales del estante que también usa. Una prenda general vive una vez y puede "
            "estar en varios uniformes."
        )
        st.setStyleSheet("color: rgba(255,255,255,0.82); font-size: 12px; background: transparent; border: none;")
        st.setWordWrap(True)
        hl.addWidget(t)
        hl.addWidget(st)
        header.setLayout(hl)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(16, 16, 16, 16)
        body.setSpacing(14)

        left = QFrame()
        left.setObjectName("infoSubcard")
        left.setFixedWidth(250)
        left.setStyleSheet("QFrame#infoSubcard { border: 1px solid #d9e5ef; border-radius: 10px; }")
        ll = QVBoxLayout()
        ll.setContentsMargins(10, 12, 10, 10)
        ll.setSpacing(8)
        lt = QLabel("Escuelas")
        lt.setStyleSheet("font-size: 13px; font-weight: 700; color: #294f69; background: transparent; border: none;")
        self._escuela_filtro = QLineEdit()
        self._escuela_filtro.setPlaceholderText("Buscar escuela…")
        self._escuela_filtro.setStyleSheet(_INPUT_CSS)
        self._escuela_filtro.textChanged.connect(self._pintar_escuelas)
        self._escuela_list = QListWidget()
        self._escuela_list.setStyleSheet(
            "QListWidget { border: none; background: transparent; outline: none; }"
            "QListWidget::item { padding: 7px 10px; border-radius: 6px; color: #294f69; }"
            "QListWidget::item:selected { background: #dbeeff; color: #1a3a54; font-weight: 600; }"
            "QListWidget::item:hover:!selected { background: #eef5fb; }"
        )
        self._escuela_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._escuela_list.currentItemChanged.connect(self._escuela_elegida)
        ll.addWidget(lt)
        ll.addWidget(self._escuela_filtro)
        ll.addWidget(self._escuela_list, 1)
        left.setLayout(ll)
        body.addWidget(left)

        right = QVBoxLayout()
        right.setSpacing(10)
        top = QHBoxLayout()
        self._titulo = QLabel("Elige una escuela")
        self._titulo.setStyleSheet("font-size: 15px; font-weight: 700; color: #294f69; background: transparent; border: none;")
        self._proponer_btn = QPushButton("Proponer desde catálogo")
        self._proponer_btn.setObjectName("toolbarPrimaryButton")
        self._proponer_btn.setToolTip(
            "Arma el uniforme con lo que la base ya sabe: las prendas de la escuela y las generales ligadas."
        )
        self._proponer_btn.clicked.connect(self._proponer)
        self._proponer_btn.hide()
        top.addWidget(self._titulo, 1)
        top.addWidget(self._proponer_btn)
        right.addLayout(top)

        self._tabla = QTableWidget(0, len(COLS))
        self._tabla.setHorizontalHeaderLabels(COLS)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tabla.verticalHeader().setDefaultSectionSize(38)
        self._tabla.setStyleSheet(
            "QTableWidget { background: #fff; border: 1px solid #d9e5ef; border-radius: 8px; gridline-color: #eef2f6; }"
            "QHeaderView::section { background: #f3f6f9; color: #294f69; font-weight: 700; padding: 6px; border: none;"
            " border-bottom: 1px solid #d9e5ef; }"
        )
        hdr = self._tabla.horizontalHeader()
        hdr.setSectionResizeMode(_COL_PIEZA, QHeaderView.ResizeMode.Stretch)
        for c in (_COL_GRUPO, _COL_TIPO, _COL_ORIGEN, _COL_COLOR, _COL_OBLIG, _COL_RECETA, _COL_UP, _COL_DOWN, _COL_QUITAR):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._vacio = QLabel("Esta escuela todavía no tiene uniforme armado.")
        self._vacio.setStyleSheet("color: #9aacb8; font-style: italic; padding: 8px 4px; background: transparent; border: none;")
        self._vacio.hide()
        right.addWidget(self._vacio)
        right.addWidget(self._tabla, 1)

        add = QFrame()
        add.setObjectName("infoSubcard")
        add.setStyleSheet("QFrame#infoSubcard { border: 1px solid #d9e5ef; border-radius: 10px; }")
        al = QVBoxLayout()
        al.setContentsMargins(12, 10, 12, 10)
        al.setSpacing(6)
        at = QLabel("Agregar prenda general del estante")
        at.setStyleSheet("font-size: 12px; font-weight: 700; color: #5f6d78; text-transform: uppercase; background: transparent; border: none;")
        fila = QHBoxLayout()
        self._buscar = QLineEdit()
        self._buscar.setPlaceholderText("Buscar prenda general… (pants, short, playera, camisa)")
        self._buscar.setStyleSheet(_INPUT_CSS)
        self._buscar.textChanged.connect(self._pintar_generales)
        self._generales_list = QListWidget()
        self._generales_list.setMaximumHeight(110)
        self._generales_list.setStyleSheet(
            "QListWidget { border: 1px solid #d9e5ef; border-radius: 8px; background: #fff; outline: none; }"
            "QListWidget::item { padding: 5px 10px; color: #2f2a24; }"
            "QListWidget::item:selected { background: #f4d4bb; color: #4a1505; }"
        )
        self._agregar_btn = QPushButton("Agregar al uniforme")
        self._agregar_btn.setObjectName("toolbarPrimaryButton")
        self._agregar_btn.setEnabled(False)
        self._agregar_btn.clicked.connect(self._agregar_general)
        self._generales_list.currentRowChanged.connect(
            lambda r: self._agregar_btn.setEnabled(r >= 0 and self._uniforme_id is not None)
        )
        self._generales_list.itemDoubleClicked.connect(lambda _i: self._agregar_general())
        fila.addWidget(self._buscar, 1)
        al.addWidget(at)
        al.addLayout(fila)
        al.addWidget(self._generales_list)
        al.addWidget(self._agregar_btn)
        add.setLayout(al)
        right.addWidget(add)

        body.addLayout(right, 1)
        bw = QWidget()
        bw.setLayout(body)
        root.addWidget(bw, 1)

        footer = QFrame()
        footer.setStyleSheet("border-top: 1px solid #e0eaf2; background: #f7f9fb;")
        fl = QHBoxLayout()
        fl.setContentsMargins(16, 10, 16, 10)
        self._status = QLabel("")
        self._status.setStyleSheet("color: #5f6d78; font-size: 12px; background: transparent; border: none;")
        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("toolbarSecondaryButton")
        cerrar.clicked.connect(self.accept)
        fl.addWidget(self._status, 1)
        fl.addWidget(cerrar)
        footer.setLayout(fl)
        root.addWidget(footer)
        self.setLayout(root)

    # -------------------------------------------------------------- datos
    def _load(self) -> None:
        try:
            with self._session_factory() as s:
                self._escuelas = list_all_schools(s)
                self._generales = list_general_products(s)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error al cargar", str(exc))
            return
        self._pintar_escuelas()
        self._pintar_generales()

    def _pintar_escuelas(self) -> None:
        filtro = self._escuela_filtro.text().strip().lower()
        self._escuela_list.clear()
        for e in self._escuelas:
            nombre = str(e["escuela_nombre"])
            if filtro and filtro not in nombre.lower():
                continue
            it = QListWidgetItem(nombre)
            it.setData(Qt.ItemDataRole.UserRole, int(e["escuela_id"]))
            self._escuela_list.addItem(it)

    def _pintar_generales(self) -> None:
        filtro = self._buscar.text().strip().lower()
        ya = {p["producto_id"] for p in self._piezas}
        self._generales_list.clear()
        for g in self._generales:
            nombre = str(g["producto_nombre_base"])
            if g["producto_id"] in ya or (filtro and filtro not in nombre.lower()):
                continue
            it = QListWidgetItem(nombre)
            it.setData(Qt.ItemDataRole.UserRole, int(g["producto_id"]))
            self._generales_list.addItem(it)

    def _escuela_elegida(self, actual, _antes=None) -> None:
        if actual is None:
            self._escuela = None
            self._uniforme_id = None
            self._piezas = []
            self._titulo.setText("Elige una escuela")
            self._proponer_btn.hide()
            self._pintar_tabla()
            return
        eid = int(actual.data(Qt.ItemDataRole.UserRole))
        self._escuela = next(e for e in self._escuelas if e["escuela_id"] == eid)
        self._titulo.setText(str(self._escuela["escuela_nombre"]))
        self._recargar()

    def _recargar(self) -> None:
        if self._escuela is None:
            return
        try:
            with self._session_factory() as s:
                uni = us.uniforme_de(s, self._escuela["escuela_id"])
                self._uniforme_id = int(uni.id) if uni is not None else None
                self._piezas = us.piezas_de(s, uni.id) if uni is not None else []
                for p in self._piezas:
                    p["receta"] = cs.receta_texto(s, p["producto_id"]) if p["tipo_pieza"] in cs.TIPOS_CONJUNTO else None
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._proponer_btn.setVisible(True)
        self._proponer_btn.setText("Proponer desde catálogo" if self._uniforme_id is None else "Completar desde catálogo")
        self._pintar_tabla()
        self._pintar_generales()
        self._agregar_btn.setEnabled(self._generales_list.currentRow() >= 0 and self._uniforme_id is not None)

    # -------------------------------------------------------------- tabla
    def _pintar_tabla(self) -> None:
        self._pintando = True
        self._tabla.setRowCount(0)
        self._vacio.setVisible(self._escuela is not None and self._uniforme_id is None)
        for i, p in enumerate(self._piezas):
            self._tabla.insertRow(i)
            grupo = QComboBox()
            grupo.setStyleSheet(_CELL_CSS)
            grupo.addItems(us.GRUPOS)
            grupo.setCurrentText(p["grupo"] if p["grupo"] in us.GRUPOS else "Otro")
            grupo.currentTextChanged.connect(lambda g, pid=p["pieza_id"]: self._cambiar(pid, grupo=g))
            self._tabla.setCellWidget(i, _COL_GRUPO, grupo)
            self._tabla.setItem(i, _COL_PIEZA, QTableWidgetItem(p["nombre"]))
            self._tabla.setItem(i, _COL_TIPO, QTableWidgetItem(p["tipo_pieza"]))
            origen = QTableWidgetItem("con escudo" if p["origen"] == "Escuela" else "general")
            origen.setForeground(Qt.GlobalColor.darkGreen if p["origen"] == "Escuela" else Qt.GlobalColor.darkBlue)
            self._tabla.setItem(i, _COL_ORIGEN, origen)
            color = QLineEdit(p["color"])
            color.setPlaceholderText("color")
            color.setFixedWidth(110)
            color.setStyleSheet(_CELL_CSS)
            color.editingFinished.connect(lambda w=color, pid=p["pieza_id"]: self._cambiar(pid, color=w.text()))
            self._tabla.setCellWidget(i, _COL_COLOR, color)
            oblig = QCheckBox()
            oblig.setChecked(bool(p["obligatoria"]))
            oblig.setToolTip("Obligatoria (sin palomita = opcional: suéter, chaleco…)")
            oblig.toggled.connect(lambda v, pid=p["pieza_id"]: self._cambiar(pid, obligatoria=v))
            self._tabla.setCellWidget(i, _COL_OBLIG, self._centrado(oblig))
            if p.get("receta") is not None:
                # Conjunto artificial (fase 3): se dice de qué se arma y se puede cambiar
                rb = QPushButton(self._receta_corta(p["receta"]) or "⚠ sin receta")
                rb.setStyleSheet(_ARROW_CSS + ("QPushButton { color: #b3541e; font-weight: 700; }" if not p["receta"] else ""))
                rb.setToolTip(p["receta"] or "Este conjunto no sabe de qué se arma: su stock no se calcula y venderlo no baja sus piezas.")
                rb.clicked.connect(lambda _c, pid=p["producto_id"], n=p["nombre"]: self._editar_receta(pid, n))
                self._tabla.setCellWidget(i, _COL_RECETA, rb)
            else:
                self._tabla.setItem(i, _COL_RECETA, QTableWidgetItem(""))
            for col, texto, delta in ((_COL_UP, "▲", -1), (_COL_DOWN, "▼", +1)):
                b = QPushButton(texto)
                b.setFixedSize(28, 26)
                b.setStyleSheet(_ARROW_CSS)
                b.clicked.connect(lambda _c, pid=p["pieza_id"], d=delta: self._mover(pid, d))
                self._tabla.setCellWidget(i, col, b)
            q = QPushButton("Quitar")
            q.setStyleSheet(
                "QPushButton { color: #c0392b; border: 1px solid #e8b4ae; border-radius: 6px;"
                " background: #fff; padding: 2px 8px; font-size: 12px; } QPushButton:hover { background: #fdf0ef; }"
            )
            q.clicked.connect(lambda _c, pid=p["pieza_id"], n=p["nombre"]: self._quitar(pid, n))
            self._tabla.setCellWidget(i, _COL_QUITAR, q)
        self._pintando = False

    @staticmethod
    def _receta_corta(texto: str) -> str:
        """'se arma de Pants 2pz Deportivo X + Playera Deportiva X' → '2pz X + Playera X'."""
        if not texto:
            return ""
        corto = texto
        for palabra in ("se arma de ", "sale de ", "Pants 2pz Deportivo ", "Deportivo ", "Deportiva "):
            corto = corto.replace(palabra, "2pz " if palabra.startswith("Pants 2pz") else "")
        return corto if len(corto) <= 44 else corto[:41] + "…"

    def _editar_receta(self, producto_id: int, nombre: str) -> None:
        dlg = RecetaDialog(self, session_factory=self._session_factory, conjunto_id=producto_id, nombre=nombre, piezas=self._piezas)
        if dlg.exec():
            self._recargar()
            self._avisar(f"Receta guardada: {nombre}")

    @staticmethod
    def _centrado(w: QWidget) -> QWidget:
        cont = QWidget()
        lay = QHBoxLayout(cont)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(w)
        return cont

    # ------------------------------------------------------------ acciones
    def _proponer(self) -> None:
        if self._escuela is None:
            return
        try:
            with self._session_factory() as s:
                antes = len(us.piezas_de(s, us.uniforme_de(s, self._escuela["escuela_id"]).id)) if self._uniforme_id else 0
                uni = us.armar(s, self._escuela["escuela_id"])
                despues = len(us.piezas_de(s, uni.id))
                s.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._recargar()
        self._avisar(f"Uniforme armado: {despues - antes} piezas nuevas ({despues} en total).")

    def _agregar_general(self) -> None:
        it = self._generales_list.currentItem()
        if it is None or self._uniforme_id is None:
            return
        pid, nombre = int(it.data(Qt.ItemDataRole.UserRole)), it.text()
        try:
            with self._session_factory() as s:
                us.agregar_pieza(s, self._uniforme_id, pid)
                s.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._recargar()
        self._avisar(f"Agregada: {nombre}")

    def _cambiar(self, pieza_id: int, **campos) -> None:
        if self._pintando or pieza_id is None:
            return
        try:
            with self._session_factory() as s:
                us.actualizar_pieza(s, pieza_id, **campos)
                s.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        for p in self._piezas:
            if p["pieza_id"] == pieza_id:
                p.update({k: (v if k != "color" else (v or "").strip()) for k, v in campos.items()})
        self._avisar("Guardado.")

    def _mover(self, pieza_id: int, delta: int) -> None:
        try:
            with self._session_factory() as s:
                us.mover_pieza(s, pieza_id, delta)
                s.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._recargar()

    def _quitar(self, pieza_id: int, nombre: str) -> None:
        try:
            with self._session_factory() as s:
                us.quitar_pieza(s, pieza_id)
                s.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._recargar()
        self._avisar(f"Quitada: {nombre}")

    def _avisar(self, texto: str) -> None:
        self._status.setText(texto)
        if self._on_changed:
            self._on_changed()
        QTimer.singleShot(4000, self._limpiar_status)

    def _limpiar_status(self) -> None:
        try:
            self._status.setText("")
        except RuntimeError:
            pass


class RecetaDialog(QDialog):
    """De qué se arma un conjunto (Pants 3pz, Chamarra): una prenda del
    uniforme por cada pieza que pide la receta. Ver conjunto_service."""

    def __init__(self, parent=None, *, session_factory, conjunto_id: int, nombre: str, piezas: list[dict]) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._conjunto_id = int(conjunto_id)
        self._combos: list[tuple[str, int, QComboBox]] = []
        self.setWindowTitle(f"Receta · {nombre}")
        self.setModal(True)
        self.resize(560, 220)
        lay = QVBoxLayout(self)
        titulo = QLabel(nombre)
        titulo.setStyleSheet("font-size: 14px; font-weight: 700; color: #294f69; background: transparent; border: none;")
        lay.addWidget(titulo)
        tipo = next((p["tipo_pieza"] for p in piezas if p["producto_id"] == self._conjunto_id), "")
        plantilla = cs.RECETAS_POR_TIPO.get(tipo, ())
        candidatas = [p for p in piezas if p["tipo_pieza"] not in cs.TIPOS_CONJUNTO]
        actual: dict[int, int] = {}
        try:
            with self._session_factory() as s:
                actual = {int(c.componente_id): int(c.cantidad) for c in cs.receta_de(s, self._conjunto_id)}
        except Exception:  # noqa: BLE001
            actual = {}
        for tipo_pieza, cantidad in plantilla:
            fila = QHBoxLayout()
            etiqueta = QLabel(("Se lleva 1 " if cantidad > 0 else "Deja 1 ") + tipo_pieza + ":")
            etiqueta.setStyleSheet("background: transparent; border: none; color: #294f69;")
            etiqueta.setFixedWidth(170)
            combo = QComboBox()
            combo.setStyleSheet(_CELL_CSS)
            combo.addItem("— elegir —", None)
            # Primero las del tipo que pide la receta, luego el resto por si la escuela lo hace distinto
            for p in sorted(candidatas, key=lambda p: (p["tipo_pieza"] != tipo_pieza, p["nombre"])):
                combo.addItem(p["nombre"] + ("" if p["tipo_pieza"] == tipo_pieza else f"  ({p['tipo_pieza']})"), p["producto_id"])
            del_tipo = [p for p in candidatas if p["tipo_pieza"] == tipo_pieza]
            elegido = next((pid for pid, c in actual.items() if (c > 0) == (cantidad > 0) and any(p["producto_id"] == pid for p in del_tipo)), None)
            if elegido is None:
                elegido = next((pid for pid, c in actual.items() if (c > 0) == (cantidad > 0) and any(p["producto_id"] == pid for p in candidatas)), None)
            if elegido is None and len(del_tipo) == 1:
                elegido = del_tipo[0]["producto_id"]
            if elegido is not None:
                combo.setCurrentIndex(combo.findData(elegido))
            fila.addWidget(etiqueta)
            fila.addWidget(combo, 1)
            lay.addLayout(fila)
            self._combos.append((tipo_pieza, int(cantidad), combo))
        nota = QLabel("Al venderlo bajan las piezas que se lleva y sube la que deja; su stock es el de sus piezas.")
        nota.setWordWrap(True)
        nota.setStyleSheet("color: #5f6d78; font-size: 12px; background: transparent; border: none;")
        lay.addWidget(nota)
        botones = QHBoxLayout()
        botones.addStretch()
        cancelar = QPushButton("Cancelar")
        cancelar.setObjectName("toolbarSecondaryButton")
        cancelar.clicked.connect(self.reject)
        guardar = QPushButton("Guardar receta")
        guardar.setObjectName("toolbarPrimaryButton")
        guardar.clicked.connect(self._guardar)
        botones.addWidget(cancelar)
        botones.addWidget(guardar)
        lay.addLayout(botones)

    def componentes(self) -> list[tuple[int, int]]:
        return [(int(c.currentData()), cant) for _t, cant, c in self._combos if c.currentData() is not None]

    def _guardar(self) -> None:
        comps = self.componentes()
        if len(comps) != len(self._combos):
            QMessageBox.warning(self, "Falta una pieza", "Elige una prenda para cada pieza de la receta.")
            return
        try:
            with self._session_factory() as s:
                cs.definir_receta(s, self._conjunto_id, comps)
                s.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.accept()
