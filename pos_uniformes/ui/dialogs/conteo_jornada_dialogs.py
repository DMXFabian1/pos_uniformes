"""Diálogos de la sección Conteos que giran alrededor de la jornada.

- `ConteoNuevaJornadaDialog`: qué vas a contar (escuela, o una prenda de los
  básicos). Devuelve el alcance; la ventana abre la jornada.
- `ConteoRevisionDialog`: lo que ve el dueño antes de corregir el inventario
  con una jornada terminada — qué cambia, talla por talla, en piezas y en $ —
  y la decisión: «Corregir inventario» o «No usar este conteo» (tanda 3,
  2026-11-15; lo que se decide sale de `conteo_revision_pantalla_service`).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from PyQt6.QtCore import QRect, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPalette, QPen
from PyQt6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from pos_uniformes.services.conteo_revision_pantalla_service import COL_PEDIDO as _COL_PEDIDO_REVISION
from pos_uniformes.services.conteo_revision_pantalla_service import COLUMNAS as _COLUMNAS_REVISION
from pos_uniformes.services.conteo_service import ESCUELA_ID_BASICOS, NOMBRE_BASICOS

# La misma paleta que el corte y la Libreta (2026-11-06): crema, vino y terracota.
_ESTILO = """
    QDialog { background: #f4ede2; }
    QLabel { color: #2c2a27; background: transparent; }
    QComboBox { background: #ffffff; color: #2c2a27; border: 1px solid #d9cdb8;
                border-radius: 10px; padding: 7px 12px; min-height: 30px; font-size: 14px; }
    QComboBox:focus { border: 2px solid #6b1f3a; }
    QCheckBox { color: #2c2a27; font-size: 14px; }
    QTableWidget { background: #ffffff; alternate-background-color: #faf6f0; color: #2c2a27;
                   border: 1px solid #e6dccb; border-radius: 10px; }
    QHeaderView::section { background: #f1e6d6; color: #6b1f3a; font-weight: 700;
                           border: none; padding: 8px 6px; }
    QPushButton { background: #ffffff; color: #8b4a2b; border: 1px solid #e6dccb;
                  border-radius: 10px; padding: 8px 14px; font-weight: 700; }
    QPushButton:hover { background: #f1e6d6; }
    QPushButton#primaryButton { background: #8b4a2b; color: #ffffff; border: none; font-weight: 800; }
    QPushButton#primaryButton:hover { background: #a2583a; }
    QPushButton#dangerButton { color: #b3261e; border-color: #e8c7c3; }
    QPushButton#dangerButton:hover { background: #fbeae8; }
    QPushButton:disabled, QPushButton#primaryButton:disabled, QPushButton#dangerButton:disabled {
                  background: #f6f1ea; color: #c4b5a5; border: 1px solid #ece3d8; }
"""


_ESTILO_TARJETAS = """
    QFrame#tarjetaFiltro { background: #ffffff; border: 1.5px solid #e5d9cd; border-radius: 12px; }
    QFrame#tarjetaFiltro[prendida="si"] { background: #87492c; border-color: #87492c; }
    QFrame#tarjetaFiltro[prendida="si"][clave="URGENTE"] { background: #b91c1c; border-color: #b91c1c; }
    QFrame#tarjetaFiltro[prendida="si"][clave="SURTIR"] { background: #1d4ed8; border-color: #1d4ed8; }
    QFrame#tarjetaFiltro QLabel { background: transparent; color: #5c3019; }
    QFrame#tarjetaFiltro[prendida="si"] QLabel { color: #ffffff; }
    /* Apagada (en 0) = gris y sin relleno, aunque esté «prendida»: estas reglas
       van después y con la misma especificidad que las de color (2026-11-15). */
    QFrame#tarjetaFiltro:disabled,
    QFrame#tarjetaFiltro[prendida="si"]:disabled,
    QFrame#tarjetaFiltro[prendida="si"][clave="URGENTE"]:disabled,
    QFrame#tarjetaFiltro[prendida="si"][clave="SURTIR"]:disabled { background: #faf7f3; border-color: #ece3d8; }
    QFrame#tarjetaFiltro:disabled QLabel,
    QFrame#tarjetaFiltro[prendida="si"]:disabled QLabel { color: #b9a89b; }
    QLabel#tarjetaTitulo { font-size: 11px; font-weight: 700; letter-spacing: 1px; }
    QLabel#tarjetaValor { font-size: 26px; font-weight: 800; }
    QLabel#tarjetaSub { font-size: 11px; }
    QLabel#porQue { background: #f5ebe0; color: #2c2a27; border-radius: 8px; padding: 8px 12px; font-size: 13px; }
    QLabel#cuandoConteo { color: #6b5d50; font-size: 13px; }
    QLabel#avisoViejo { background: #fdf1d8; color: #7a4d00; border: 1px solid #f0d49a;
                        border-radius: 8px; padding: 7px 12px; font-size: 13px; font-weight: 700; }
    QLabel#yaRevisada { background: #eef3ea; color: #2f5130; border: 1px solid #cfdcc8;
                        border-radius: 8px; padding: 7px 12px; font-size: 13px; font-weight: 700; }
"""


def _elegir(parent: QWidget | None, titulo: str, texto: str, opciones, *, default: str, escape: str) -> str:
    """Una pregunta con botones propios en español (nada de Yes/No).

    `opciones` = [(clave, texto del botón, QMessageBox.ButtonRole), …].
    Devuelve la clave del botón tocado; Esc o la ✕ devuelven `escape`."""
    caja = QMessageBox(parent)
    caja.setIcon(QMessageBox.Icon.Question)
    caja.setWindowTitle(titulo)
    caja.setText(texto)
    botones = {}
    for clave, etiqueta, rol in opciones:
        botones[clave] = caja.addButton(etiqueta, rol)
    caja.setDefaultButton(botones[default])
    caja.setEscapeButton(botones[escape])
    caja.exec()
    tocado = caja.clickedButton()
    return next((clave for clave, b in botones.items() if b is tocado), escape)


def _preguntar(parent: QWidget | None, titulo: str, texto: str, *, si: str, no: str = "Volver") -> bool:
    """«Volver» / «Sí, …»: True solo si tocaron el botón del sí."""
    opciones = [("no", no, QMessageBox.ButtonRole.RejectRole), ("si", si, QMessageBox.ButtonRole.AcceptRole)]
    return _elegir(parent, titulo, texto, opciones, default="no", escape="no") == "si"


def _area_disponible(widget: QWidget | None) -> QRect:
    """El área libre de la pantalla donde se abre (sin la barra de tareas)."""
    pantalla = widget.screen() if widget is not None else None
    pantalla = pantalla or QApplication.primaryScreen()
    return pantalla.availableGeometry() if pantalla is not None else QRect(0, 0, 1366, 728)


def _default_session_factory() -> Session:
    from pos_uniformes.database.connection import get_session

    return get_session().__enter__()


def _estado_en_proceso(abierta) -> str:
    """'EN PROCESO (Fanny) · hoja impresa 10:32'."""
    hoja = getattr(abierta, "hoja_texto", "")
    return f"EN PROCESO ({abierta.quien})" + (f" · {hoja}" if hoja else "")


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
        self.prenda: str = ""   # una sola prenda (nombre del producto); "" = todo el alcance
        self.titulo: str = ""   # "Práxedis Guerrero" o "Básicos · Camisa", para rotular

        layout = QVBoxLayout()
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        pregunta = QLabel("¿Qué vas a contar?")
        pregunta.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(pregunta)
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
            try:
                # Cuánto se lleva contado de cada una. Sin esto, contar UNA
                # talla escondía el alcance entero por "recién contado" y la
                # que seguía ya no podía registrar lo demás (2026-10-05).
                from pos_uniformes.services.conteo_jornada_service import coberturas

                self._cobertura = coberturas(session)
            except Exception:  # noqa: BLE001 — sin esto se esconde como antes
                self._cobertura = {}
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
        from pos_uniformes.services.conteo_jornada_service import cobertura_de

        for e in self._escuelas:
            u = ultimo_conteo_de(self._ultimos, int(e["escuela_id"]))
            abierta = self._abiertas.get(int(e["escuela_id"]))
            cob = cobertura_de(getattr(self, "_cobertura", {}), int(e["escuela_id"]))
            # Una en proceso siempre se ve: hay que poder seguirla. Y una a
            # medias TAMBIÉN: es justo la que alguien tiene que terminar.
            if abierta is None and u.reciente() and not cob.a_medias and not todas:
                ocultas += 1
                continue
            if abierta is not None:
                estado = _estado_en_proceso(abierta)
            elif cob.a_medias:
                estado = cob.texto()
            else:
                estado = u.texto()
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
        prenda = str(self._prenda_combo.currentData() or "")
        if int(dato) == ESCUELA_ID_BASICOS:
            return ultimo_conteo_de(self._ultimos, None, str(self._tipo_combo.currentData() or ""), prenda)
        return ultimo_conteo_de(self._ultimos, int(dato), "", prenda)

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
        # Escuelas: la misma regla. Una prenda choca con la de toda la escuela
        # y con la de esa prenda; toda la escuela choca con cualquiera de ahí.
        escuela_id = int(dato)
        prenda_escuela = str(self._prenda_combo.currentData() or "")
        if prenda_escuela:
            return (
                self._abiertas.get((escuela_id, prenda_escuela))
                or self._abiertas.get(escuela_id)
            )
        return self._abiertas.get(escuela_id) or next(
            (
                j for k, j in self._abiertas.items()
                if isinstance(k, tuple) and len(k) == 2 and k[0] == escuela_id
            ),
            None,
        )

    def cobertura_elegida(self):
        """La Cobertura de lo que está seleccionado ahora."""
        from pos_uniformes.services.conteo_jornada_service import cobertura_de

        guardadas = getattr(self, "_cobertura", {})
        dato = self._escuela_combo.currentData()
        if dato is None:
            return cobertura_de({}, None)
        prenda = str(self._prenda_combo.currentData() or "")
        if int(dato) == ESCUELA_ID_BASICOS:
            return cobertura_de(
                guardadas, None, str(self._tipo_combo.currentData() or ""), prenda
            )
        return cobertura_de(guardadas, int(dato), "", prenda)

    def _pintar_ultimo(self, *_args) -> None:
        abierta = self.abierta_elegida()
        if abierta is not None:
            hoja = f" Ya tiene su {abierta.hoja_texto}: no la imprimas otra vez." if abierta.hoja_texto else ""
            self._ultimo_label.setText(f"En proceso: la está contando {abierta.quien} desde {abierta.iniciada_at.strftime('%H:%M') if abierta.iniciada_at else 'hoy'}. Puedes seguirla.{hoja}")
            self._ultimo_label.setStyleSheet("color: #b45309; font-size: 12px; font-weight: 700;")
            return
        # Lo que va a medias se dice ANTES de la fecha: "ya se contó hoy" es
        # verdad y es engañoso al mismo tiempo cuando faltan 37 de 40 tallas
        # (2026-10-05).
        cob = self.cobertura_elegida()
        if cob.a_medias:
            self._ultimo_label.setText(
                f"Va a medias: {cob.contadas} de {cob.total} tallas contadas, "
                f"faltan {cob.faltan}. Esta es la que hay que terminar."
            )
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

            from pos_uniformes.services.conteo_jornada_service import cobertura_de

            for t in tipos:
                abierta = self._abiertas.get(("basicos", t))
                u = ultimo_conteo_de(self._ultimos, None, t)
                cob = cobertura_de(getattr(self, "_cobertura", {}), None, t)
                if (
                    abierta is None and u.reciente() and not cob.a_medias
                    and not self._ver_todas.isChecked()
                ):
                    continue
                if abierta is not None:
                    estado = _estado_en_proceso(abierta)
                elif cob.a_medias:
                    estado = cob.texto()
                else:
                    estado = u.texto()
                self._tipo_combo.addItem(f"{t}   ·  {estado}", t)
        self._on_tipo()

    def _on_tipo(self, *_args) -> None:
        """Llena el combo de prendas del tipo elegido, cada una con su última fecha."""
        from pos_uniformes.services.conteo_jornada_service import nombre_corto_prenda, prendas_basicas, ultimo_conteo_de

        tipo = str(self._tipo_combo.currentData() or "")
        dato = self._escuela_combo.currentData()
        es_basicos = dato == ESCUELA_ID_BASICOS
        self._prenda_combo.blockSignals(True)
        self._prenda_combo.clear()
        if not es_basicos and dato is not None:
            # Una escuela también se puede contar de una sola prenda: es lo que
            # permite que dos personas se repartan los colores de la misma
            # playera en vez de que una se quede sin poder registrar
            # (Daniel, 2026-10-05).
            from pos_uniformes.services.conteo_jornada_service import (
                cobertura_de,
                prendas_de_escuela,
            )

            escuela_id = int(dato)
            u_escuela = ultimo_conteo_de(self._ultimos, escuela_id)
            cob_escuela = cobertura_de(getattr(self, "_cobertura", {}), escuela_id)
            estado_todas = cob_escuela.texto() or u_escuela.texto()
            self._prenda_combo.addItem(f"Toda la escuela   ·  {estado_todas}", "")
            session = self._session_factory()
            try:
                prendas = prendas_de_escuela(session, escuela_id)
            except Exception:  # noqa: BLE001
                prendas = []
            finally:
                session.close()
            for prenda in prendas:
                abierta = self._abiertas.get((escuela_id, prenda))
                u = ultimo_conteo_de(self._ultimos, escuela_id, "", prenda)
                cob = cobertura_de(getattr(self, "_cobertura", {}), escuela_id, "", prenda)
                if abierta is not None:
                    estado = _estado_en_proceso(abierta)
                elif cob.a_medias:
                    estado = cob.texto()
                elif cob.completa:
                    estado = f"lista · {u.texto()}"
                else:
                    estado = u.texto()
                self._prenda_combo.addItem(f"{nombre_corto_prenda(prenda)}   ·  {estado}", prenda)
            self._prenda_combo.setVisible(self._prenda_combo.count() > 1)
            self._prenda_combo.blockSignals(False)
            self._pintar_ultimo()
            return
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
            from pos_uniformes.services.conteo_jornada_service import cobertura_de

            for prenda in prendas:
                abierta = self._abiertas.get(("basicos", tipo, prenda))
                u = ultimo_conteo_de(self._ultimos, None, tipo, prenda)
                cob = cobertura_de(getattr(self, "_cobertura", {}), None, tipo, prenda)
                if abierta is not None:
                    estado = _estado_en_proceso(abierta)
                elif cob.a_medias:
                    estado = cob.texto()
                else:
                    estado = u.texto()
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
            from pos_uniformes.services.conteo_jornada_service import nombre_corto_prenda

            self.escuela_id = int(dato)
            self.tipo_pieza = ""
            self.prenda = str(self._prenda_combo.currentData() or "")
            nombre_escuela = self._escuela_combo.currentText().split("   ·  ")[0].strip()
            # Con prenda el título lo dice, para que la hoja impresa y el
            # tablero no se vean iguales que los de toda la escuela.
            self.titulo = (
                f"{nombre_escuela} · {nombre_corto_prenda(self.prenda)}"
                if self.prenda
                else nombre_escuela
            )
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


class _CajitaPedido(QStyledItemDelegate):
    """La celda PEDIR se ve como un campo (borde redondo) para que se note que
    ahí se escribe; vacía enseña un 0 tenue. En las demás celdas solo pinta el
    fondo de las filas de prenda."""

    def __init__(self, columna: int, parent=None) -> None:
        super().__init__(parent)
        self._columna = columna

    def initStyleOption(self, option, index) -> None:  # noqa: N802 - API de Qt
        """La fila elegida conserva el color de su letra (rojo de la diferencia,
        «¡URGENTE!»…): Qt pinta lo seleccionado con HighlightedText, no con el
        ForegroundRole de la celda."""
        super().initStyleOption(option, index)
        letra = index.data(Qt.ItemDataRole.ForegroundRole)
        if isinstance(letra, QBrush):
            option.palette.setBrush(QPalette.ColorRole.HighlightedText, letra)
        else:
            option.palette.setBrush(QPalette.ColorRole.HighlightedText, option.palette.brush(QPalette.ColorRole.Text))

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: D401
        if index.column() != self._columna or index.data(Qt.ItemDataRole.UserRole) is None:
            # La hoja de estilo de la tabla (::item) se come el fondo de la celda:
            # las filas de prenda lo pintan aquí.
            fondo = index.data(Qt.ItemDataRole.BackgroundRole)
            if isinstance(fondo, QBrush) and not option.state & QStyle.StateFlag.State_Selected:
                painter.fillRect(option.rect, fondo)
            super().paint(painter, option, index)
            return
        from pos_uniformes.ui.styles import conteo_revision_styles as cr

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        seleccionada = bool(option.state & QStyle.StateFlag.State_Selected)
        if seleccionada:
            painter.fillRect(option.rect, QColor(cr.SELECCION))
        caja = QRectF(option.rect).adjusted(10, 4, -10, -4)
        painter.setPen(QPen(QColor(cr.CAJITA_BORDE), 1.2))
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawRoundedRect(caja, 7, 7)
        texto = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        fuente = QFont(option.font)
        fuente.setBold(bool(texto))
        painter.setFont(fuente)
        painter.setPen(QColor(cr.TEXTO if texto else "#c9bcad"))
        painter.drawText(caja, int(Qt.AlignmentFlag.AlignCenter), texto or "0")
        painter.restore()


class ConteoColumnasDialog(QDialog):
    """«Ver todas las columnas»: la tabla completa en un diálogo aparte, con
    scroll de lado (no cabe en la ventana de Revisar)."""

    def __init__(self, parent: QWidget | None, *, titulo: str, filas: list[tuple[str, ...]]) -> None:
        super().__init__(parent)
        from pos_uniformes.services.conteo_revision_pantalla_service import COLUMNAS_TODAS

        self.setWindowTitle(f"Todas las columnas · {titulo}")
        self.setStyleSheet(_ESTILO)
        ly = QVBoxLayout(self)
        self._tabla = QTableWidget(len(filas), len(COLUMNAS_TODAS))
        self._tabla.setHorizontalHeaderLabels(list(COLUMNAS_TODAS))
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.setShowGrid(False)
        self._tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tabla.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        for f, valores in enumerate(filas):
            for c, txt in enumerate(valores):
                item = QTableWidgetItem(txt)
                if c not in (0, len(valores) - 1):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._tabla.setItem(f, c, item)
        self._tabla.resizeColumnsToContents()
        ly.addWidget(self._tabla, 1)
        cerrar = QPushButton("Cerrar")
        cerrar.setAutoDefault(False)
        cerrar.clicked.connect(self.accept)
        pie = QHBoxLayout()
        pie.addStretch()
        pie.addWidget(cerrar)
        ly.addLayout(pie)
        self.resize(1180, 600)


class ConteoRevisionDialog(QDialog):
    """Revisar un conteo: arriba, «¿le creo a este conteo?»; abajo, la decisión.

    - Encabezado: la prenda (o la escuela), quién contó, cuándo y hace cuánto,
      el aviso ámbar si ya es viejo o el letrero de ya revisada.
    - Franja de chips: el ajuste («Corrige 4 tallas · faltan 7 …») y Urgente,
      Pedir y Surtir; tocar uno filtra, tocarlo otra vez quita el filtro.
    - Tabla: una fila por talla con lo que decía el sistema, lo contado, la
      diferencia, lo vendido desde, lo que queda hoy, qué hacer y PEDIR
      (editable). Las de diferencia primero. Tocar una talla abre su «por qué».
    - Abajo: «Consultar ▾», «No usar este conteo», «Hoja de pedido» (si hay
      pedido) y «Corregir inventario (N tallas, ±N pz)».
    - Después de decidir, «✓ Listo» con «Siguiente por revisar»: la ventana
      deja `siguiente_jornada_id` / `siguiente_jornada` y el kiosko la abre.

    Todo lo que se decide (orden, textos, qué se ve) sale de
    `conteo_revision_pantalla_service`; aquí solo se pinta.
    """

    COLUMNAS = _COLUMNAS_REVISION
    COL_PEDIDO = _COL_PEDIDO_REVISION

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        jornada,
        revisada_por: str,
        session_factory: Callable[[], Session] | None = None,
        hoy: date | None = None,
        ofrecer_siguiente: bool = True,
    ) -> None:
        super().__init__(parent)
        from pos_uniformes.ui.styles import conteo_revision_styles as cr

        self.setObjectName("crDialogo")
        self.setWindowTitle(f"Revisar conteo · {jornada.titulo}")
        self.setStyleSheet(cr.build_conteo_revision_stylesheet())
        self._session_factory = session_factory or _default_session_factory
        self._jornada = jornada
        self._revisada_por = revisada_por
        self._ofrecer_siguiente = ofrecer_siguiente
        self.resultado: str = ""   # "aplicada" | "descartada" | ""
        self.siguiente_jornada_id: int | None = None   # «Siguiente por revisar»: la abre quien llamó
        self.siguiente_jornada = None                  # su JornadaRef
        self._siguiente = None                         # la que se ofrece en «Listo»
        self._revision = None
        self._pedidos: dict[int, int | None] = {}      # conteo_id → lo que Daniel escribió
        self._pedidos_base: dict[int, int | None] = {}  # lo guardado (o el sugerido): no cuenta como cambio
        self._pintando = False
        self._por_fila: dict[int, int] = {}            # fila → conteo_id (las de prenda y separador no están)
        self._hoy = hoy                                # None = hoy en la tienda (las pruebas lo fijan)
        self._contado_at = None
        self._dias = None
        self._diferencias: list[int] = []              # de las tallas que Corregir todavía mueve
        self._ajuste = None                            # conteo_resumen_service.ResumenAjuste
        self._ya_revisada = False
        self._aplicada = True
        self._filtro: str | None = None                # la clave del chip prendido
        self._en_su_orden = False

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        self._paginas = QStackedWidget()
        raiz.addWidget(self._paginas)
        self._paginas.addWidget(self._armar_revisar())
        self._paginas.addWidget(self._armar_listo())

        area = _area_disponible(parent)
        ancho, alto, min_ancho, min_alto = cr.medidas_ventana(area.width(), area.height())
        self.resize(ancho, alto)
        self.setMinimumSize(min_ancho, min_alto)
        self._cargar()

    # --- armado --------------------------------------------------------------------
    def _armar_revisar(self) -> QWidget:
        from pos_uniformes.services import conteo_revision_pantalla_service as pantalla
        from pos_uniformes.ui.styles import conteo_revision_styles as cr

        pagina = QWidget()
        pagina.setObjectName("crPagina")
        ly = QVBoxLayout(pagina)
        ly.setContentsMargins(22, 12, 22, 12)
        ly.setSpacing(6)

        # Una sola línea: la prenda (o escuela) y quién, cuándo, cuántas.
        cabeza = QHBoxLayout()
        cabeza.setSpacing(14)
        self._titulo_label = QLabel("")
        self._titulo_label.setObjectName("crTitulo")
        cabeza.addWidget(self._titulo_label, 0, Qt.AlignmentFlag.AlignBaseline)
        self._cuando_label = QLabel("")
        self._cuando_label.setObjectName("crSub")
        self._cuando_label.setWordWrap(True)
        cabeza.addWidget(self._cuando_label, 1, Qt.AlignmentFlag.AlignBaseline)
        ly.addLayout(cabeza)
        self._aviso_label = QLabel("")
        self._aviso_label.setObjectName("crAviso")
        self._aviso_label.setWordWrap(True)
        self._aviso_label.setVisible(False)
        ly.addWidget(self._aviso_label)
        self._revisada_label = QLabel("")
        self._revisada_label.setObjectName("crRevisada")
        self._revisada_label.setWordWrap(True)
        self._revisada_label.setVisible(False)
        ly.addWidget(self._revisada_label)

        # La franja: chips en una línea, la nota de las cajas y el orden.
        franja = QHBoxLayout()
        franja.setSpacing(8)
        self._chips: dict[str, QPushButton] = {}
        for clave in pantalla.CHIPS:
            b = QPushButton("")
            b.setObjectName("crChip")
            b.setAutoDefault(False)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=clave: self._tocar_chip(c))
            self._chips[clave] = b
            franja.addWidget(b)
        self._nota_cajas = QLabel(f"* {pantalla.NOTA_CAJAS}")
        self._nota_cajas.setObjectName("crNotaCajas")
        franja.addWidget(self._nota_cajas)
        franja.addStretch()
        self._orden_btn = QPushButton(pantalla.texto_orden(False))
        self._orden_btn.setObjectName("crOrden")
        self._orden_btn.setAutoDefault(False)
        self._orden_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._orden_btn.clicked.connect(self._cambiar_orden)
        franja.addWidget(self._orden_btn)
        ly.addLayout(franja)

        # Motivo real si no hay nada que pedir, y lo pedido.
        self._resumen_label = QLabel("")
        self._resumen_label.setObjectName("crResumen")
        self._resumen_label.setWordWrap(True)
        ly.addWidget(self._resumen_label)

        self._table = QTableWidget(0, len(self.COLUMNAS))
        self._table.setObjectName("crTabla")
        self._table.setHorizontalHeaderLabels(list(self.COLUMNAS))
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(cr.ALTO_FILA)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # El doble clic ya no abre la historia: deja escribir en PEDIR (y un toque también).
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.SelectedClicked
            | QTableWidget.EditTrigger.AnyKeyPressed
        )
        self._table.setItemDelegate(_CajitaPedido(self.COL_PEDIDO, self._table))
        h = self._table.horizontalHeader()
        h.setHighlightSections(False)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        from pos_uniformes.services.conteo_revision_pantalla_service import COL_QUE

        que = QTableWidgetItem(self.COLUMNAS[COL_QUE])
        que.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._table.setHorizontalHeaderItem(COL_QUE, que)
        anchos = (96, 132, 76, 70, 124, 130, None, 104)
        for c, ancho in enumerate(anchos):
            if ancho is None:
                h.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)
            else:
                h.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(c, ancho)
        self._table.itemChanged.connect(self._pedido_editado)
        self._table.itemSelectionChanged.connect(self._por_que)
        self._table.cellClicked.connect(self._celda_tocada)
        ly.addWidget(self._table, 1)

        # Por qué: la evidencia de la talla tocada, en una línea.
        self._por_que_label = QLabel("")
        self._por_que_label.setObjectName("crPorQue")
        self._por_que_label.setWordWrap(True)
        ly.addWidget(self._por_que_label)

        pie = QHBoxLayout()
        pie.setSpacing(10)
        self._consultar_btn = QToolButton()
        self._consultar_btn.setObjectName("crConsultar")
        self._consultar_btn.setText("Consultar ▾")
        self._consultar_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._consultar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._menu_consultar = QMenu(self._consultar_btn)
        self._menu_consultar.setObjectName("crMenu")
        self._accion_historia = self._menu_consultar.addAction("📈  Historia de la talla")
        self._accion_historia.triggered.connect(lambda: self._historia())
        self._accion_escuela = self._menu_consultar.addAction("🏫  Historia de la escuela")
        self._accion_escuela.triggered.connect(self._historia_escuela)
        self._accion_comparar = self._menu_consultar.addAction("🔁  Comparar con el anterior")
        self._accion_comparar.triggered.connect(self._comparar)
        self._menu_consultar.addSeparator()
        self._accion_todas = self._menu_consultar.addAction("▦  Ver todas las columnas")
        self._accion_todas.triggered.connect(self._ver_todas_las_columnas)
        self._consultar_btn.setMenu(self._menu_consultar)
        pie.addWidget(self._consultar_btn)
        pie.addSpacing(12)
        self._descartar_btn = QPushButton("No usar este conteo")
        self._descartar_btn.setObjectName("crNoUsar")
        self._descartar_btn.setAutoDefault(False)
        self._descartar_btn.clicked.connect(self._descartar)
        pie.addWidget(self._descartar_btn)
        pie.addStretch()
        self._hoja_btn = QPushButton("🧾 Hoja de pedido")
        self._hoja_btn.setObjectName("crSecundario")
        self._hoja_btn.setAutoDefault(False)
        self._hoja_btn.clicked.connect(self._hoja_de_pedido)
        pie.addWidget(self._hoja_btn)
        self._aplicar_btn = QPushButton("Corregir inventario")
        self._aplicar_btn.setObjectName("crPrimario")
        self._aplicar_btn.setAutoDefault(False)
        self._aplicar_btn.clicked.connect(self._aplicar)
        pie.addWidget(self._aplicar_btn)
        ly.addLayout(pie)
        return pagina

    def _armar_listo(self) -> QWidget:
        pagina = QWidget()
        pagina.setObjectName("crPagina")
        ly = QVBoxLayout(pagina)
        ly.setContentsMargins(22, 22, 22, 22)
        ly.addStretch(1)
        tarjeta = QFrame()
        tarjeta.setObjectName("crListo")
        tarjeta.setMaximumWidth(620)
        t = QVBoxLayout(tarjeta)
        t.setContentsMargins(36, 30, 36, 28)
        t.setSpacing(10)
        icono = QLabel("✓")
        icono.setObjectName("crListoIcono")
        icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.addWidget(icono)
        self._listo_titulo = QLabel("Listo")
        self._listo_titulo.setObjectName("crListoTitulo")
        self._listo_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.addWidget(self._listo_titulo)
        self._listo_texto = QLabel("")
        self._listo_texto.setObjectName("crListoTexto")
        self._listo_texto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._listo_texto.setWordWrap(True)
        t.addWidget(self._listo_texto)
        self._listo_quedan = QLabel("")
        self._listo_quedan.setObjectName("crListoQuedan")
        self._listo_quedan.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._listo_quedan.setWordWrap(True)
        t.addWidget(self._listo_quedan)
        botones = QHBoxLayout()
        botones.setSpacing(10)
        botones.addStretch()
        self._cerrar_btn = QPushButton("Cerrar")
        self._cerrar_btn.setObjectName("crSecundario")
        self._cerrar_btn.setAutoDefault(False)
        self._cerrar_btn.clicked.connect(self._cerrar_listo)
        botones.addWidget(self._cerrar_btn)
        self._siguiente_btn = QPushButton("Siguiente por revisar")
        self._siguiente_btn.setObjectName("crPrimario")
        self._siguiente_btn.setAutoDefault(False)
        self._siguiente_btn.clicked.connect(self._ir_a_siguiente)
        botones.addWidget(self._siguiente_btn)
        botones.addStretch()
        t.addSpacing(8)
        t.addLayout(botones)
        fila = QHBoxLayout()
        fila.addStretch()
        fila.addWidget(tarjeta, 1)
        fila.addStretch()
        ly.addLayout(fila)
        ly.addStretch(2)
        return pagina

    def showEvent(self, evento) -> None:  # noqa: N802 - API de Qt
        super().showEvent(evento)
        QTimer.singleShot(0, self._caber_en_pantalla)

    def _caber_en_pantalla(self) -> None:
        """Con el marco real: si se sale del área libre, se achica y se mueve."""
        area = _area_disponible(self)
        marco = self.frameGeometry()
        extra_alto = max(0, marco.height() - self.height())
        extra_ancho = max(0, marco.width() - self.width())
        if marco.height() > area.height() or marco.width() > area.width():
            self.resize(min(self.width(), area.width() - extra_ancho), min(self.height(), area.height() - extra_alto))
            marco = self.frameGeometry()
        x = max(area.left(), min(marco.x(), area.right() + 1 - marco.width()))
        y = max(area.top(), min(marco.y(), area.bottom() + 1 - marco.height()))
        if (x, y) != (marco.x(), marco.y()):
            self.move(x, y)

    # --- datos ---------------------------------------------------------------------
    def _cargar(self) -> None:
        from pos_uniformes.database.models import ConteoJornada
        from pos_uniformes.services import conteo_revision_vista_service as vista
        from pos_uniformes.services.conteo_jornada_service import DESCARTADA, resumen_para_revisar
        from pos_uniformes.services.conteo_resumen_service import resumen_de_jornada
        from pos_uniformes.services.nombres_empleadas_service import mostrar, nombres_por_codigo
        from pos_uniformes.services.revision_service import revisar

        session = self._session_factory()
        try:
            j = session.get(ConteoJornada, self._jornada.id)
            self._revision = revisar(session, j)
            # La diferencia de cada talla se guardó al capturar; Corregir suma
            # las que todavía no se ajustan.
            self._diferencias = [l.diferencia for l in resumen_para_revisar(session, j).lineas]
            # El resumen real del ajuste: piezas, $, vendidas desde y otros ajustes.
            self._ajuste = resumen_de_jornada(session, j)
            self._contado_at = j.terminada_at or j.iniciada_at
            self._ya_revisada = vista.ya_revisada(j)
            self._aplicada = (j.notas or "") != DESCARTADA
            revisada_txt = ""
            if self._ya_revisada:
                por = mostrar(j.revisada_por, nombres_por_codigo(session)) if j.revisada_por else ""
                revisada_txt = vista.texto_ya_revisada(revisada_at=j.revisada_at, aplicada=self._aplicada, por=por)
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
        self._pedidos_base = dict(self._pedidos)   # el prellenado no es «un cambio sin guardar»
        self._encabezado(revisada_txt)
        self._resumen()
        self._pintar()

    def _encabezado(self, revisada_txt: str) -> None:
        """Prenda (o escuela), quién/cuándo/cuántas, el aviso ámbar si ya es
        viejo, y si ya se revisó: el letrero y sin Corregir ni No usar."""
        from pos_uniformes.services import conteo_revision_pantalla_service as pantalla
        from pos_uniformes.services import conteo_revision_vista_service as vista

        r = self._revision
        self._dias = vista.dias_desde(self._contado_at, self._hoy)
        self._titulo_label.setText(pantalla.titulo_encabezado(r.lineas, r.titulo))
        self._cuando_label.setText(pantalla.subtitulo_encabezado(
            quien=r.quien, contado=self._contado_at, lineas=r.lineas, hoy=self._hoy,
        ))
        # En una línea: con varias tallas con otro ajuste solo dice cuántas; el detalle, en el tooltip.
        aviso = "" if self._ya_revisada else vista.aviso_conteo_viejo(self._dias, self._ajuste, corto=True)
        largo = "" if self._ya_revisada else vista.aviso_conteo_viejo(self._dias, self._ajuste)
        self._aviso_label.setText(f"⚠ {aviso}" if aviso else "")
        self._aviso_label.setToolTip(largo if largo != aviso else "")
        self._aviso_label.setVisible(bool(aviso))
        if self._ya_revisada:
            self._revisada_label.setText(f"✓ {revisada_txt}. El pedido se puede seguir escribiendo y guardando.")
        self._revisada_label.setVisible(self._ya_revisada)
        self._aplicar_btn.setText(pantalla.texto_boton_corregir(self._ajuste))
        self._aplicar_btn.setToolTip(pantalla.ayuda_boton_corregir(self._ajuste))

    def _pedido_cambiado(self) -> bool:
        """¿Daniel escribió en PEDIR algo distinto de lo guardado (o lo sugerido)?"""
        return self._revision is not None and self._pedidos != self._pedidos_base

    def _resumen(self) -> None:
        """Los chips, el renglón de motivo/pedido y qué botones se ven."""
        from pos_uniformes.services import conteo_revision_pantalla_service as pantalla
        from pos_uniformes.services.conteo_revision_vista_service import motivo_sin_accion

        r = self._revision
        for chip in pantalla.chips(r.lineas, self._ajuste, ya_revisada=self._ya_revisada, aplicada=self._aplicada):
            b = self._chips[chip.clave]
            b.setText(chip.texto + ("*" if chip.nota else ""))
            b.setToolTip(chip.nota)
            b.setEnabled(chip.tocable)
            b.setProperty("tono", chip.tono)
            b.setProperty("activo", "si" if self._filtro == chip.clave else "no")
            b.style().unpolish(b)
            b.style().polish(b)
        partes = []
        # Tanda 4: por qué hay tallas que Corregir no toca (y si por eso solo se marca revisado).
        no_se_tocan = "" if self._ya_revisada else pantalla.ayuda_boton_corregir(self._ajuste)
        if no_se_tocan:
            partes.append(f"<span style='color:#a35a00'>⚠ {no_se_tocan}</span>")
        if not r.lineas:
            partes.append("Esta jornada no tiene tallas capturadas.")
        else:
            motivo = motivo_sin_accion(r.lineas)
            if motivo:
                partes.append(motivo)
        pedido = pantalla.texto_pedido(self._pedidos)
        if pedido:
            partes.append(pedido)
        self._resumen_label.setText("  ·  ".join(partes))
        self._resumen_label.setVisible(bool(partes))
        acciones = pantalla.acciones(ya_revisada=self._ya_revisada, pedidos=self._pedidos)
        self._aplicar_btn.setVisible(acciones.corregir)
        self._descartar_btn.setVisible(acciones.no_usar)
        self._hoja_btn.setVisible(acciones.hoja)
        self._hoja_btn.setEnabled(acciones.hoja)

    # --- filtro y orden --------------------------------------------------------------
    def _tocar_chip(self, clave: str) -> None:
        from pos_uniformes.services.conteo_revision_pantalla_service import tocar_chip

        self._filtro = tocar_chip(self._filtro, clave)
        self._resumen()
        self._pintar()

    def _cambiar_orden(self) -> None:
        from pos_uniformes.services.conteo_revision_pantalla_service import texto_orden

        self._en_su_orden = not self._en_su_orden
        self._orden_btn.setText(texto_orden(self._en_su_orden))
        self._pintar()

    # --- pintura -------------------------------------------------------------------
    def _que_hacer(self, l) -> str:
        from pos_uniformes.services.conteo_revision_vista_service import que_hacer

        return que_hacer(l)

    def _pintar(self, *_a) -> None:
        if self._revision is None or self._pintando:
            return
        from pos_uniformes.services import conteo_revision_pantalla_service as pantalla
        from pos_uniformes.ui.styles import conteo_revision_styles as cr

        elegido = self._por_fila.get(self._table.currentRow())
        self._pintando = True
        filas = pantalla.filas_tabla(
            self._revision.lineas, self._ajuste, self._pedidos, titulo=self._revision.titulo,
            filtro=self._filtro, en_su_orden=self._en_su_orden, ya_revisada=self._ya_revisada,
        )
        self._table.clearSpans()
        self._table.clearContents()
        self._table.setRowCount(len(filas))
        self._por_fila = {}
        n_col = len(self.COLUMNAS)
        fila_elegida = -1
        for f, fila in enumerate(filas):
            if fila.tipo != pantalla.FILA_TALLA:
                item = QTableWidgetItem(fila.texto)
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                fuente = self._fuente_tabla()
                if fila.tipo == pantalla.FILA_PRENDA:
                    fuente.setBold(True)
                    item.setForeground(QBrush(QColor(cr.TERRACOTA_OSCURO)))
                    item.setBackground(QBrush(QColor(cr.GRUPO)))
                    item.setFont(fuente)
                else:
                    item.setForeground(QBrush(QColor(cr.TENUE)))
                    item.setText(f"— {fila.texto} —")
                self._table.setItem(f, 0, item)
                self._table.setSpan(f, 0, 1, n_col)
                continue
            self._por_fila[f] = fila.conteo_id
            if fila.conteo_id == elegido:
                fila_elegida = f
            for c, txt in enumerate(fila.celdas):
                item = QTableWidgetItem(txt)
                item.setData(Qt.ItemDataRole.UserRole, fila.conteo_id)
                if c == pantalla.COL_QUE:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c != self.COL_PEDIDO:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                color = None
                if c == pantalla.COL_TALLA:
                    fuente = self._fuente_tabla()
                    fuente.setBold(True)
                    item.setFont(fuente)
                elif c == pantalla.COL_CONTO and fila.tono_conto:
                    color = cr.ROJO
                elif c == pantalla.COL_DIF:
                    color = cr.COLOR_DIF.get(fila.tono_dif)
                    if fila.ojo:
                        item.setToolTip(f"⚠ {fila.ojo}")
                    if fila.tono_dif in ("faltan", "sobran"):
                        fuente = self._fuente_tabla()
                        fuente.setBold(True)
                        item.setFont(fuente)
                elif c == pantalla.COL_VENDIDAS and txt == "0":
                    color = "#b4a898"
                elif c == pantalla.COL_QUEDA and fila.tono_queda:
                    color = cr.ROJO
                elif c == pantalla.COL_QUE:
                    color = cr.COLOR_QUE.get(fila.tono_que)
                    if fila.tono_que in ("urgente", "pedir"):
                        fuente = self._fuente_tabla()
                        fuente.setBold(True)
                        item.setFont(fuente)
                    # Si no cabe, el texto entero en el tooltip (con las cajas, si hay).
                    item.setToolTip("\n".join(x for x in (txt, fila.ayuda_que) if x))
                if color:
                    item.setForeground(QBrush(QColor(color)))
                self._table.setItem(f, c, item)
        if fila_elegida >= 0:
            self._table.selectRow(fila_elegida)
        else:
            self._table.clearSelection()
            self._table.setCurrentCell(-1, -1)
        self._pintando = False
        self._por_que()

    def _fuente_tabla(self) -> QFont:
        """La letra de la tabla (la de su hoja de estilo): una celda con letra
        propia no hereda el tamaño de la hoja."""
        self._table.ensurePolished()
        return QFont(self._table.font())

    def _la_vez_pasada(self, l) -> str:
        from pos_uniformes.services.conteo_revision_pantalla_service import la_vez_pasada

        return la_vez_pasada(l)

    def _linea_en_fila(self, fila: int):
        conteo_id = self._por_fila.get(fila)
        if conteo_id is None:
            return None
        return next((l for l in self._revision.lineas if l.conteo_id == conteo_id), None)

    def _celda_tocada(self, fila: int, columna: int) -> None:
        """Un toque en PEDIR ya abre la cajita para escribir."""
        if columna == self.COL_PEDIDO and fila in self._por_fila:
            item = self._table.item(fila, columna)
            if item is not None:
                self._table.editItem(item)

    def _por_que(self) -> None:
        """La evidencia de la talla tocada, en una línea debajo de la tabla."""
        if self._revision is None or self._pintando:
            return
        filas = {i.row() for i in self._table.selectedIndexes()}
        fila = self._table.currentRow() if self._table.currentRow() in filas else (min(filas) if filas else -1)
        l = self._linea_en_fila(fila)
        if l is None:
            self._por_que_label.setText("Toca una talla para ver por qué se sugiere eso.")
            self._por_que_label.setProperty("vacio", "si")
            self._por_que_label.style().unpolish(self._por_que_label)
            self._por_que_label.style().polish(self._por_que_label)
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
            partes.append(f"<span style='color:#b3261e'>pidieron <b>{l.pidieron}</b> y no había</span>")
        if l.ellas_sugieren is not None:
            partes.append(f"en la hoja anotaron pedir {l.ellas_sugieren}")
        if l.cajas:
            partes.append("en cajas*: " + " · ".join(f"{c} ×{n}" for c, n in l.cajas))
        partes.append(self._la_vez_pasada(l))
        # Lo demás (el sistema decía, vendidas desde, queda hoy) ya está en la fila.
        from pos_uniformes.services.conteo_revision_pantalla_service import texto_por_que_ajuste

        otro = texto_por_que_ajuste(self._talla_del_ajuste(l.conteo_id), ya_revisada=self._ya_revisada)
        if otro:
            partes.append(f"<span style='color:#a35a00'>⚠ {otro}</span>")
        from pos_uniformes.services.conteo_revision_pantalla_service import _colores, talla_texto

        varios = len({x.producto for x in self._revision.lineas}) > 1
        nombre = f"{nombre_para_hoja(l.producto, self._revision.titulo)} · " if varios else ""
        de_la_prenda = [x for x in self._revision.lineas if x.producto == l.producto]
        talla = talla_texto(l, varios_colores=len(_colores(de_la_prenda)) > 1)
        self._por_que_label.setText(f"▸ <b>{nombre}Talla {talla}</b>: " + " · ".join(partes))
        self._por_que_label.setProperty("vacio", "no")
        self._por_que_label.style().unpolish(self._por_que_label)
        self._por_que_label.style().polish(self._por_que_label)

    def _talla_del_ajuste(self, conteo_id: int):
        if self._ajuste is None:
            return None
        return next((t for t in self._ajuste.tallas if t.conteo_id == conteo_id), None)

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
        self._repintar_grupos()

    def _repintar_grupos(self) -> None:
        """La fila de grupo dice «pedir N» con lo escrito en PEDIR: al cambiar
        una cajita se rehace su texto (las filas no se mueven)."""
        from pos_uniformes.services import conteo_revision_pantalla_service as pantalla

        filas = pantalla.filas_tabla(
            self._revision.lineas, self._ajuste, self._pedidos, titulo=self._revision.titulo,
            filtro=self._filtro, en_su_orden=self._en_su_orden, ya_revisada=self._ya_revisada,
        )
        if len(filas) != self._table.rowCount():
            return
        self._pintando = True
        try:
            for f, fila in enumerate(filas):
                item = self._table.item(f, 0)
                if fila.tipo == pantalla.FILA_PRENDA and item is not None and item.text() != fila.texto:
                    item.setText(fila.texto)
        finally:
            self._pintando = False

    # --- acciones ------------------------------------------------------------------
    def _guardar_pedidos(self, *, avisar: bool = True) -> bool:
        """Guarda lo escrito en PEDIR. Ya no hay botón: lo llaman Corregir, la
        Hoja de pedido y el cierre (con la pregunta)."""
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
        self._pedidos_base = dict(self._pedidos)
        if avisar:
            QMessageBox.information(self, "Pedido guardado", f"Quedó tu pedido en {n} tallas. La próxima revisión lo va a recordar.")
        return True

    def _revision_con_pedidos(self):
        """La revisión con lo que Daniel tiene escrito ahora."""
        from dataclasses import replace

        r = self._revision
        lineas = [replace(l, pedido=self._pedidos.get(l.conteo_id)) for l in r.lineas]
        return replace(r, lineas=lineas)

    def _hoja_de_pedido(self) -> None:
        """Guarda el pedido (si cambió) y abre la hoja para mandarlo."""
        if self._revision is None:
            return
        self._cerrar_editor_abierto()
        if self._pedido_cambiado() and not self._guardar_pedidos(avisar=False):
            return
        from pos_uniformes.services.revision_service import html_pedido, texto_pedido

        r = self._revision_con_pedidos()
        PedidoHojaDialog(self, texto=texto_pedido(r), html=html_pedido(r), titulo=f"Pedido · {r.titulo}").exec()

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

    def _filas_todas(self) -> list[tuple[str, ...]]:
        from pos_uniformes.services import conteo_revision_pantalla_service as pantalla

        por_id = pantalla.tallas_por_id(self._ajuste)
        return [
            pantalla.fila_todas(
                l, por_id.get(l.conteo_id), self._pedidos.get(l.conteo_id),
                titulo=self._revision.titulo, ya_revisada=self._ya_revisada,
            )
            for l in self._revision.lineas
        ]

    def _ver_todas_las_columnas(self) -> None:
        """Todas las columnas no caben aquí: van en un diálogo aparte con scroll de lado."""
        if self._revision is None:
            return
        self._todas_dlg = ConteoColumnasDialog(self, titulo=self._revision.titulo, filas=self._filas_todas())
        self._todas_dlg.exec()

    def _aplicar(self) -> None:
        if self._revision is None or self._ya_revisada:
            return
        from pos_uniformes.services import conteo_revision_vista_service as vista

        self._cerrar_editor_abierto()
        texto = vista.texto_confirmar_aplicar(
            quien=self._revision.quien, contado=self._contado_at, diferencias=self._diferencias, hoy=self._hoy,
            resumen=self._ajuste,
        )
        si = vista.boton_corregir(self._dias, self._diferencias, resumen=self._ajuste)
        if not _preguntar(self, "Corregir inventario", texto, si=si, no=vista.BOTON_VOLVER):
            return
        if not self._guardar_pedidos(avisar=False):
            return
        from pos_uniformes.database.models import ConteoJornada
        from pos_uniformes.services.conteo_jornada_service import aplicar_jornada

        session = self._session_factory()
        try:
            j = session.get(ConteoJornada, self._jornada.id)
            hecho = aplicar_jornada(session, j, revisada_por=self._revisada_por)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            QMessageBox.critical(self, "No se corrigió", str(exc))
            return
        finally:
            session.close()
        # «✓ Listo» dice lo que decidió el servicio al aplicar (tallas que se
        # saltaron incluidas), no lo que la pantalla leyó al abrir.
        if getattr(hecho, "resumen", None) is not None:
            self._ajuste = hecho.resumen
        self.resultado = "aplicada"
        self._mostrar_listo()

    def _descartar(self) -> None:
        if self._ya_revisada:
            return
        from pos_uniformes.services import conteo_revision_vista_service as vista

        if not _preguntar(self, "No usar este conteo", vista.TEXTO_CONFIRMAR_DESCARTAR, si=vista.BOTON_DESCARTAR, no=vista.BOTON_VOLVER):
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
        self._mostrar_listo()

    # --- ✓ Listo -------------------------------------------------------------------
    def _por_revisar(self) -> list:
        """Las jornadas que siguen por revisar (en el orden de la tarjeta del kiosko)."""
        from pos_uniformes.services.conteo_jornada_service import jornadas_por_revisar, ref

        session = self._session_factory()
        try:
            return [ref(j) for j in jornadas_por_revisar(session) if int(j.id) != int(self._jornada.id)]
        except Exception:  # noqa: BLE001 — sin conexión: solo se ofrece cerrar
            return []
        finally:
            session.close()

    def _mostrar_listo(self) -> None:
        """«✓ Listo» en la misma ventana, con [Siguiente por revisar] si hay otra."""
        from pos_uniformes.services import conteo_revision_pantalla_service as pantalla

        pendientes = self._por_revisar() if self._ofrecer_siguiente else []
        sid = pantalla.siguiente_por_revisar([j.id for j in pendientes], self._jornada.id)
        self._siguiente = next((j for j in pendientes if j.id == sid), None)
        self._listo_titulo.setText("Listo")
        self._listo_texto.setText(pantalla.texto_listo(self.resultado, self._ajuste))
        quedan = pantalla.texto_quedan(len(pendientes)) if self._ofrecer_siguiente else ""
        if self._siguiente is not None:
            quedan += f" Sigue: {self._siguiente.titulo} ({self._siguiente.quien})."
        self._listo_quedan.setText(quedan)
        self._listo_quedan.setVisible(bool(quedan))
        self._siguiente_btn.setVisible(self._siguiente is not None)
        self._cerrar_btn.setObjectName("crSecundario" if self._siguiente is not None else "crPrimario")
        self._cerrar_btn.style().unpolish(self._cerrar_btn)
        self._cerrar_btn.style().polish(self._cerrar_btn)
        self._paginas.setCurrentIndex(1)
        (self._siguiente_btn if self._siguiente is not None else self._cerrar_btn).setFocus()

    def _ir_a_siguiente(self) -> None:
        if self._siguiente is None or not self._pedido_resuelto():
            return
        self.siguiente_jornada = self._siguiente
        self.siguiente_jornada_id = int(self._siguiente.id)
        self.accept()

    def _cerrar_listo(self) -> None:
        """[Cerrar] de «✓ Listo»: como la ✕, pregunta si el pedido quedó sin guardar
        (pasa al «No usar»: ese camino no lo guarda)."""
        if self._pedido_resuelto():
            self.accept()

    def _pedido_resuelto(self) -> bool:
        """Si cambiaste el pedido a mano y no lo guardaste, pregunta Guardar /
        No guardar / Volver. False = Volver (o no se pudo guardar): no salir."""
        self._cerrar_editor_abierto()
        if not self._pedido_cambiado():
            return True
        opcion = _elegir(
            self, "Pedido sin guardar", "Cambiaste el pedido y no lo guardaste.",
            [
                ("guardar", "Guardar", QMessageBox.ButtonRole.AcceptRole),
                ("no_guardar", "No guardar", QMessageBox.ButtonRole.DestructiveRole),
                ("volver", "Volver", QMessageBox.ButtonRole.RejectRole),
            ],
            default="guardar", escape="volver",
        )
        if opcion == "volver":
            return False
        if opcion == "guardar":
            return self._guardar_pedidos(avisar=False)
        return True

    # --- cerrar --------------------------------------------------------------------
    def _cerrar_editor_abierto(self) -> None:
        """Si hay una celda de PEDIR a medio escribir, la guarda antes de seguir.

        Con la ✕ el editor no pierde el foco: sin esto, lo escrito entraba a
        `_pedidos` hasta que la ventana ya se ocultaba, después de la pregunta."""
        if self._table.state() != QAbstractItemView.State.EditingState:
            return
        viewport = self._table.viewport()
        editor = QApplication.focusWidget()
        while editor is not None and editor.parentWidget() is not viewport:
            editor = editor.parentWidget()
        editores = [editor] if editor is not None else [
            w for w in viewport.children() if isinstance(w, QWidget) and w.isVisible()
        ]
        for editor in editores:
            self._table.commitData(editor)
            self._table.closeEditor(editor, QAbstractItemDelegate.EndEditHint.NoHint)

    def reject(self) -> None:
        """Cerrar (✕ o Esc): si cambiaste el pedido a mano y no lo guardaste,
        pregunta. El prellenado con el sugerido no cuenta."""
        if self._pedido_resuelto():
            super().reject()


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
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        encabezado = QLabel(titulo)
        encabezado.setStyleSheet("font-size: 20px; font-weight: 800; color: #6b1f3a;")
        layout.addWidget(encabezado)
        ayuda = QLabel(
            "Así se manda por WhatsApp o Telegram. «Imprimir hoja» saca la hoja carta "
            "con las tallas en fila, casillas «Llegó» y lugar para el maquilador y la entrega."
        )
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color: #8a8177; font-size: 13px;")
        layout.addWidget(ayuda)
        self._cuadro = QPlainTextEdit(texto)
        self._cuadro.setReadOnly(True)
        self._cuadro.setStyleSheet(
            "background: #ffffff; color: #2c2a27; border: 1px solid #e6dccb; border-radius: 10px;"
            "padding: 8px; font-family: Menlo, Consolas, monospace; font-size: 13px;"
        )
        layout.addWidget(self._cuadro, 1)
        botones = QHBoxLayout()
        botones.setSpacing(8)
        copiar = QPushButton("📋  Copiar para WhatsApp")
        copiar.clicked.connect(self._copiar)
        botones.addWidget(copiar)
        self._telegram_btn = QPushButton("✈️  Mandar por Telegram")
        self._telegram_btn.clicked.connect(self._telegram)
        botones.addWidget(self._telegram_btn)
        botones.addStretch()
        imprimir = QPushButton("🖨  Imprimir hoja")
        imprimir.setObjectName("primaryButton")
        imprimir.clicked.connect(self._imprimir)
        botones.addWidget(imprimir)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        botones.addWidget(cerrar)
        layout.addLayout(botones)
        self.setLayout(layout)
        self.resize(620, 600)

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
        self._tabla.setColumnCount(7)
        self._tabla.setHorizontalHeaderLabels(["Fecha", "Contó", "Quién", "Sugerido", "Pediste", "Vendidas después", "Inventario"])
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.setShowGrid(False)
        h = self._tabla.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for c in (0, 1, 3, 4, 5, 6):
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
                c.inventario or "—",   # tanda 4: «no se corrigió (otro ajuste)» si se saltó
            )
            for col, txt in enumerate(valores):
                item = QTableWidgetItem(txt)
                if col != 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 6 and c.inventario.startswith("no se corrigió"):
                    item.setForeground(QBrush(QColor("#a35a00")))
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
