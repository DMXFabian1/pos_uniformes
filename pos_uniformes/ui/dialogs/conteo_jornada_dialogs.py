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
    QFrame,
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


_ESTILO_TARJETAS = """
    QFrame#tarjetaFiltro { background: #ffffff; border: 1.5px solid #e5d9cd; border-radius: 12px; }
    QFrame#tarjetaFiltro[prendida="si"] { background: #87492c; border-color: #87492c; }
    QFrame#tarjetaFiltro[prendida="si"][clave="URGENTE"] { background: #b91c1c; border-color: #b91c1c; }
    QFrame#tarjetaFiltro[prendida="si"][clave="SURTIR"] { background: #1d4ed8; border-color: #1d4ed8; }
    QFrame#tarjetaFiltro:disabled { background: #faf7f3; }
    QFrame#tarjetaFiltro QLabel { background: transparent; color: #5c3019; }
    QFrame#tarjetaFiltro[prendida="si"] QLabel { color: #ffffff; }
    QFrame#tarjetaFiltro:disabled QLabel { color: #b9a89b; }
    QLabel#tarjetaTitulo { font-size: 11px; font-weight: 700; letter-spacing: 1px; }
    QLabel#tarjetaValor { font-size: 26px; font-weight: 800; }
    QLabel#tarjetaSub { font-size: 11px; }
    QLabel#porQue { background: #f5ebe0; color: #2c2a27; border-radius: 8px; padding: 8px 12px; font-size: 13px; }
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
        self.prenda: str = ""   # básicos: una sola prenda (nombre del producto); "" = todo el tipo
        self.titulo: str = ""   # "Práxedis Guerrero" o "Básicos · Camisa", para rotular

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.addWidget(QLabel("¿Qué vas a contar?"))
        self._escuela_combo = QComboBox()
        self._escuela_combo.currentIndexChanged.connect(self._on_escuela)
        layout.addWidget(self._escuela_combo)
        self._tipo_combo = QComboBox()
        self._tipo_combo.setVisible(False)
        self._tipo_combo.currentIndexChanged.connect(self._on_tipo)
        layout.addWidget(self._tipo_combo)
        # Tercer nivel (básicos): todas las prendas del tipo, o una sola —
        # "a veces no quiero contar todos los pantalones" (Daniel 2026-09-14).
        self._prenda_combo = QComboBox()
        self._prenda_combo.setVisible(False)
        self._prenda_combo.currentIndexChanged.connect(self._pintar_ultimo)
        layout.addWidget(self._prenda_combo)
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
            return ultimo_conteo_de(self._ultimos, None, str(self._tipo_combo.currentData() or ""), str(self._prenda_combo.currentData() or ""))
        return ultimo_conteo_de(self._ultimos, int(dato))

    def abierta_elegida(self):
        """La JornadaRef en proceso de lo seleccionado, o None."""
        dato = self._escuela_combo.currentData()
        if dato is None:
            return None
        if int(dato) == ESCUELA_ID_BASICOS:
            from pos_uniformes.services.conteo_jornada_service import clave_alcance

            tipo = str(self._tipo_combo.currentData() or "")
            prenda = str(self._prenda_combo.currentData() or "")
            # Una prenda choca con la de todo el tipo; todo el tipo, con cualquier prenda abierta.
            if prenda:
                return self._abiertas.get(clave_alcance(None, tipo, prenda)) or self._abiertas.get(("basicos", tipo))
            return self._abiertas.get(("basicos", tipo)) or next(
                (j for k, j in self._abiertas.items() if isinstance(k, tuple) and len(k) == 3 and k[1] == tipo), None
            )
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
        if not es_basicos:
            self._prenda_combo.setVisible(False)
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
                u = ultimo_conteo_de(self._ultimos, None, t)
                if abierta is None and u.reciente() and not self._ver_todas.isChecked():
                    continue
                estado = f"EN PROCESO ({abierta.quien})" if abierta is not None else u.texto()
                self._tipo_combo.addItem(f"{t}   ·  {estado}", t)
        self._on_tipo()

    def _on_tipo(self, *_args) -> None:
        """Llena el combo de prendas del tipo elegido, cada una con su última fecha."""
        from pos_uniformes.services.conteo_jornada_service import nombre_corto_prenda, prendas_basicas, ultimo_conteo_de

        tipo = str(self._tipo_combo.currentData() or "")
        es_basicos = self._escuela_combo.currentData() == ESCUELA_ID_BASICOS
        self._prenda_combo.blockSignals(True)
        self._prenda_combo.clear()
        if es_basicos and tipo:
            u_tipo = ultimo_conteo_de(self._ultimos, None, tipo)
            self._prenda_combo.addItem(f"Todas las de {tipo}   ·  {u_tipo.texto()}", "")
            session = self._session_factory()
            try:
                prendas = prendas_basicas(session, tipo)
            except Exception:  # noqa: BLE001
                prendas = []
            finally:
                session.close()
            for prenda in prendas:
                abierta = self._abiertas.get(("basicos", tipo, prenda))
                u = ultimo_conteo_de(self._ultimos, None, tipo, prenda)
                estado = f"EN PROCESO ({abierta.quien})" if abierta is not None else u.texto()
                self._prenda_combo.addItem(f"{nombre_corto_prenda(prenda)}   ·  {estado}", prenda)
        self._prenda_combo.setVisible(es_basicos and self._prenda_combo.count() > 1)
        self._prenda_combo.blockSignals(False)
        self._pintar_ultimo()

    def _aceptar(self) -> None:
        dato = self._escuela_combo.currentData()
        if dato is None:
            return
        if int(dato) == ESCUELA_ID_BASICOS:
            tipo = self._tipo_combo.currentData()
            if not tipo:
                QMessageBox.information(self, "Elige una prenda", "Los básicos se cuentan por prenda: elige cuál.")
                return
            from pos_uniformes.services.conteo_jornada_service import nombre_corto_prenda

            self.escuela_id = None
            self.tipo_pieza = str(tipo)
            self.prenda = str(self._prenda_combo.currentData() or "")
            self.titulo = f"Básicos · {nombre_corto_prenda(self.prenda)}" if self.prenda else f"Básicos · {tipo}"
        else:
            self.escuela_id = int(dato)
            self.tipo_pieza = ""
            self.titulo = self._escuela_combo.currentText().split("   ·  ")[0].strip()
        self.accept()


class _TarjetaFiltro(QFrame):
    """Tarjeta tipo Libreta (título chico, número grande, línea chica) que
    además es un filtro: se prende y apaga al tocarla."""

    def __init__(self, clave: str, titulo: str, al_cambiar) -> None:
        super().__init__()
        self.clave = clave
        self._checked = False
        self._enabled = True
        self._al_cambiar = al_cambiar
        self.setObjectName("tarjetaFiltro")
        self.setProperty("clave", clave)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        ly = QVBoxLayout()
        ly.setContentsMargins(14, 10, 14, 10)
        ly.setSpacing(2)
        self._titulo = QLabel(titulo)
        self._titulo.setObjectName("tarjetaTitulo")
        self._valor = QLabel("0")
        self._valor.setObjectName("tarjetaValor")
        self._sub = QLabel("")
        self._sub.setObjectName("tarjetaSub")
        for w in (self._titulo, self._valor, self._sub):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ly.addWidget(w)
        self.setLayout(ly)
        self._repintar()

    def poner(self, valor: int, sub: str) -> None:
        self._valor.setText(str(valor))
        self._sub.setText(sub)
        self.setEnabled(valor > 0)

    def setEnabled(self, on: bool) -> None:  # noqa: N802
        self._enabled = bool(on)
        super().setEnabled(on)
        self._repintar()

    def isEnabled(self) -> bool:  # noqa: N802
        return self._enabled

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, on: bool) -> None:  # noqa: N802
        if self._checked == bool(on):
            return
        self._checked = bool(on)
        self._repintar()
        self._al_cambiar()

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if self._enabled and e.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def _repintar(self) -> None:
        self.setProperty("prendida", "si" if self._checked else "no")
        self.style().unpolish(self)
        self.style().polish(self)
        for w in (self._titulo, self._valor, self._sub):
            w.style().unpolish(w)
            w.style().polish(w)


class ConteoRevisionDialog(QDialog):
    """Revisar = decidir qué pedir. Primero la decisión, después la evidencia.

    Arriba cuatro tarjetas (URGENTE · PEDIR · SURTIR · BIEN) que filtran; la
    tabla compacta dice por talla cuántas hay, **qué hacer** y el Pedido
    editable; al tocar una talla, debajo aparece **por qué** en una línea.
    "Ver todas las columnas" trae la tabla completa. Aplicar al inventario
    también guarda los pedidos: un solo gesto.
    """

    COLUMNAS_COMPLETAS = ("Prenda", "Talla", "A la mano", "En cajas", "Vendidas", "Ritmo/sem", "Alcanza", "Pidieron", "Hoja", "Surtir", "Sugerido", "Pedido", "La vez pasada")
    COLUMNAS_COMPACTAS = ("Prenda", "Talla", "Hay", "Qué hacer", "Pedido")
    _FILTROS = ("URGENTE", "PEDIR", "SURTIR", "OTRAS")

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
        self.setStyleSheet(_ESTILO + _ESTILO_TARJETAS)
        self._session_factory = session_factory or _default_session_factory
        self._jornada = jornada
        self._revisada_por = revisada_por
        self.resultado: str = ""   # "aplicada" | "descartada" | ""
        self._revision = None
        self._pedidos: dict[int, int | None] = {}   # conteo_id → lo que Daniel escribió
        self._pintando = False
        self._por_fila: dict[int, int] = {}          # fila → conteo_id (las de prenda no están)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        self._resumen_label = QLabel("")
        self._resumen_label.setWordWrap(True)
        self._resumen_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self._resumen_label)

        # Las cuatro tarjetas: cifra grande, y son el filtro.
        tarjetas = QHBoxLayout()
        tarjetas.setSpacing(10)
        self._tarjetas: dict[str, _TarjetaFiltro] = {}
        for clave, titulo in (("URGENTE", "URGENTE"), ("PEDIR", "PEDIR"), ("SURTIR", "SURTIR DE CAJAS"), ("OTRAS", "BIEN / SIN DATOS")):
            b = _TarjetaFiltro(clave, titulo, self._pintar)
            self._tarjetas[clave] = b
            tarjetas.addWidget(b, 1)
        layout.addLayout(tarjetas)

        self._table = QTableWidget()
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.SelectedClicked
            | QTableWidget.EditTrigger.AnyKeyPressed
        )
        self._table.itemChanged.connect(self._pedido_editado)
        self._table.itemDoubleClicked.connect(self._doble_clic)
        self._table.itemSelectionChanged.connect(self._por_que)
        layout.addWidget(self._table, 1)

        # Por qué: la evidencia de la talla tocada, en una línea.
        self._por_que_label = QLabel("Toca una talla para ver por qué se sugiere eso.")
        self._por_que_label.setObjectName("porQue")
        self._por_que_label.setWordWrap(True)
        layout.addWidget(self._por_que_label)

        acciones = QHBoxLayout()
        self._completo = QPushButton("Ver todas las columnas")
        self._completo.setCheckable(True)
        self._completo.setAutoDefault(False)
        self._completo.toggled.connect(self._pintar)
        acciones.addWidget(self._completo)
        self._historia_btn = QPushButton("Historia de la talla")
        self._historia_btn.setAutoDefault(False)
        self._historia_btn.clicked.connect(self._historia)
        acciones.addWidget(self._historia_btn)
        self._escuela_btn = QPushButton("Historia de la escuela")
        self._escuela_btn.setAutoDefault(False)
        self._escuela_btn.clicked.connect(self._historia_escuela)
        acciones.addWidget(self._escuela_btn)
        self._comparar_btn = QPushButton("Comparar con el anterior")
        self._comparar_btn.setAutoDefault(False)
        self._comparar_btn.clicked.connect(self._comparar)
        acciones.addWidget(self._comparar_btn)
        acciones.addStretch()
        descartar = QPushButton("Descartar")
        descartar.setObjectName("dangerButton")
        descartar.setAutoDefault(False)
        descartar.clicked.connect(self._descartar)
        acciones.addWidget(descartar)
        self._guardar_btn = QPushButton("Guardar pedido")
        self._guardar_btn.setAutoDefault(False)
        self._guardar_btn.clicked.connect(self._guardar_pedidos)
        acciones.addWidget(self._guardar_btn)
        self._hoja_btn = QPushButton("Hoja de pedido")
        self._hoja_btn.setAutoDefault(False)
        self._hoja_btn.clicked.connect(self._hoja_de_pedido)
        acciones.addWidget(self._hoja_btn)
        self._aplicar_btn = QPushButton("Aplicar al inventario")
        self._aplicar_btn.setObjectName("primaryButton")
        self._aplicar_btn.setAutoDefault(False)
        self._aplicar_btn.clicked.connect(self._aplicar)
        acciones.addWidget(self._aplicar_btn)
        cerrar = QPushButton("Cerrar")
        cerrar.setAutoDefault(False)
        cerrar.clicked.connect(self.reject)
        acciones.addWidget(cerrar)
        layout.addLayout(acciones)
        self.setLayout(layout)
        self.resize(1040, 680)
        self._cargar()

    # --- compatibilidad con lo que había ------------------------------------------
    @property
    def COL_PEDIDO(self) -> int:  # noqa: N802 — nombre heredado
        return len(self._columnas()) - 1 if not self._completo.isChecked() else 11

    def _columnas(self) -> tuple:
        return self.COLUMNAS_COMPLETAS if self._completo.isChecked() else self.COLUMNAS_COMPACTAS

    # --- datos ---------------------------------------------------------------------
    def _cargar(self) -> None:
        from pos_uniformes.database.models import ConteoJornada
        from pos_uniformes.services.revision_service import PEDIR, SURTIR, URGENTE, revisar

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
        # Filtro inicial: lo que pide acción. Si no hay nada de eso, todas.
        hay_accion = any(l.estado in (URGENTE, PEDIR, SURTIR) for l in self._revision.lineas)
        self._pintando = True
        for clave, b in self._tarjetas.items():
            b.setChecked(clave != "OTRAS" if hay_accion else True)
        self._pintando = False
        self._resumen()
        self._pintar()

    def _conteo(self, clave: str) -> tuple[int, int, int]:
        """(tallas, piezas sugeridas, piezas a surtir) de un grupo del filtro."""
        from pos_uniformes.services.revision_service import PEDIR, SURTIR, URGENTE

        grupo = {"URGENTE": (URGENTE,), "PEDIR": (PEDIR,), "SURTIR": (SURTIR,)}.get(clave)
        lineas = [l for l in self._revision.lineas if (l.estado in grupo if grupo else l.estado not in (URGENTE, PEDIR, SURTIR))]
        return len(lineas), sum(l.sugerido for l in lineas), sum(l.surtir for l in lineas)

    def _resumen(self) -> None:
        r = self._revision
        piezas = sum(p for p in self._pedidos.values() if p)
        tallas = sum(1 for p in self._pedidos.values() if p)
        texto = f"<b>{r.quien}</b> contó <b>{len(r.lineas)}</b> tallas de <b>{r.titulo}</b>  ·  tu pedido va en <b>{piezas}</b> piezas en {tallas} tallas"
        if not r.lineas:
            texto += "<br><span style='color:#8a8a8a'>Esta jornada no tiene tallas capturadas.</span>"
        elif not any(l.estado in ("URGENTE", "PEDIR", "SURTIR") for l in r.lineas):
            texto += "<br><span style='color:#8a8a8a'>Nada que pedir ni surtir todavía (faltan ventas para sacar el ritmo).</span>"
        self._resumen_label.setText(texto)
        self._hoja_btn.setEnabled(piezas > 0)
        # Las tarjetas: cifra grande + una línea chica.
        for clave, b in self._tarjetas.items():
            n, sug, sur = self._conteo(clave)
            if clave == "URGENTE":
                sub = "no hay y la piden" if n else "ninguna"
            elif clave == "PEDIR":
                sub = f"{sug} piezas al maquilador" if n else "nada"
            elif clave == "SURTIR":
                sub = f"{sur} piezas de las cajas" if n else "nada"
            else:
                sub = "tallas que están bien o sin datos"
            b.poner(n, sub)

    def _lineas_visibles(self):
        from pos_uniformes.services.revision_service import PEDIR, SURTIR, URGENTE

        activos = {k for k, b in self._tarjetas.items() if b.isChecked() and b.isEnabled()}
        if not activos:
            return list(self._revision.lineas)
        grupo_de = {URGENTE: "URGENTE", PEDIR: "PEDIR", SURTIR: "SURTIR"}
        return [l for l in self._revision.lineas if grupo_de.get(l.estado, "OTRAS") in activos or self._pedidos.get(l.conteo_id)]

    def _filtro_sin_efecto(self) -> bool:
        return bool(self._revision.lineas) and not any(l.estado in ("URGENTE", "PEDIR", "SURTIR") for l in self._revision.lineas)

    # --- pintura -------------------------------------------------------------------
    def _que_hacer(self, l) -> str:
        from pos_uniformes.services.revision_service import NO_SE_MUEVE, SIN_DATOS, URGENTE

        if l.estado == SIN_DATOS:
            return "sin datos"
        if l.estado == NO_SE_MUEVE:
            return "no se mueve"
        partes = []
        if l.sugerido:
            partes.append(f"pedir {l.sugerido}")
        if l.surtir:
            partes.append(f"surtir {l.surtir}")
        texto = " · ".join(partes) if partes else "bien"
        return f"¡URGENTE! {texto}" if l.estado == URGENTE else texto

    def _pintar(self, *_a) -> None:
        if self._revision is None or self._pintando:
            return
        from pos_uniformes.services.conteo_hoja_carta_service import nombre_para_hoja
        from pos_uniformes.services.revision_service import NO_SE_MUEVE, SIN_DATOS, SURTIR, URGENTE

        self._pintando = True
        columnas = self._columnas()
        self._table.clear()
        self._table.setColumnCount(len(columnas))
        self._table.setHorizontalHeaderLabels(list(columnas))
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, len(columnas)):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        lineas = self._lineas_visibles()
        compacto = not self._completo.isChecked()
        col_pedido = self.COL_PEDIDO
        self._por_fila = {}

        # Compacto: agrupado por prenda con una fila de encabezado por prenda.
        filas: list = []
        if compacto:
            grupos: dict[str, list] = {}
            for l in lineas:
                grupos.setdefault(l.producto, []).append(l)
            for producto, tallas in grupos.items():
                filas.append(("prenda", producto, tallas))
                filas.extend(("talla", l, None) for l in tallas)
        else:
            filas = [("talla", l, None) for l in lineas]
        self._table.setRowCount(len(filas))

        for fila, (tipo, dato, extra) in enumerate(filas):
            if tipo == "prenda":
                sug = sum(l.sugerido for l in extra)
                sur = sum(l.surtir for l in extra)
                resumen = " · ".join(p for p in (f"pedir {sug}" if sug else "", f"surtir {sur}" if sur else "") if p)
                item = QTableWidgetItem(nombre_para_hoja(dato, self._revision.titulo) + (f"   —   {resumen}" if resumen else ""))
                fuente = item.font()
                fuente.setBold(True)
                item.setFont(fuente)
                item.setBackground(QBrush(QColor("#f5ebe0")))
                item.setForeground(QBrush(QColor("#5c3019")))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self._table.setItem(fila, 0, item)
                for c in range(1, len(columnas)):
                    vacio = QTableWidgetItem("")
                    vacio.setBackground(QBrush(QColor("#f5ebe0")))
                    vacio.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    self._table.setItem(fila, c, vacio)
                self._table.setSpan(fila, 0, 1, len(columnas))
                continue

            l = dato
            self._por_fila[fila] = l.conteo_id
            pedido = self._pedidos.get(l.conteo_id)
            talla = f"{l.talla} {l.color}".strip() if l.color and l.color.upper() not in ("", "UNICO", "ÚNICO") else l.talla
            if compacto:
                hay = f"{l.conto}" + (f"  + {l.en_cajas} en cajas" if l.en_cajas else "")
                valores = ("", talla, hay, self._que_hacer(l), "" if pedido is None else str(pedido))
                col_que = 3
            else:
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
                valores = (
                    nombre_para_hoja(l.producto, self._revision.titulo), talla, str(l.conto),
                    str(l.en_cajas) if l.en_cajas else "—", vendidas,
                    f"{l.ritmo_semana:.1f}" if l.ritmo_semana else "—", alcanza,
                    str(l.pidieron) if l.pidieron else "—",
                    str(l.ellas_sugieren) if l.ellas_sugieren is not None else "—",
                    str(l.surtir) if l.surtir else "—", sugerido,
                    "" if pedido is None else str(pedido), self._la_vez_pasada(l),
                )
                col_que = 10
            for col, txt in enumerate(valores):
                item = QTableWidgetItem(txt)
                item.setData(Qt.ItemDataRole.UserRole, l.conteo_id)
                if col not in (0, len(valores) - 1) or (compacto and col == len(valores) - 1):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == col_pedido:
                    item.setBackground(QBrush(QColor("#fff8e6")))
                    fuente = item.font()
                    fuente.setBold(True)
                    item.setFont(fuente)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == col_que:
                    if l.estado == URGENTE:
                        item.setForeground(QBrush(QColor("#b91c1c")))
                    elif l.estado == SURTIR:
                        item.setForeground(QBrush(QColor("#1d4ed8")))
                    elif l.estado in (NO_SE_MUEVE, SIN_DATOS):
                        item.setForeground(QBrush(QColor("#8a8a8a")))
                    elif l.sugerido:
                        item.setForeground(QBrush(QColor("#5c3019")))
                    if compacto:
                        fuente = item.font()
                        fuente.setBold(bool(l.sugerido or l.surtir))
                        item.setFont(fuente)
                if not compacto and col == 3 and l.cajas:
                    item.setToolTip("En cajas: " + " · ".join(f"{codigo} ×{n}" for codigo, n in l.cajas))
                if compacto and col == 2 and l.cajas:
                    item.setToolTip("En cajas: " + " · ".join(f"{codigo} ×{n}" for codigo, n in l.cajas))
                if col == 2 and l.conto == 0:
                    item.setForeground(QBrush(QColor("#b91c1c")))
                self._table.setItem(fila, col, item)
        self._pintando = False
        self._por_que()

    def _la_vez_pasada(self, l) -> str:
        if l.pedido_anterior is not None:
            cuando = l.pedido_anterior_at.strftime("%d/%m") if l.pedido_anterior_at else ""
            vendio = f", vendiste {l.vendidas_desde_pedido}" if l.vendidas_desde_pedido is not None else ""
            return f"pediste {l.pedido_anterior} el {cuando}{vendio}"
        if l.anterior is not None:
            return f"había {l.anterior} el {l.anterior_at.strftime('%d/%m')}"
        return "primer conteo"

    def _linea_en_fila(self, fila: int):
        conteo_id = self._por_fila.get(fila)
        if conteo_id is None:
            return None
        return next((l for l in self._revision.lineas if l.conteo_id == conteo_id), None)

    def _por_que(self) -> None:
        """La evidencia de la talla seleccionada, en una línea."""
        if self._revision is None or self._pintando:
            return
        l = self._linea_en_fila(self._table.currentRow())
        if l is None:
            self._por_que_label.setText("Toca una talla para ver por qué se sugiere eso.")
            return
        from pos_uniformes.services.conteo_hoja_carta_service import nombre_para_hoja

        partes = []
        if l.dias_observados:
            partes.append(f"vendidas <b>{l.vendidas}</b> en {l.dias_observados} días ({l.ritmo_semana:.1f} por semana)")
            if l.semanas_cubiertas is not None:
                partes.append(f"con lo que hay alcanza <b>{l.semanas_cubiertas:g}</b> semanas")
        else:
            partes.append("sin ventas registradas todavía")
        if l.pidieron:
            partes.append(f"<span style='color:#b91c1c'>pidieron <b>{l.pidieron}</b> y no había</span>")
        if l.ellas_sugieren is not None:
            partes.append(f"en la hoja anotaron pedir {l.ellas_sugieren}")
        if l.cajas:
            partes.append("en cajas: " + " · ".join(f"{c} ×{n}" for c, n in l.cajas))
        partes.append(self._la_vez_pasada(l))
        talla = f"{l.talla} {l.color}".strip() if l.color and l.color.upper() not in ("", "UNICO", "ÚNICO") else l.talla
        self._por_que_label.setText(f"<b>{nombre_para_hoja(l.producto, self._revision.titulo)} · {talla}</b>  —  " + " · ".join(partes))

    def _pedido_editado(self, item: QTableWidgetItem) -> None:
        if self._pintando or item.column() != self.COL_PEDIDO:
            return
        conteo_id = item.data(Qt.ItemDataRole.UserRole)
        if conteo_id is None:
            return
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
        linea = self._linea_en_fila(fila) if fila >= 0 else None
        if linea is None:
            QMessageBox.information(self, "Historia", "Elige una talla en la tabla.")
            return
        TallaHistoriaDialog(self, variante_id=linea.variante_id, titulo=self._revision.titulo, session_factory=self._session_factory).exec()

    def _comparar(self) -> None:
        ConteoComparativoDialog(self, jornada_id=self._jornada.id, session_factory=self._session_factory).exec()

    def _historia_escuela(self) -> None:
        EscuelaHistoriaDialog(
            self, escuela_id=self._jornada.escuela_id, tipo_pieza=getattr(self._jornada, "tipo_pieza", "") or "",
            prenda=getattr(self._jornada, "prenda", "") or "", session_factory=self._session_factory,
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

    def __init__(self, parent: QWidget | None = None, *, escuela_id: int | None, tipo_pieza: str = "", prenda: str = "", session_factory: Callable[[], Session] | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(_ESTILO)
        self._session_factory = session_factory or _default_session_factory
        self._escuela_id = escuela_id
        self._tipo_pieza = tipo_pieza
        self._prenda = prenda
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
            self.historia = historia_de_escuela(session, self._escuela_id, self._tipo_pieza, prenda=self._prenda)
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


class ConteoComparativoDialog(QDialog):
    """Este conteo contra el anterior: cuánto había, cuánto hay, cuánto se
    vendió en medio y cuánto no se explica. Se abre desde el tablero de
    Conteos (doble clic en una escuela) y desde Revisar, aplicado o no.
    Daniel (2026-09-14): "ver cómo estuvo de diferente, qué se movió más y cuánto"."""

    def __init__(self, parent: QWidget | None = None, *, jornada_id: int, session_factory: Callable[[], Session] | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(_ESTILO + _ESTILO_TARJETAS)
        self._session_factory = session_factory or _default_session_factory
        self._jornada_id = jornada_id
        self.comparativo = None

        layout = QVBoxLayout()
        layout.setSpacing(10)
        self._encabezado = QLabel("")
        self._encabezado.setStyleSheet("font-size: 15px; font-weight: 600; color: #5c3019;")
        layout.addWidget(self._encabezado)
        self._resumen = QLabel("")
        self._resumen.setWordWrap(True)
        layout.addWidget(self._resumen)

        tarjetas = QHBoxLayout()
        tarjetas.setSpacing(10)
        self._cards: dict[str, _TarjetaFiltro] = {}
        for clave, titulo in (("ANTES", "HABÍA"), ("AHORA", "HAY"), ("VENDIDAS", "VENDIDAS EN MEDIO"), ("FALTAN", "FALTAN SIN EXPLICAR"), ("SOBRAN", "SOBRAN SIN EXPLICAR")):
            c = _TarjetaFiltro(clave, titulo, lambda: None)
            c.setCursor(Qt.CursorShape.ArrowCursor)
            c.mousePressEvent = lambda e: None   # solo informan
            self._cards[clave] = c
            tarjetas.addWidget(c, 1)
        layout.addLayout(tarjetas)

        fila = QHBoxLayout()
        fila.addWidget(QLabel("Por talla, de lo que más se movió a lo que menos"))
        fila.addStretch()
        self._solo_cambios = QPushButton("Solo lo que cambió")
        self._solo_cambios.setCheckable(True)
        self._solo_cambios.setChecked(True)
        self._solo_cambios.setAutoDefault(False)
        self._solo_cambios.toggled.connect(self._pintar)
        fila.addWidget(self._solo_cambios)
        layout.addLayout(fila)

        self._tabla = QTableWidget()
        self._tabla.setColumnCount(7)
        self._tabla.setHorizontalHeaderLabels(["Prenda", "Talla", "Había", "Hay", "Cambio", "Vendidas", "Sin explicar"])
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.setShowGrid(False)
        h = self._tabla.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 7):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._tabla, 1)

        pie = QLabel("Sin explicar = había − vendidas − hay. Positivo: faltan piezas que ninguna venta explica (merma o venta sin registrar). Negativo: sobran (llegó mercancía que no se anotó).")
        pie.setWordWrap(True)
        pie.setStyleSheet("color: #8a8a8a; font-size: 12px;")
        layout.addWidget(pie)

        botones = QHBoxLayout()
        botones.addStretch()
        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("primaryButton")
        cerrar.setAutoDefault(False)
        cerrar.clicked.connect(self.accept)
        botones.addWidget(cerrar)
        layout.addLayout(botones)
        self.setLayout(layout)
        self.resize(980, 680)
        self._cargar()

    def _cargar(self) -> None:
        from pos_uniformes.database.models import ConteoJornada
        from pos_uniformes.services.conteo_jornada_service import cuando
        from pos_uniformes.services.revision_service import comparativo_de_jornada

        session = self._session_factory()
        try:
            j = session.get(ConteoJornada, self._jornada_id)
            if j is None:
                raise ValueError("Esa jornada ya no existe.")
            self.comparativo = comparativo_de_jornada(session, j)
            terminada = cuando(j.terminada_at) if j.terminada_at else "a medias"
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Error", f"No se pudo leer el conteo:\n{exc}")
            return
        finally:
            session.close()
        c = self.comparativo
        self.setWindowTitle(f"Comparativo · {c.titulo}")
        self._encabezado.setText(f"{c.titulo}  ·  contado {terminada} por {c.quien}")
        if c.con_anterior:
            ant = c.anterior_at.strftime("%d/%m/%Y") if c.anterior_at else "antes"
            self._resumen.setText(
                f"Contra el conteo anterior del <b>{ant}</b>: <b>{len(c.con_anterior)}</b> tallas con qué comparar"
                + (f", <b>{len(c.lineas) - len(c.con_anterior)}</b> contadas por primera vez" if len(c.lineas) > len(c.con_anterior) else "") + "."
            )
        else:
            self._resumen.setText("Es el primer conteo de esta escuela: todavía no hay con qué comparar. El siguiente ya tendrá.")
        self._cards["ANTES"].poner(c.antes_total, "piezas en el conteo anterior")
        self._cards["AHORA"].poner(c.ahora_total, "piezas en este conteo")
        self._cards["VENDIDAS"].poner(c.vendidas_total, "según la Libreta")
        self._cards["FALTAN"].poner(c.faltan, "piezas que ninguna venta explica")
        self._cards["SOBRAN"].poner(c.sobran, "piezas de más")
        for k in ("ANTES", "AHORA", "VENDIDAS", "FALTAN", "SOBRAN"):
            self._cards[k].setEnabled(True)
        self._cards["FALTAN"].setChecked(c.faltan > 0)
        self._cards["FALTAN"].setProperty("clave", "URGENTE")
        self._cards["SOBRAN"].setChecked(c.sobran > 0)
        self._cards["SOBRAN"].setProperty("clave", "SURTIR")
        for k in ("FALTAN", "SOBRAN"):
            self._cards[k]._repintar()
        self._pintar()

    def _pintar(self, *_a) -> None:
        if self.comparativo is None:
            return
        from pos_uniformes.services.conteo_hoja_carta_service import nombre_para_hoja

        c = self.comparativo
        lineas = [l for l in c.lineas if not self._solo_cambios.isChecked() or l.cambio or l.vendidas]
        if not lineas:
            lineas = list(c.lineas)
        self._tabla.setRowCount(len(lineas))
        for i, l in enumerate(lineas):
            talla = f"{l.talla} {l.color}".strip() if l.color and l.color.upper() not in ("UNICO", "ÚNICO") else l.talla
            if l.antes is None:
                valores = (nombre_para_hoja(l.producto, c.titulo), talla, "—", str(l.ahora), "primer conteo", str(l.vendidas) if l.vendidas else "—", "—")
            else:
                valores = (
                    nombre_para_hoja(l.producto, c.titulo), talla, str(l.antes), str(l.ahora),
                    f"{l.cambio:+d}" if l.cambio else "=", str(l.vendidas) if l.vendidas else "—",
                    (f"faltan {l.sin_explicar}" if l.sin_explicar > 0 else f"sobran {-l.sin_explicar}") if l.sin_explicar else "cuadra",
                )
            for col, txt in enumerate(valores):
                item = QTableWidgetItem(txt)
                if col:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 4 and l.cambio:
                    item.setForeground(QBrush(QColor("#b91c1c" if l.cambio < 0 else "#166534")))
                    fuente = item.font()
                    fuente.setBold(abs(l.cambio) >= 3)
                    item.setFont(fuente)
                if col == 6 and l.sin_explicar:
                    item.setForeground(QBrush(QColor("#b91c1c" if l.sin_explicar > 0 else "#1d4ed8")))
                if col == 6 and l.antes is not None and not l.sin_explicar:
                    item.setForeground(QBrush(QColor("#8a8a8a")))
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
