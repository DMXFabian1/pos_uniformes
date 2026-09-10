"""Formulario para subir (registrar) el conteo físico de una escuela.

Qt-nativo, reusa el MISMO backend que el conteo del panel de uniformes:
`obtener_variantes_para_conteo` para traer las piezas y `registrar_conteos_lote`
para guardar (actualiza `ultimo_conteo_at` → reinicia el ciclo del calendario).

Solo admin (se abre desde el menú admin del satélite, Ctrl+Shift+A).
`session_factory` inyectable para tests.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QIntValidator, QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pos_uniformes.services.catalog_school_link_service import list_all_schools
from pos_uniformes.services.conteo_service import (
    ESCUELA_ID_BASICOS,
    NOMBRE_BASICOS,
    ConteoInput,
    obtener_variantes_agrupadas_por_producto,
    obtener_variantes_basicos_agrupadas,
    registrar_conteos_lote,
)


def _default_session_factory() -> Session:
    from pos_uniformes.database.connection import get_session

    return get_session()


class ConteoSubirDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
        contado_por: str = "admin (satélite)",
        jornada=None,
        empleada_code: str = "",
    ) -> None:
        """`jornada`: un `JornadaRef` (foto plana de una jornada abierta). Con ella el diálogo queda
        amarrado a su escuela (o prenda básica), muestra lo que ya se capturó
        en esa jornada y permite guardar a medias. Sin jornada funciona como
        siempre (eligiendo escuela)."""
        super().__init__(parent)
        self._session_factory = session_factory or _default_session_factory
        self._contado_por = contado_por
        self._jornada = jornada
        self._empleada_code = (empleada_code or "").strip().upper()
        self._variant_ids: list[int] = []
        self._fisico_inputs: list[QLineEdit] = []
        self._sistemas: list[int] = []
        self._ya_capturados: dict[int, int] = {}
        self._build_ui()
        if jornada is not None:
            self.setWindowTitle(f"Conteo · {jornada.titulo}")
            self._modo_jornada()
        else:
            self.setWindowTitle("Subir conteo")
            self._cargar_escuelas()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Paleta del panel de uniformes (café/crema) para un look coherente.
        self.setStyleSheet(
            """
            QDialog { background: #f7f5f2; }
            QLabel { color: #1a1a1a; background: transparent; }
            QComboBox, QSpinBox {
                background: #ffffff; color: #1a1a1a;
                border: 1px solid #e5e5e5; border-radius: 6px; padding: 3px 6px;
            }
            /* El campo "Físico": explícito para que no lo dibuje el estilo nativo
               de macOS, que a poca altura recorta el número. */
            QLineEdit {
                background: #ffffff; color: #1a1a1a;
                border: 1px solid #d8ccc2; border-radius: 6px;
                padding: 4px 6px; font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #87492c; }
            QTableWidget {
                background: #ffffff; alternate-background-color: #faf7f3;
                color: #1a1a1a; border: 1px solid #e5e5e5; border-radius: 8px;
            }
            QTableWidget::item { padding: 4px 6px; }
            QHeaderView::section {
                background: #f5ebe0; color: #5c3019; font-weight: 600;
                border: none; padding: 7px 6px;
            }
            QPushButton {
                background: #ffffff; color: #87492c;
                border: 1px solid #e5d9cd; border-radius: 8px; padding: 6px 14px;
            }
            QPushButton:hover { background: #f5ebe0; }
            QPushButton#primaryButton {
                background: #87492c; color: #ffffff; border: none; font-weight: 600;
            }
            QPushButton#primaryButton:hover { background: #5c3019; }
            QPushButton#primaryButton:disabled { background: #d8ccc2; color: #f7f5f2; }
            """
        )

        layout = QVBoxLayout()

        top = QHBoxLayout()
        top.addWidget(QLabel("Escuela:"))
        self._escuela_combo = QComboBox()
        self._escuela_combo.setMinimumWidth(260)
        self._escuela_combo.currentIndexChanged.connect(self._on_escuela_cambiada)
        top.addWidget(self._escuela_combo, 1)
        # Filtro de tipo — solo visible con Productos básicos.
        self._tipo_combo = QComboBox()
        self._tipo_combo.setMinimumWidth(150)
        self._tipo_combo.setVisible(False)
        top.addWidget(self._tipo_combo)
        self._cargar_btn = QPushButton("Cargar piezas")
        self._cargar_btn.clicked.connect(self._cargar_piezas)
        top.addWidget(self._cargar_btn)
        layout.addLayout(top)

        self._hint = QLabel("Elige una escuela y carga sus piezas para capturar el conteo.")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        # Solo lo que ella tiene que llenar. Antes había columnas "Tienda"
        # (lo que el sistema cree que hay) y "Diferencia" en vivo: cualquiera
        # cansado copia ese número, y entonces el conteo no cuenta nada.
        # Daniel sí ve la diferencia al revisar, que es cuando sirve.
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Talla", "Color", "Cuántas hay"])
        self._table.verticalHeader().setVisible(False)
        # Filas con aire: si la fila queda corta, el campo "Físico" se comprime y
        # el número del placeholder se recorta (se ve como una rayita).
        self._table.verticalHeader().setDefaultSectionSize(38)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        self._table.setAlternatingRowColors(True)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table, 1)

        actions = QHBoxLayout()
        self._registrar_btn = QPushButton("Registrar conteo")
        self._registrar_btn.setObjectName("primaryButton")
        self._registrar_btn.setEnabled(False)
        self._registrar_btn.clicked.connect(self._registrar)
        actions.addWidget(self._registrar_btn)
        # Solo con jornada: guardar lo que va y seguir otro día.
        self._pausar_btn = QPushButton("Guardar y seguir después")
        self._pausar_btn.setEnabled(False)
        self._pausar_btn.setVisible(False)
        self._pausar_btn.clicked.connect(self._pausar)
        actions.addWidget(self._pausar_btn)
        actions.addStretch()
        layout.addLayout(actions)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        layout.addWidget(close_buttons)

        self.setLayout(layout)
        self.resize(680, 560)

    # ── Datos ─────────────────────────────────────────────────────────────────

    def _cargar_escuelas(self) -> None:
        session = self._session_factory()
        try:
            escuelas = list_all_schools(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Sin conexión", f"No se pudieron cargar las escuelas:\n{exc}")
            return
        finally:
            session.close()
        self._escuela_combo.clear()
        # Entrada especial: productos básicos (sin escuela), al inicio.
        self._escuela_combo.addItem(f"— {NOMBRE_BASICOS} —", ESCUELA_ID_BASICOS)
        for e in escuelas:
            self._escuela_combo.addItem(e["escuela_nombre"], e["escuela_id"])

    def _modo_jornada(self) -> None:
        """Amarra el diálogo a la jornada: sin elegir escuela, y con lo que ya
        se capturó puesto y bloqueado (para no contar dos veces)."""
        from pos_uniformes.services.conteo_jornada_service import capturado_en_jornada

        for w in (self._escuela_combo, self._tipo_combo, self._cargar_btn):
            w.setVisible(False)
        self._registrar_btn.setText("Terminar conteo")
        self._pausar_btn.setVisible(True)
        session = self._session_factory()
        try:
            self._ya_capturados = capturado_en_jornada(session, self._jornada.id)
        except Exception:  # noqa: BLE001 — sin lo previo se captura de cero
            self._ya_capturados = {}
        finally:
            session.close()
        self._cargar_piezas()

    def _on_escuela_cambiada(self) -> None:
        """Muestra el filtro de tipo solo cuando se elige Productos básicos."""
        es_basicos = self._escuela_combo.currentData() == ESCUELA_ID_BASICOS
        self._tipo_combo.setVisible(es_basicos)
        if es_basicos:
            self._poblar_tipos_basicos()

    def _poblar_tipos_basicos(self) -> None:
        session = self._session_factory()
        try:
            grupos = obtener_variantes_basicos_agrupadas(session)
        except Exception:  # noqa: BLE001
            grupos = []
        finally:
            session.close()
        tipos = sorted({
            g["tipo_pieza"] for g in grupos
            if not g.get("virtual", False) and g["tipo_pieza"]
        })
        self._tipo_combo.clear()
        self._tipo_combo.addItem("Todos", None)
        for t in tipos:
            self._tipo_combo.addItem(t, t)

    def _cargar_piezas(self) -> None:
        if self._jornada is not None:
            escuela_id = (
                ESCUELA_ID_BASICOS if self._jornada.escuela_id is None else self._jornada.escuela_id
            )
            tipo_basicos = self._jornada.tipo_pieza or None
        else:
            escuela_id = self._escuela_combo.currentData()
            if escuela_id is None:
                return
            tipo_basicos = (
                self._tipo_combo.currentData() if int(escuela_id) == ESCUELA_ID_BASICOS else None
            )
        session = self._session_factory()
        try:
            if int(escuela_id) == ESCUELA_ID_BASICOS:
                grupos_raw = obtener_variantes_basicos_agrupadas(session, tipo_pieza=tipo_basicos)
            else:
                grupos_raw = obtener_variantes_agrupadas_por_producto(session, int(escuela_id))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Error", f"No se pudieron cargar las piezas:\n{exc}")
            return
        finally:
            session.close()

        self._variant_ids = []
        self._fisico_inputs = []
        self._sistemas = []

        # Misma estructura que el panel de uniformes: se agrupa por producto y se
        # EXCLUYEN los productos virtuales (Pants 3pz, Chamarra) — esos no se
        # cuentan directo, se arman de sus componentes (Pants 2pz + playera).
        grupos: list[tuple[str, list]] = [
            (g["producto_nombre"], g["variantes"])
            for g in grupos_raw
            if not g.get("virtual", False) and g["variantes"]
        ]
        total_piezas = sum(len(items) for _, items in grupos)

        total_filas = sum(1 + len(items) for _, items in grupos)
        self._table.clearSpans()
        self._table.setRowCount(0)
        self._table.setRowCount(total_filas)

        fila = 0
        for producto, items in grupos:
            self._agregar_encabezado(fila, f"{producto}  ·  {len(items)} pzs")
            fila += 1
            for v in items:
                self._table.setItem(fila, 0, QTableWidgetItem(f"  {v.talla}"))
                self._table.setItem(fila, 1, QTableWidgetItem(v.color))

                # Campo limpio: sin placeholder con el esperado. Vacío significa
                # "no la conté" y no se registra — no se toma por buena.
                inp = QLineEdit()
                inp.setValidator(QIntValidator(0, 999999, inp))
                inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
                inp.setMinimumHeight(30)
                inp.setMinimumWidth(72)
                inp.setMaximumWidth(110)
                if v.variante_id in self._ya_capturados:
                    # Ya contada en esta jornada: se ve SU número (no el del
                    # sistema) y no se vuelve a registrar.
                    inp.setText(str(self._ya_capturados[v.variante_id]))
                    inp.setReadOnly(True)
                    inp.setStyleSheet(
                        "QLineEdit { background: #eef5ee; color: #2f6b2f; border-color: #a9c9a9; }"
                    )
                inp.textChanged.connect(self._on_fisico_changed)
                self._table.setCellWidget(fila, 2, inp)

                self._variant_ids.append(v.variante_id)
                self._fisico_inputs.append(inp)
                self._sistemas.append(v.stock_tienda)
                fila += 1

        if total_piezas:
            # El avance y el botón los maneja `_on_fisico_changed`: al cargar
            # no hay nada capturado, así que no hay nada que registrar.
            self._on_fisico_changed()
        else:
            self._registrar_btn.setEnabled(False)
            self._hint.setText("Esta escuela no tiene piezas para contar.")

    def _agregar_encabezado(self, fila: int, texto: str) -> None:
        """Fila-encabezado de un producto: negrita, con fondo, ocupa todo el ancho."""
        item = QTableWidgetItem(texto)
        fuente = QFont()
        fuente.setBold(True)
        item.setFont(fuente)
        item.setBackground(QBrush(QColor("#f5ebe0")))  # --brand-light
        item.setForeground(QBrush(QColor("#5c3019")))  # --brand-dark
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # no seleccionable
        self._table.setItem(fila, 0, item)
        self._table.setSpan(fila, 0, 1, self._table.columnCount())

    def _on_fisico_changed(self, _texto: str = "") -> None:
        """Cuántas tallas llevan número. Nada de diferencias.

        Antes esta función pintaba la diferencia contra lo esperado en vivo
        (rojo si faltaba, verde si sobraba). Eso le decía a quien captura cuál
        era la respuesta "correcta", y un conteo que confirma lo que el
        sistema ya creía no sirve de nada.
        """
        llenas = sum(1 for w in self._fisico_inputs if w.text().strip())
        nuevas = sum(1 for w in self._fisico_inputs if w.text().strip() and not w.isReadOnly())
        total = len(self._fisico_inputs)
        if self._jornada is not None:
            # Terminar vale con lo que haya (aunque todo venga de antes);
            # pausar solo tiene sentido si hay algo nuevo que guardar.
            self._registrar_btn.setEnabled(llenas > 0)
            self._pausar_btn.setEnabled(nuevas > 0)
        else:
            self._registrar_btn.setEnabled(llenas > 0)
        if total:
            faltan = total - llenas
            self._hint.setText(
                f"{llenas} de {total} tallas capturadas."
                + (f"  Las {faltan} vacías se quedan sin contar." if faltan else "")
            )

    def _nuevos(self) -> tuple[list, int]:
        """(conteos nuevos, tallas vacías). Lo ya capturado en la jornada no cuenta."""
        conteos = []
        sin_contar = 0
        for vid, inp in zip(self._variant_ids, self._fisico_inputs):
            txt = inp.text().strip()
            if inp.isReadOnly():
                continue
            if not txt:
                sin_contar += 1
                continue
            conteos.append(ConteoInput(variante_id=vid, stock_fisico=int(txt)))
        return conteos, sin_contar

    def _guardar(self, conteos: list) -> bool:
        """Sube los conteos nuevos. False si algo falló (ya avisó)."""
        if not conteos:
            return True
        session = self._session_factory()
        try:
            registrar_conteos_lote(
                session, conteos, self._contado_por,
                jornada_id=self._jornada.id if self._jornada is not None else None,
            )
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo registrar el conteo:\n{exc}")
            return False
        finally:
            session.close()
        return True

    def _pausar(self) -> None:
        """Guarda lo que va y cierra. La jornada sigue abierta para retomarla."""
        conteos, _ = self._nuevos()
        if not self._guardar(conteos):
            return
        QMessageBox.information(
            self,
            "Guardado",
            f"Se guardaron {len(conteos)} tallas. Puedes seguir después desde Conteos.",
        )
        self.accept()

    def _registrar(self) -> None:
        """Registra SOLO las tallas que traen número (y con jornada, la cierra).

        Antes una casilla vacía tomaba el esperado y se guardaba como contada
        sin diferencia: la talla quedaba con fecha de conteo fresca sin que
        nadie la hubiera visto. Eso le pone cara de nuevo a un dato viejo, que
        es peor que no contar. Ahora vacío = no la conté, y no se toca.
        """
        conteos, sin_contar = self._nuevos()
        if not conteos and not self._ya_capturados:
            QMessageBox.information(
                self,
                "Nada que registrar",
                "No capturaste ninguna talla. Escribe cuántas hay al menos en una.",
            )
            return
        if sin_contar:
            respuesta = QMessageBox.question(
                self,
                "Faltan tallas por capturar",
                f"Vas a registrar {len(conteos)} tallas.\n"
                f"Quedan {sin_contar} sin capturar y esas NO se van a tocar.\n\n"
                + ("¿Terminar el conteo así?" if self._jornada is not None else "¿Registrar así?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                return
        if not self._guardar(conteos):
            return
        if self._jornada is not None:
            from pos_uniformes.services.conteo_jornada_service import terminar_jornada

            from pos_uniformes.database.models import ConteoJornada

            session = self._session_factory()
            try:
                jornada = session.get(ConteoJornada, self._jornada.id)
                terminar_jornada(session, jornada, empleada_code=self._empleada_code)
                session.commit()
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                QMessageBox.critical(self, "Error", f"Se guardó el conteo pero no se pudo cerrar la jornada:\n{exc}")
                return
            finally:
                session.close()
        total = len(conteos) + len(self._ya_capturados)
        QMessageBox.information(
            self,
            "Conteo registrado",
            f"Se registraron {total} tallas a nombre de "
            f"{self._contado_por}. Quedan pendientes de revisión: el inventario "
            "no cambia hasta que se aprueben.",
        )
        self.accept()
