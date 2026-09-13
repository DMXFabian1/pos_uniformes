"""Diálogos de la sección Conteos que giran alrededor de la jornada.

- `ConteoNuevaJornadaDialog`: qué vas a contar (escuela, o una prenda de los
  básicos). Devuelve el alcance; la ventana abre la jornada.
- `ConteoRevisionDialog`: lo que ve el dueño antes de aplicar una jornada
  terminada — cada talla con su diferencia — y los botones Aplicar / Descartar.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
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
        titulo: str = "Empezar conteo",
        boton: str = "Empezar",
    ) -> None:
        """El mismo selector sirve para empezar una jornada y para imprimir la
        hoja: cambian el título y el texto del botón."""
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setStyleSheet(_ESTILO)
        self._session_factory = session_factory or _default_session_factory
        self.escuela_id: int | None = None
        self.tipo_pieza: str = ""
        self.titulo: str = ""   # "Práxedis Guerrero" o "Básicos · Camisa", para rotular

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.addWidget(QLabel("¿Qué vas a contar?"))
        self._escuela_combo = QComboBox()
        self._escuela_combo.currentIndexChanged.connect(self._on_escuela)
        layout.addWidget(self._escuela_combo)
        self._tipo_combo = QComboBox()
        self._tipo_combo.setVisible(False)
        self._tipo_combo.currentIndexChanged.connect(self._pintar_ultimo)
        layout.addWidget(self._tipo_combo)
        # Cuándo se contó por última vez lo elegido: para no contar la misma
        # escuela a cada rato. Verde si fue hace poco.
        self._ultimo_label = QLabel("")
        self._ultimo_label.setStyleSheet("color: #8a7a68; font-size: 12px; font-weight: 600;")
        layout.addWidget(self._ultimo_label)
        self._ultimos: dict = {}
        self._abiertas: dict = {}
        self._escuelas: list = []
        self._tipos_pintados_con = None   # con qué valor de "ver todas" se llenó el combo de básicos
        # Las contadas hace poco no aparecen: así no se cuenta la misma a cada
        # rato. "Ver todas" las trae por si Daniel quiere forzar una.
        self._ver_todas = QCheckBox("Ver todas (también las contadas hace poco)")
        self._ver_todas.toggled.connect(self._pintar_escuelas)
        layout.addWidget(self._ver_todas)
        self._ocultas_label = QLabel("")
        self._ocultas_label.setStyleSheet("color: #8a7a68; font-size: 12px;")
        layout.addWidget(self._ocultas_label)
        pista = QLabel("Imprime la hoja antes de ir al piso, y regresa aquí a capturar.")
        pista.setStyleSheet("color: #8a7a68; font-size: 12px;")
        pista.setWordWrap(True)
        layout.addWidget(pista)

        botones = QDialogButtonBox()
        ok = botones.addButton(boton, QDialogButtonBox.ButtonRole.AcceptRole)
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

        from pos_uniformes.services.conteo_jornada_service import ultimo_conteo_de, ultimos_conteos

        from pos_uniformes.services.conteo_jornada_service import abiertas_por_alcance, ref

        session = self._session_factory()
        try:
            escuelas = list_all_schools(session)
            try:
                self._ultimos = ultimos_conteos(session)
            except Exception:  # noqa: BLE001 — sin fechas se puede contar igual
                self._ultimos = {}
            try:
                # Quién está contando qué ahora mismo: se marca "en proceso"
                # para que la siguiente la siga en vez de abrir otra.
                self._abiertas = {k: ref(j) for k, j in abiertas_por_alcance(session).items()}
            except Exception:  # noqa: BLE001
                self._abiertas = {}
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Sin conexión", f"No se pudieron cargar las escuelas:\n{exc}")
            escuelas = []
        finally:
            session.close()
        self._escuelas = list(escuelas)
        self._pintar_escuelas()

    def _pintar_escuelas(self, *_args) -> None:
        from pos_uniformes.services.conteo_jornada_service import ultimo_conteo_de

        todas = self._ver_todas.isChecked()
        self._escuela_combo.blockSignals(True)
        self._escuela_combo.clear()
        self._escuela_combo.addItem(f"— {NOMBRE_BASICOS} —", ESCUELA_ID_BASICOS)
        ocultas = 0
        for e in self._escuelas:
            u = ultimo_conteo_de(self._ultimos, int(e["escuela_id"]))
            abierta = self._abiertas.get(int(e["escuela_id"]))
            # Una en proceso siempre se ve: hay que poder seguirla.
            if abierta is None and u.reciente() and not todas:
                ocultas += 1
                continue
            estado = f"EN PROCESO ({abierta.quien})" if abierta is not None else u.texto()
            self._escuela_combo.addItem(f'{e["escuela_nombre"]}   ·  {estado}', e["escuela_id"])
        self._escuela_combo.blockSignals(False)
        self._ocultas_label.setText(
            f"{ocultas} escuela{'s' if ocultas != 1 else ''} contada{'s' if ocultas != 1 else ''} hace poco no se muestra{'n' if ocultas != 1 else ''}."
            if ocultas else ""
        )
        self._escuela_combo.setCurrentIndex(1 if self._escuela_combo.count() > 1 else 0)
        self._on_escuela()

    def ultimo_elegido(self):
        """El UltimoConteo de lo que está seleccionado ahora."""
        from pos_uniformes.services.conteo_jornada_service import ultimo_conteo_de

        dato = self._escuela_combo.currentData()
        if dato is None:
            return ultimo_conteo_de({}, None)
        if int(dato) == ESCUELA_ID_BASICOS:
            return ultimo_conteo_de(self._ultimos, None, str(self._tipo_combo.currentData() or ""))
        return ultimo_conteo_de(self._ultimos, int(dato))

    def abierta_elegida(self):
        """La JornadaRef en proceso de lo seleccionado, o None."""
        dato = self._escuela_combo.currentData()
        if dato is None:
            return None
        if int(dato) == ESCUELA_ID_BASICOS:
            return self._abiertas.get(("basicos", str(self._tipo_combo.currentData() or "")))
        return self._abiertas.get(int(dato))

    def _pintar_ultimo(self, *_args) -> None:
        abierta = self.abierta_elegida()
        if abierta is not None:
            self._ultimo_label.setText(f"En proceso: la está contando {abierta.quien} desde {abierta.iniciada_at.strftime('%H:%M') if abierta.iniciada_at else 'hoy'}. Puedes seguirla.")
            self._ultimo_label.setStyleSheet("color: #b45309; font-size: 12px; font-weight: 700;")
            return
        u = self.ultimo_elegido()
        texto = u.texto()
        if u.fecha is None:
            self._ultimo_label.setText("Nunca se ha contado.")
            self._ultimo_label.setStyleSheet("color: #8a7a68; font-size: 12px; font-weight: 600;")
            return
        f = u.fecha.astimezone().date() if u.fecha.tzinfo else u.fecha.date()
        dias = (date.today() - f).days
        if dias < 7:
            self._ultimo_label.setText(f"Ojo: ya se contó {texto}. ¿De verdad hace falta otra vez?")
            self._ultimo_label.setStyleSheet("color: #2f6b2f; font-size: 12px; font-weight: 700;")
        else:
            self._ultimo_label.setText(f"Último conteo: {texto}.")
            self._ultimo_label.setStyleSheet("color: #8a7a68; font-size: 12px; font-weight: 600;")

    def _on_escuela(self) -> None:
        es_basicos = self._escuela_combo.currentData() == ESCUELA_ID_BASICOS
        self._tipo_combo.setVisible(es_basicos)
        self._pintar_ultimo()
        if es_basicos and self._tipos_pintados_con != self._ver_todas.isChecked():
            self._tipos_pintados_con = self._ver_todas.isChecked()
            self._tipo_combo.clear()
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
            from pos_uniformes.services.conteo_jornada_service import ultimo_conteo_de

            for t in tipos:
                abierta = self._abiertas.get(("basicos", t))
                if abierta is None and ultimo_conteo_de(self._ultimos, None, t).reciente() and not self._ver_todas.isChecked():
                    continue
                self._tipo_combo.addItem(f"{t}   ·  EN PROCESO ({abierta.quien})" if abierta is not None else t, t)

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
            self.titulo = f"Básicos · {tipo}"
        else:
            self.escuela_id = int(dato)
            self.tipo_pieza = ""
            self.titulo = self._escuela_combo.currentText().split("   ·  ")[0].strip()
        self.accept()


class ConteoRevisionDialog(QDialog):
    """Revisar = decidir qué pedir. Por talla: cuántas hay, cuántas se
    vendieron, a qué ritmo, cuánto se sugiere y lo que Daniel decide.

    Aplicar al inventario también guarda los pedidos: un solo gesto.
    """

    COLUMNAS = ("Prenda", "Talla", "A la mano", "En cajas", "Vendidas", "Ritmo/sem", "Alcanza", "Pidieron", "Hoja", "Surtir", "Sugerido", "Pedido", "La vez pasada")
    COL_CAJAS = 3
    COL_SURTIR = 9
    COL_SUGERIDO = 10
    COL_PEDIDO = 11

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
        self._revision = None
        self._pedidos: dict[int, int | None] = {}   # conteo_id → lo que Daniel escribió
        self._pintando = False

        layout = QVBoxLayout()
        layout.setSpacing(10)
        self._resumen_label = QLabel("")
        self._resumen_label.setWordWrap(True)
        self._resumen_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self._resumen_label)

        self._table = QTableWidget()
        self._table.setColumnCount(len(self.COLUMNAS))
        self._table.setHorizontalHeaderLabels(list(self.COLUMNAS))
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.SelectedClicked
            | QTableWidget.EditTrigger.AnyKeyPressed
        )
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, len(self.COLUMNAS)):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._table.itemChanged.connect(self._pedido_editado)
        self._table.itemDoubleClicked.connect(self._doble_clic)
        layout.addWidget(self._table, 1)

        acciones = QHBoxLayout()
        self._solo_pedir = QPushButton("Ver solo qué hacer")
        self._solo_pedir.setCheckable(True)
        self._solo_pedir.setChecked(True)
        self._solo_pedir.toggled.connect(self._pintar)
        acciones.addWidget(self._solo_pedir)
        self._hoja_btn = QPushButton("Hoja de pedido")
        self._hoja_btn.clicked.connect(self._hoja_de_pedido)
        acciones.addWidget(self._hoja_btn)
        self._historia_btn = QPushButton("Historia de la talla")
        self._historia_btn.clicked.connect(self._historia)
        acciones.addWidget(self._historia_btn)
        self._escuela_btn = QPushButton("Historia de la escuela")
        self._escuela_btn.clicked.connect(self._historia_escuela)
        acciones.addWidget(self._escuela_btn)
        acciones.addStretch()
        descartar = QPushButton("Descartar")
        descartar.setObjectName("dangerButton")
        descartar.clicked.connect(self._descartar)
        acciones.addWidget(descartar)
        self._guardar_btn = QPushButton("Guardar pedido")
        self._guardar_btn.clicked.connect(self._guardar_pedidos)
        acciones.addWidget(self._guardar_btn)
        self._aplicar_btn = QPushButton("Aplicar al inventario")
        self._aplicar_btn.setObjectName("primaryButton")
        self._aplicar_btn.clicked.connect(self._aplicar)
        acciones.addWidget(self._aplicar_btn)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.reject)
        acciones.addWidget(cerrar)
        layout.addLayout(acciones)
        self.setLayout(layout)
        self.resize(1320, 620)
        self._cargar()

    # --- datos ---------------------------------------------------------------------
    def _cargar(self) -> None:
        from pos_uniformes.database.models import ConteoJornada
        from pos_uniformes.services.revision_service import revisar

        session = self._session_factory()
        try:
            j = session.get(ConteoJornada, self._jornada.id)
            self._revision = revisar(session, j)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Error", f"No se pudo leer la jornada:\n{exc}")
            self._revision = None
            return
        finally:
            session.close()
        # Lo que Daniel escribe empieza en lo ya guardado; si no hay, en lo sugerido.
        self._pedidos = {
            l.conteo_id: (l.pedido if l.pedido is not None else (l.sugerido or None))
            for l in self._revision.lineas
        }
        self._resumen()
        self._pintar()

    def _resumen(self) -> None:
        r = self._revision
        piezas = sum(p for p in self._pedidos.values() if p)
        tallas = sum(1 for p in self._pedidos.values() if p)
        partes = [f"<b>{r.quien}</b> contó <b>{len(r.lineas)}</b> tallas de <b>{r.titulo}</b>"]
        partes.append(f"se sugiere pedir <b>{r.piezas_sugeridas}</b> piezas en {r.tallas_a_pedir} tallas")
        if r.piezas_a_surtir:
            partes.append(f"surtir de las cajas <b>{r.piezas_a_surtir}</b> piezas en {r.tallas_a_surtir} tallas")
        if r.urgentes:
            partes.append(f"<span style='color:#b91c1c'><b>{r.urgentes} urgentes</b> (no hay y la piden)</span>")
        partes.append(f"tu pedido: <b>{piezas}</b> piezas en {tallas} tallas")
        texto = " · ".join(partes)
        if not r.lineas:
            texto += "<br><span style='color:#8a8a8a'>Esta jornada no tiene tallas capturadas.</span>"
        elif self._filtro_sin_efecto():
            texto += "<br><span style='color:#8a8a8a'>Nada que pedir ni surtir todavía (faltan ventas para sacar el ritmo): se muestran todas las tallas.</span>"
        self._resumen_label.setText(texto)
        self._hoja_btn.setEnabled(piezas > 0)

    def _lineas_visibles(self):
        from pos_uniformes.services.revision_service import PEDIR, SURTIR, URGENTE

        if not self._solo_pedir.isChecked():
            return list(self._revision.lineas)
        que_hacer = [l for l in self._revision.lineas if l.estado in (URGENTE, PEDIR, SURTIR) or self._pedidos.get(l.conteo_id)]
        # Con poca Libreta casi nada tiene ritmo: si el filtro se lo come todo,
        # se enseñan todas en vez de una tabla vacía (pasó el 2026-09-13).
        return que_hacer if que_hacer else list(self._revision.lineas)

    def _filtro_sin_efecto(self) -> bool:
        from pos_uniformes.services.revision_service import PEDIR, SURTIR, URGENTE

        return self._solo_pedir.isChecked() and bool(self._revision.lineas) and not any(
            l.estado in (URGENTE, PEDIR, SURTIR) or self._pedidos.get(l.conteo_id) for l in self._revision.lineas
        )

    # --- pintura -------------------------------------------------------------------
    def _pintar(self) -> None:
        if self._revision is None:
            return
        from pos_uniformes.services.conteo_hoja_carta_service import nombre_para_hoja
        from pos_uniformes.services.revision_service import NO_SE_MUEVE, SIN_DATOS, URGENTE

        self._pintando = True
        lineas = self._lineas_visibles()
        self._table.setRowCount(len(lineas))
        for fila, l in enumerate(lineas):
            vendidas = f"{l.vendidas} en {l.dias_observados} d" if l.dias_observados else "—"
            alcanza = "—" if l.semanas_cubiertas is None else (f"{l.semanas_cubiertas:g} sem" if l.semanas_cubiertas < 99 else "+")
            if l.estado == SIN_DATOS:
                sugerido = "sin datos"
            elif l.estado == NO_SE_MUEVE:
                sugerido = "no se mueve"
            elif l.estado == URGENTE:
                sugerido = f"{l.sugerido}  ¡urgente!"
            else:
                sugerido = str(l.sugerido) if l.sugerido else "bien"
            if l.pedido_anterior is not None:
                cuando = l.pedido_anterior_at.strftime("%d/%m") if l.pedido_anterior_at else ""
                vendio = f", vendiste {l.vendidas_desde_pedido}" if l.vendidas_desde_pedido is not None else ""
                pasada = f"pediste {l.pedido_anterior} el {cuando}{vendio}"
            elif l.anterior is not None:
                pasada = f"había {l.anterior} el {l.anterior_at.strftime('%d/%m')}"
            else:
                pasada = "primer conteo"
            pedido = self._pedidos.get(l.conteo_id)
            valores = (
                nombre_para_hoja(l.producto, self._revision.titulo),
                f"{l.talla} {l.color}".strip() if l.color and l.color.upper() not in ("", "UNICO", "ÚNICO") else l.talla,
                str(l.conto),
                str(l.en_cajas) if l.en_cajas else "—",
                vendidas,
                f"{l.ritmo_semana:.1f}" if l.ritmo_semana else "—",
                alcanza,
                str(l.pidieron) if l.pidieron else "—",
                str(l.ellas_sugieren) if l.ellas_sugieren is not None else "—",
                str(l.surtir) if l.surtir else "—",
                sugerido,
                "" if pedido is None else str(pedido),
                pasada,
            )
            for col, txt in enumerate(valores):
                item = QTableWidgetItem(txt)
                item.setData(Qt.ItemDataRole.UserRole, l.conteo_id)
                if col not in (0, len(valores) - 1):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == self.COL_PEDIDO:
                    item.setBackground(QBrush(QColor("#fff8e6")))
                    fuente = item.font()
                    fuente.setBold(True)
                    item.setFont(fuente)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == self.COL_SUGERIDO:
                    if l.estado == URGENTE:
                        item.setForeground(QBrush(QColor("#b91c1c")))
                    elif l.estado in (NO_SE_MUEVE, SIN_DATOS):
                        item.setForeground(QBrush(QColor("#8a8a8a")))
                if col == self.COL_CAJAS and l.cajas:
                    item.setToolTip("En cajas: " + " · ".join(f"{codigo} ×{n}" for codigo, n in l.cajas))
                if col == self.COL_SURTIR and l.surtir:
                    item.setForeground(QBrush(QColor("#1d4ed8")))
                    fuente = item.font()
                    fuente.setBold(True)
                    item.setFont(fuente)
                if col == 2 and l.conto == 0:
                    item.setForeground(QBrush(QColor("#b91c1c")))
                self._table.setItem(fila, col, item)
        self._pintando = False

    def _pedido_editado(self, item: QTableWidgetItem) -> None:
        if self._pintando or item.column() != self.COL_PEDIDO:
            return
        conteo_id = item.data(Qt.ItemDataRole.UserRole)
        texto = item.text().strip()
        if texto == "":
            self._pedidos[conteo_id] = None
        else:
            try:
                self._pedidos[conteo_id] = max(0, int(texto))
            except ValueError:
                self._pintando = True
                item.setText("" if self._pedidos.get(conteo_id) is None else str(self._pedidos[conteo_id]))
                self._pintando = False
                return
        self._resumen()

    # --- acciones ------------------------------------------------------------------
    def _guardar_pedidos(self, *, avisar: bool = True) -> bool:
        if self._revision is None:
            return False
        from pos_uniformes.database.models import ConteoJornada
        from pos_uniformes.services.revision_service import guardar_pedidos

        session = self._session_factory()
        try:
            j = session.get(ConteoJornada, self._jornada.id)
            n = guardar_pedidos(session, j, dict(self._pedidos), decidido_por=self._revisada_por)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            QMessageBox.critical(self, "No se guardó el pedido", str(exc))
            return False
        finally:
            session.close()
        if avisar:
            QMessageBox.information(self, "Pedido guardado", f"Quedó tu pedido en {n} tallas. La próxima revisión lo va a recordar.")
        return True

    def _revision_con_pedidos(self):
        """La revisión con lo que Daniel tiene escrito ahora (sin guardar)."""
        from dataclasses import replace

        r = self._revision
        lineas = [replace(l, pedido=self._pedidos.get(l.conteo_id)) for l in r.lineas]
        return replace(r, lineas=lineas)

    def _hoja_de_pedido(self) -> None:
        if self._revision is None:
            return
        from pos_uniformes.services.revision_service import html_pedido, texto_pedido

        r = self._revision_con_pedidos()
        PedidoHojaDialog(self, texto=texto_pedido(r), html=html_pedido(r), titulo=f"Pedido · {r.titulo}").exec()

    def _doble_clic(self, item: QTableWidgetItem) -> None:
        # En Pedido el doble clic edita; en cualquier otra columna abre la historia.
        if item.column() != self.COL_PEDIDO:
            self._historia(item.row())

    def _historia(self, fila: int | None = None) -> None:
        if self._revision is None:
            return
        if fila is None or fila is False:
            fila = self._table.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Historia", "Elige una talla en la tabla.")
            return
        conteo_id = self._table.item(fila, 0).data(Qt.ItemDataRole.UserRole)
        linea = next((l for l in self._revision.lineas if l.conteo_id == conteo_id), None)
        if linea is None:
            return
        TallaHistoriaDialog(self, variante_id=linea.variante_id, titulo=self._revision.titulo, session_factory=self._session_factory).exec()

    def _historia_escuela(self) -> None:
        EscuelaHistoriaDialog(
            self, escuela_id=self._jornada.escuela_id, tipo_pieza=getattr(self._jornada, "tipo_pieza", "") or "",
            session_factory=self._session_factory,
        ).exec()

    def _aplicar(self) -> None:
        if self._revision is None:
            return
        n = len(self._revision.lineas)
        r = QMessageBox.question(
            self, "Aplicar al inventario",
            f"El inventario quedará como lo contó {self._revision.quien} ({n} tallas) y se guarda tu pedido.\n\n¿Aplicar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        if not self._guardar_pedidos(avisar=False):
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


class PedidoHojaDialog(QDialog):
    """El pedido listo para el maquilador: se copia, se imprime o se manda por Telegram."""

    def __init__(self, parent: QWidget | None, *, texto: str, html: str, titulo: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setStyleSheet(_ESTILO)
        self._texto = texto
        self._html = html
        self._titulo = titulo
        layout = QVBoxLayout()
        ayuda = QLabel("Cópialo al WhatsApp del maquilador, imprímelo o mándatelo por Telegram.")
        ayuda.setWordWrap(True)
        layout.addWidget(ayuda)
        self._cuadro = QPlainTextEdit(texto)
        self._cuadro.setReadOnly(True)
        self._cuadro.setStyleSheet("background: #ffffff; color: #1a1a1a; font-family: Menlo, Consolas, monospace; font-size: 13px;")
        layout.addWidget(self._cuadro, 1)
        botones = QHBoxLayout()
        copiar = QPushButton("Copiar")
        copiar.clicked.connect(self._copiar)
        botones.addWidget(copiar)
        imprimir = QPushButton("Imprimir")
        imprimir.clicked.connect(self._imprimir)
        botones.addWidget(imprimir)
        self._telegram_btn = QPushButton("Mandar por Telegram")
        self._telegram_btn.clicked.connect(self._telegram)
        botones.addWidget(self._telegram_btn)
        botones.addStretch()
        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("primaryButton")
        cerrar.clicked.connect(self.accept)
        botones.addWidget(cerrar)
        layout.addLayout(botones)
        self.setLayout(layout)
        self.resize(520, 560)

    def _copiar(self) -> None:
        QApplication.clipboard().setText(self._texto)
        self._cuadro.selectAll()

    def _imprimir(self) -> None:
        from pos_uniformes.ui.helpers.conteo_hoja_carta_print_helper import imprimir_hoja_carta

        imprimir_hoja_carta(self, self._html, self._titulo)

    def _telegram(self) -> None:
        from pos_uniformes.services.telegram_service import enviar_mensaje, token_configurado

        if not token_configurado():
            QMessageBox.information(self, "Telegram", "Esta PC no tiene configurado el bot de Telegram.")
            return
        try:
            enviar_mensaje(self._texto)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Telegram", f"No se pudo mandar:\n{exc}")
            return
        self._telegram_btn.setText("Enviado ✓")
        self._telegram_btn.setEnabled(False)


class SemanasWidget(QWidget):
    """Barras por semana: vendidas (café) y encima lo que pidieron y no había (rojo)."""

    def __init__(self, semanas=(), parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.semanas = list(semanas)
        self.setMinimumHeight(170)

    def poner(self, semanas) -> None:
        self.semanas = list(semanas)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        if not self.semanas:
            p.setPen(QColor("#8a8a8a"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin ventas registradas")
            return
        margen_izq, margen_inf, margen_sup = 8, 26, 22
        ancho = (self.width() - margen_izq * 2) / len(self.semanas)
        alto_util = self.height() - margen_inf - margen_sup
        tope = max(1, max(s.vendidas + s.pidieron for s in self.semanas))
        p.setPen(QPen(QColor("#e5e5e5"), 1))
        p.drawLine(margen_izq, self.height() - margen_inf, self.width() - margen_izq, self.height() - margen_inf)
        for i, sem in enumerate(self.semanas):
            x = margen_izq + i * ancho + ancho * 0.18
            w = ancho * 0.64
            base = self.height() - margen_inf
            h_v = alto_util * sem.vendidas / tope
            h_p = alto_util * sem.pidieron / tope
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor("#87492c")))
            p.drawRect(QRectF(x, base - h_v, w, h_v))
            p.setBrush(QBrush(QColor("#c0392b")))
            p.drawRect(QRectF(x, base - h_v - h_p, w, h_p))
            total = sem.vendidas + sem.pidieron
            p.setPen(QColor("#1a1a1a"))
            if total:
                p.drawText(QRectF(x - 10, base - h_v - h_p - 18, w + 20, 16), Qt.AlignmentFlag.AlignCenter, str(total))
            p.setPen(QColor("#6b6b6b"))
            p.drawText(QRectF(x - 12, base + 4, w + 24, 18), Qt.AlignmentFlag.AlignCenter, sem.etiqueta)


class TallaHistoriaDialog(QDialog):
    """Cómo ha evolucionado una talla: ventas por semana y cada conteo con lo
    que se pidió y lo que se vendió después."""

    def __init__(self, parent: QWidget | None = None, *, variante_id: int, titulo: str = "", session_factory: Callable[[], Session] | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(_ESTILO)
        self._session_factory = session_factory or _default_session_factory
        self._variante_id = variante_id
        self._titulo = titulo
        self.historia = None

        layout = QVBoxLayout()
        layout.setSpacing(10)
        self._encabezado = QLabel("")
        self._encabezado.setStyleSheet("font-size: 15px; font-weight: 600; color: #5c3019;")
        layout.addWidget(self._encabezado)
        self._resumen = QLabel("")
        self._resumen.setWordWrap(True)
        layout.addWidget(self._resumen)
        leyenda = QLabel("Ventas por semana · <span style='color:#87492c'>■ vendidas</span> · <span style='color:#c0392b'>■ pidieron y no había</span>")
        layout.addWidget(leyenda)
        self._grafica = SemanasWidget()
        layout.addWidget(self._grafica)

        layout.addWidget(QLabel("Conteos"))
        self._tabla = QTableWidget()
        self._tabla.setColumnCount(6)
        self._tabla.setHorizontalHeaderLabels(["Fecha", "Contó", "Quién", "Sugerido", "Pediste", "Vendidas después"])
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.setShowGrid(False)
        h = self._tabla.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for c in (0, 1, 3, 4, 5):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._tabla, 1)

        botones = QHBoxLayout()
        botones.addStretch()
        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("primaryButton")
        cerrar.clicked.connect(self.accept)
        botones.addWidget(cerrar)
        layout.addLayout(botones)
        self.setLayout(layout)
        self.resize(720, 620)
        self._cargar()

    def _cargar(self) -> None:
        from pos_uniformes.services.conteo_hoja_carta_service import nombre_para_hoja
        from pos_uniformes.services.revision_service import historia_de_talla

        session = self._session_factory()
        try:
            self.historia = historia_de_talla(session, self._variante_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Error", f"No se pudo leer la historia:\n{exc}")
            return
        finally:
            session.close()
        h = self.historia
        nombre = nombre_para_hoja(h.producto, self._titulo)
        talla = f"{h.talla} {h.color}".strip() if h.color and h.color.upper() not in ("UNICO", "ÚNICO") else h.talla
        self.setWindowTitle(f"Historia · {nombre} · {talla}")
        self._encabezado.setText(f"{nombre} · talla {talla}")
        piezas = f"<b>{h.vendidas_total}</b> vendidas en {len(h.semanas)} semanas"
        pedidas = f" · has pedido <b>{h.pedido_total}</b> en total" if h.pedido_total else ""
        conteos = f" · <b>{len(h.conteos)}</b> conteos" if h.conteos else " · nunca se ha contado"
        self._resumen.setText(piezas + pedidas + conteos)
        self._grafica.poner(h.semanas if h.vendidas_total or any(s.pidieron for s in h.semanas) else [])
        self._tabla.setRowCount(len(h.conteos))
        for fila, c in enumerate(h.conteos):
            valores = (
                c.fecha.strftime("%d/%m/%Y"),
                str(c.conto),
                c.quien,
                "—" if c.sugerido is None else str(c.sugerido),
                "—" if c.pedido is None else str(c.pedido),
                "—" if c.vendidas_despues is None else str(c.vendidas_despues),
            )
            for col, txt in enumerate(valores):
                item = QTableWidgetItem(txt)
                if col != 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 4 and c.pedido:
                    fuente = item.font()
                    fuente.setBold(True)
                    item.setFont(fuente)
                self._tabla.setItem(fila, col, item)


class EscuelaHistoriaDialog(QDialog):
    """Cómo se ha vendido una escuela: piezas por semana y, por prenda y
    talla, qué se pide más y qué menos. Lo pidió Daniel el 2026-09-13:
    "más que historial de talla me viene bien un historial de escuela"."""

    def __init__(self, parent: QWidget | None = None, *, escuela_id: int | None, tipo_pieza: str = "", session_factory: Callable[[], Session] | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(_ESTILO)
        self._session_factory = session_factory or _default_session_factory
        self._escuela_id = escuela_id
        self._tipo_pieza = tipo_pieza
        self.historia = None

        layout = QVBoxLayout()
        layout.setSpacing(10)
        self._encabezado = QLabel("")
        self._encabezado.setStyleSheet("font-size: 15px; font-weight: 600; color: #5c3019;")
        layout.addWidget(self._encabezado)
        self._resumen = QLabel("")
        self._resumen.setWordWrap(True)
        layout.addWidget(self._resumen)
        layout.addWidget(QLabel("Piezas por semana · <span style='color:#87492c'>■ vendidas</span> · <span style='color:#c0392b'>■ pidieron y no había</span>"))
        self._grafica = SemanasWidget()
        layout.addWidget(self._grafica)

        fila = QHBoxLayout()
        fila.addWidget(QLabel("Por prenda y talla, de lo que más se vende a lo que menos"))
        fila.addStretch()
        self._solo_prendas = QPushButton("Ver tallas")
        self._solo_prendas.setCheckable(True)
        self._solo_prendas.toggled.connect(self._pintar)
        fila.addWidget(self._solo_prendas)
        layout.addLayout(fila)
        self._tabla = QTableWidget()
        self._tabla.setColumnCount(7)
        self._tabla.setHorizontalHeaderLabels(["Prenda", "Talla", "Vendidas", "% del total", "Pidieron", "A la mano", "En cajas"])
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.setShowGrid(False)
        h = self._tabla.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 7):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._tabla, 1)

        botones = QHBoxLayout()
        botones.addStretch()
        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("primaryButton")
        cerrar.clicked.connect(self.accept)
        botones.addWidget(cerrar)
        layout.addLayout(botones)
        self.setLayout(layout)
        self.resize(900, 680)
        self._cargar()

    def _cargar(self) -> None:
        from pos_uniformes.services.revision_service import historia_de_escuela

        session = self._session_factory()
        try:
            self.historia = historia_de_escuela(session, self._escuela_id, self._tipo_pieza)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Error", f"No se pudo leer la historia:\n{exc}")
            return
        finally:
            session.close()
        h = self.historia
        self.setWindowTitle(f"Historia · {h.titulo}")
        self._encabezado.setText(h.titulo)
        partes = [f"<b>{h.vendidas_total}</b> piezas vendidas en {len(h.semanas)} semanas"]
        if h.pidieron_total:
            partes.append(f"<span style='color:#b91c1c'><b>{h.pidieron_total}</b> pidieron y no había</span>")
        if h.pedido_total:
            partes.append(f"has pedido <b>{h.pedido_total}</b>")
        if h.vendidas_total and h.prendas:
            partes.append(f"<b>{h.prendas_del_80}</b> de {len(h.prendas)} prendas hacen el 80 % de lo vendido")
        self._resumen.setText(" · ".join(partes))
        self._grafica.poner(h.semanas if h.vendidas_total or h.pidieron_total else [])
        self._pintar()

    def _pintar(self, *_a) -> None:
        if self.historia is None:
            return
        from pos_uniformes.services.conteo_hoja_carta_service import nombre_para_hoja

        h = self.historia
        con_tallas = self._solo_prendas.isChecked()
        self._solo_prendas.setText("Solo prendas" if con_tallas else "Ver tallas")
        filas = []
        for p in h.prendas:
            filas.append((p, None))
            if con_tallas:
                for t in p.tallas:
                    filas.append((p, t))
        self._tabla.setRowCount(len(filas))
        total = h.vendidas_total or 0
        for i, (p, t) in enumerate(filas):
            if t is None:
                pct = f"{100 * p.vendidas / total:.0f} %" if total and p.vendidas else "—"
                valores = (nombre_para_hoja(p.producto, h.titulo), "", str(p.vendidas), pct, str(p.pidieron) if p.pidieron else "—", str(p.a_la_mano), str(p.en_cajas) if p.en_cajas else "—")
            else:
                talla = f"{t.talla} {t.color}".strip() if t.color and t.color.upper() not in ("UNICO", "ÚNICO") else t.talla
                pct = f"{100 * t.vendidas / total:.0f} %" if total and t.vendidas else "—"
                valores = ("", talla, str(t.vendidas) if t.vendidas else "—", pct, str(t.pidieron) if t.pidieron else "—", str(t.a_la_mano), str(t.en_cajas) if t.en_cajas else "—")
            for col, txt in enumerate(valores):
                item = QTableWidgetItem(txt)
                if col:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if t is None:
                    fuente = item.font()
                    fuente.setBold(True)
                    item.setFont(fuente)
                    if con_tallas:
                        item.setBackground(QBrush(QColor("#f5ebe0")))
                if col == 4 and ((t is None and p.pidieron) or (t is not None and t.pidieron)):
                    item.setForeground(QBrush(QColor("#b91c1c")))
                self._tabla.setItem(i, col, item)


class ConteoDestinoDialog(QDialog):
    """¿A qué impresora va la hoja? Lo decide quien imprime, cada vez.

    Dos botones grandes: **carta** (la HP, tarjetas con Talla · Exist. ·
    Pedido de a tres por fila) o **tira** (la impresora de tickets, una tira
    por prenda). La tira es el respaldo cuando la HP falla.
    """

    CARTA = "carta"
    TIRA = "tira"

    def __init__(self, parent: QWidget | None = None, *, titulo: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("¿En qué impresora?")
        self.setStyleSheet(_ESTILO)
        self.destino: str = ""

        layout = QVBoxLayout()
        layout.setSpacing(10)
        encabezado = QLabel(f"Hoja de conteo · {titulo}" if titulo else "Hoja de conteo")
        encabezado.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(encabezado)
        pregunta = QLabel("¿Dónde la imprimo?")
        pregunta.setStyleSheet("color: #8a7a68; font-size: 12px;")
        layout.addWidget(pregunta)

        fila = QHBoxLayout()
        fila.setSpacing(10)
        carta = QPushButton("🖨  Hoja carta\n(HP, tres prendas por hoja)")
        carta.setObjectName("primaryButton")
        carta.setMinimumSize(210, 74)
        carta.clicked.connect(lambda: self._elegir(self.CARTA))
        fila.addWidget(carta)
        tira = QPushButton("🧾  Tira de tickets\n(una tira por prenda)")
        tira.setMinimumSize(210, 74)
        tira.clicked.connect(lambda: self._elegir(self.TIRA))
        fila.addWidget(tira)
        layout.addLayout(fila)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)
        self.setLayout(layout)

    def _elegir(self, destino: str) -> None:
        self.destino = destino
        self.accept()
