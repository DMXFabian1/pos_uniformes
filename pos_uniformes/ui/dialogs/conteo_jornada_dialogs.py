"""Diálogos de la sección Conteos que giran alrededor de la jornada.

- `ConteoNuevaJornadaDialog`: qué vas a contar (escuela, o una prenda de los
  básicos). Devuelve el alcance; la ventana abre la jornada.
- `ConteoRevisionDialog`: lo que ve el dueño antes de aplicar una jornada
  terminada — cada talla con su diferencia — y los botones Aplicar / Descartar.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pos_uniformes.services.conteo_service import ESCUELA_ID_BASICOS, NOMBRE_BASICOS

_ESTILO = """
    QDialog { background: #f7f5f2; }
    QLabel { color: #1a1a1a; background: transparent; }
    QComboBox { background: #ffffff; color: #1a1a1a; border: 1px solid #e5e5e5;
                border-radius: 6px; padding: 4px 8px; min-height: 28px; }
    QTableWidget { background: #ffffff; alternate-background-color: #faf7f3; color: #1a1a1a;
                   border: 1px solid #e5e5e5; border-radius: 8px; }
    QHeaderView::section { background: #f5ebe0; color: #5c3019; font-weight: 600;
                           border: none; padding: 7px 6px; }
    QPushButton { background: #ffffff; color: #87492c; border: 1px solid #e5d9cd;
                  border-radius: 8px; padding: 7px 14px; }
    QPushButton:hover { background: #f5ebe0; }
    QPushButton#primaryButton { background: #87492c; color: #ffffff; border: none; font-weight: 600; }
    QPushButton#primaryButton:hover { background: #5c3019; }
    QPushButton#dangerButton { color: #8a2f2f; border-color: #e0c4c4; }
"""


def _default_session_factory() -> Session:
    from pos_uniformes.database.connection import get_session

    return get_session().__enter__()


class ConteoNuevaJornadaDialog(QDialog):
    """¿Qué vas a contar? Escuela, o una prenda de los básicos."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Empezar conteo")
        self.setStyleSheet(_ESTILO)
        self._session_factory = session_factory or _default_session_factory
        self.escuela_id: int | None = None
        self.tipo_pieza: str = ""

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.addWidget(QLabel("¿Qué vas a contar?"))
        self._escuela_combo = QComboBox()
        self._escuela_combo.currentIndexChanged.connect(self._on_escuela)
        layout.addWidget(self._escuela_combo)
        self._tipo_combo = QComboBox()
        self._tipo_combo.setVisible(False)
        layout.addWidget(self._tipo_combo)
        pista = QLabel("Imprime la hoja antes de ir al piso, y regresa aquí a capturar.")
        pista.setStyleSheet("color: #8a7a68; font-size: 12px;")
        pista.setWordWrap(True)
        layout.addWidget(pista)

        botones = QDialogButtonBox()
        ok = botones.addButton("Empezar", QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("primaryButton")
        botones.addButton(QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)
        self.setLayout(layout)
        self.setMinimumWidth(420)
        self._cargar_escuelas()

    def _cargar_escuelas(self) -> None:
        from pos_uniformes.services.catalog_school_link_service import list_all_schools

        session = self._session_factory()
        try:
            escuelas = list_all_schools(session)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Sin conexión", f"No se pudieron cargar las escuelas:\n{exc}")
            escuelas = []
        finally:
            session.close()
        self._escuela_combo.clear()
        self._escuela_combo.addItem(f"— {NOMBRE_BASICOS} —", ESCUELA_ID_BASICOS)
        for e in escuelas:
            self._escuela_combo.addItem(e["escuela_nombre"], e["escuela_id"])
        if self._escuela_combo.count() > 1:
            self._escuela_combo.setCurrentIndex(1)

    def _on_escuela(self) -> None:
        es_basicos = self._escuela_combo.currentData() == ESCUELA_ID_BASICOS
        self._tipo_combo.setVisible(es_basicos)
        if es_basicos and self._tipo_combo.count() == 0:
            from pos_uniformes.services.conteo_service import obtener_variantes_basicos_agrupadas

            session = self._session_factory()
            try:
                grupos = obtener_variantes_basicos_agrupadas(session)
            except Exception:  # noqa: BLE001
                grupos = []
            finally:
                session.close()
            tipos = sorted({g["tipo_pieza"] for g in grupos if not g.get("virtual") and g["tipo_pieza"]})
            # Una jornada de básicos SIEMPRE es de una prenda: los 2,361
            # renglones de "todos" no se cuentan en una tarde.
            for t in tipos:
                self._tipo_combo.addItem(t, t)

    def _aceptar(self) -> None:
        dato = self._escuela_combo.currentData()
        if dato is None:
            return
        if int(dato) == ESCUELA_ID_BASICOS:
            tipo = self._tipo_combo.currentData()
            if not tipo:
                QMessageBox.information(self, "Elige una prenda", "Los básicos se cuentan por prenda: elige cuál.")
                return
            self.escuela_id = None
            self.tipo_pieza = str(tipo)
        else:
            self.escuela_id = int(dato)
            self.tipo_pieza = ""
        self.accept()


class ConteoRevisionDialog(QDialog):
    """Lo que el dueño ve antes de aplicar: cada talla contada y su diferencia."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        jornada,
        revisada_por: str,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Revisar conteo · {jornada.titulo}")
        self.setStyleSheet(_ESTILO)
        self._session_factory = session_factory or _default_session_factory
        self._jornada = jornada
        self._revisada_por = revisada_por
        self.resultado: str = ""   # "aplicada" | "descartada" | ""

        layout = QVBoxLayout()
        layout.setSpacing(10)
        self._resumen_label = QLabel("")
        self._resumen_label.setWordWrap(True)
        self._resumen_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self._resumen_label)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Producto", "Talla", "Sistema", "Contó", "Diferencia"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table, 1)

        self._solo_dif = QPushButton("Ver solo las que difieren")
        self._solo_dif.setCheckable(True)
        self._solo_dif.setChecked(True)
        self._solo_dif.toggled.connect(self._pintar)
        acciones = QHBoxLayout()
        acciones.addWidget(self._solo_dif)
        acciones.addStretch()
        descartar = QPushButton("Descartar")
        descartar.setObjectName("dangerButton")
        descartar.clicked.connect(self._descartar)
        acciones.addWidget(descartar)
        self._aplicar_btn = QPushButton("Aplicar al inventario")
        self._aplicar_btn.setObjectName("primaryButton")
        self._aplicar_btn.clicked.connect(self._aplicar)
        acciones.addWidget(self._aplicar_btn)
        layout.addLayout(acciones)

        cerrar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        cerrar.rejected.connect(self.reject)
        layout.addWidget(cerrar)
        self.setLayout(layout)
        self.resize(760, 560)
        self._cargar()

    def _cargar(self) -> None:
        from pos_uniformes.database.models import ConteoJornada
        from pos_uniformes.services.conteo_jornada_service import resumen_para_revisar

        session = self._session_factory()
        try:
            j = session.get(ConteoJornada, self._jornada.id)
            self._resumen = resumen_para_revisar(session, j)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Error", f"No se pudo leer la jornada:\n{exc}")
            self._resumen = None
            return
        finally:
            session.close()
        r = self._resumen
        self._resumen_label.setText(
            f"<b>{r.quien}</b> contó <b>{len(r.lineas)}</b> tallas · "
            f"<b>{len(r.con_diferencia)}</b> difieren · "
            f"faltan <b>{r.piezas_de_menos}</b> piezas · sobran <b>{r.piezas_de_mas}</b>"
        )
        self._aplicar_btn.setEnabled(bool(r.con_diferencia))
        self._pintar()

    def _pintar(self) -> None:
        if self._resumen is None:
            return
        lineas = self._resumen.con_diferencia if self._solo_dif.isChecked() else self._resumen.lineas
        self._table.setRowCount(len(lineas))
        for fila, l in enumerate(lineas):
            dif = f"{l.diferencia:+d}" if l.diferencia else "—"
            valores = (l.producto, l.talla, str(l.sistema), str(l.fisico), dif)
            for col, txt in enumerate(valores):
                item = QTableWidgetItem(txt)
                if col:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 4 and l.diferencia:
                    item.setForeground(QBrush(QColor("#b91c1c" if l.diferencia < 0 else "#166534")))
                self._table.setItem(fila, col, item)

    def _aplicar(self) -> None:
        if self._resumen is None:
            return
        n = len(self._resumen.con_diferencia)
        r = QMessageBox.question(
            self, "Aplicar al inventario",
            f"Se van a ajustar {n} tallas según lo que contó {self._resumen.quien}.\n\n¿Aplicar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        from pos_uniformes.database.models import ConteoJornada
        from pos_uniformes.services.conteo_jornada_service import aplicar_jornada

        session = self._session_factory()
        try:
            j = session.get(ConteoJornada, self._jornada.id)
            ajustados, omitidos = aplicar_jornada(session, j, revisada_por=self._revisada_por)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            QMessageBox.critical(self, "No se aplicó", str(exc))
            return
        finally:
            session.close()
        self.resultado = "aplicada"
        QMessageBox.information(
            self, "Inventario actualizado",
            f"Se ajustaron {ajustados} tallas." + (f" {omitidos} se omitieron (dejarían negativo)." if omitidos else ""),
        )
        self.accept()

    def _descartar(self) -> None:
        r = QMessageBox.question(
            self, "Descartar conteo",
            "El conteo se guarda como historia pero NO se aplica al inventario.\n\n¿Descartar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        from pos_uniformes.database.models import ConteoJornada
        from pos_uniformes.services.conteo_jornada_service import descartar_jornada

        session = self._session_factory()
        try:
            j = session.get(ConteoJornada, self._jornada.id)
            descartar_jornada(session, j, revisada_por=self._revisada_por)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            QMessageBox.critical(self, "No se descartó", str(exc))
            return
        finally:
            session.close()
        self.resultado = "descartada"
        self.accept()
