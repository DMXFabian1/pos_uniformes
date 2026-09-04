"""Dialogo de administracion del satelite (Ctrl+Shift+A, PIN admin)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtPrintSupport import QPrinterInfo
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QScrollArea,
    QTabWidget,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services.satellite_startup_service import probe_database_host
from pos_uniformes.services.ticket_print_settings_cache_service import (
    load_ticket_print_settings,
    save_ticket_print_settings,
)
from pos_uniformes.utils.config import settings, _appdata_config_dir, runtime_base_dir

_ADMIN_PIN = "634700"
_ENV_FILENAME = "pos_uniformes.env"


def _find_env_path() -> Path:
    appdata = _appdata_config_dir()
    if appdata is not None:
        candidate = appdata / _ENV_FILENAME
        if candidate.exists():
            return candidate
        return candidate
    return runtime_base_dir() / _ENV_FILENAME


def _write_env(host: str, password: str) -> None:
    path = _find_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"POS_UNIFORMES_DB_HOST={host}",
        f"POS_UNIFORMES_DB_PORT={settings.db_port}",
        f"POS_UNIFORMES_DB_NAME={settings.db_name}",
        f"POS_UNIFORMES_DB_USER={settings.db_user}",
        f"POS_UNIFORMES_DB_PASSWORD={password}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _release_instance_lock() -> None:
    """Suelta el QLockFile de instancia única antes de reiniciar.

    En Windows os.execv arranca el proceso nuevo mientras el viejo muere: si
    el candado sigue tomado, la instancia nueva ve "Ya está abierto" y la app
    queda cerrada en vez de reiniciada.
    """
    app = QApplication.instance()
    lock = getattr(app, "_instance_lock", None)
    if lock is None:
        return
    try:
        lock.unlock()
    except Exception:  # noqa: BLE001 — reiniciar es mejor que quedarse trabado
        pass


def _restart_app() -> None:
    _release_instance_lock()
    os.execv(sys.executable, sys.argv)


def _prompt_pin(parent: QWidget) -> bool:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Acceso administrador")
    dialog.setMinimumWidth(320)
    layout = QVBoxLayout()
    label = QLabel("Ingresa el PIN de administrador:")
    label.setWordWrap(True)
    pin_input = QLineEdit()
    pin_input.setEchoMode(QLineEdit.EchoMode.Password)
    pin_input.setPlaceholderText("PIN")
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(label)
    layout.addWidget(pin_input)
    layout.addWidget(buttons)
    dialog.setLayout(layout)
    pin_input.returnPressed.connect(dialog.accept)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    return pin_input.text().strip() == _ADMIN_PIN


def _build_anuncios_boxes(dialog: QWidget) -> list[QGroupBox]:
    """Sección de anuncios/cartelera: este satélite + satélites + crear + lista.

    Devuelve la lista de cajas. Toda la I/O de DB es defensiva: si la PC
    principal está apagada, avisa en vez de reventar.
    """
    estado_img: dict = {"bytes": None, "mime": None, "nombre": None}
    # Estado de satélites conocidos (para el selector de destinos y la lista).
    sat_estado: list[dict] = []

    def _nombre_de(identificador: str) -> str:
        for s in sat_estado:
            if s["identificador"] == identificador:
                return s["nombre"]
        return identificador

    # — Este satélite (identidad) —
    este_box = QGroupBox("Este satélite")
    try:
        from pos_uniformes.services.satellite_identity_service import (
            get_satellite_id,
            get_satellite_name,
        )

        _mi_id = get_satellite_id()
        _mi_nombre = get_satellite_name()
    except Exception:  # noqa: BLE001
        _mi_id, _mi_nombre = "", ""
    nombre_in = QLineEdit(_mi_nombre)
    nombre_in.setPlaceholderText("Nombre de esta pantalla (ej. Entrada, Caja 2)")
    guardar_nombre_btn = QPushButton("Guardar nombre")
    id_lbl = QLabel(f"id: {_mi_id}")
    id_lbl.setObjectName("satStatus")

    # — Satélites (presencia) —
    satelites_box = QGroupBox("Satélites")
    satelites_list = QListWidget()
    refrescar_sat_btn = QPushButton("Actualizar")

    # — Crear —
    crear_box = QGroupBox("Nuevo anuncio")
    titulo_in = QLineEdit()
    titulo_in.setPlaceholderText("Título (opcional)")
    mensaje_in = QTextEdit()
    mensaje_in.setPlaceholderText("Mensaje (opcional)")
    mensaje_in.setFixedHeight(90)
    duracion_in = QSpinBox()
    duracion_in.setRange(3, 120)
    duracion_in.setValue(8)
    duracion_in.setSuffix(" s en cartelera")
    imagen_btn = QPushButton("Elegir imagen…")
    imagen_lbl = QLabel("Sin imagen")
    imagen_lbl.setWordWrap(True)
    quitar_img_btn = QPushButton("Quitar imagen")
    quitar_img_btn.setVisible(False)
    inmediato_chk = QCheckBox("Mostrar ahora (aviso inmediato)")
    # Destinos: por defecto TODOS; se puede destildar y elegir satélites.
    todos_chk = QCheckBox("Mostrar en todos los satélites")
    todos_chk.setChecked(True)
    destinos_list = QListWidget()
    destinos_list.setMaximumHeight(120)
    destinos_list.setEnabled(False)  # habilitado solo si se destilda "todos"
    enviar_btn = QPushButton("Enviar anuncio")
    enviar_btn.setObjectName("primaryButton")
    resultado_lbl = QLabel("")
    resultado_lbl.setWordWrap(True)
    resultado_lbl.setObjectName("satStatus")

    # — Lista de activos —
    lista_box = QGroupBox("Anuncios activos")
    lista = QListWidget()
    quitar_btn = QPushButton("Quitar seleccionado")
    quitar_todos_btn = QPushButton("Quitar todos")

    def _refrescar_satelites() -> None:
        """Baja la lista de satélites conocidos + su estado encendido/apagado."""
        sat_estado.clear()
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services import satelite_registry_service as rsvc

            with get_session() as session:
                sat_estado.extend(rsvc.listar_con_estado(session))
        except Exception:  # noqa: BLE001
            pass
        # Lista de presencia (solo lectura).
        satelites_list.clear()
        if not sat_estado:
            satelites_list.addItem("(Sin satélites registrados o sin conexión)")
        else:
            for s in sat_estado:
                punto = "🟢" if s["online"] else "⚪"
                marca = "  (este)" if s["identificador"] == _mi_id else ""
                satelites_list.addItem(f"{punto}  {s['nombre']}{marca}")
        # Lista de destinos (checkable) para el nuevo anuncio.
        destinos_list.clear()
        for s in sat_estado:
            punto = "🟢" if s["online"] else "⚪"
            item = QListWidgetItem(f"{punto}  {s['nombre']}")
            item.setData(Qt.ItemDataRole.UserRole, s["identificador"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            destinos_list.addItem(item)

    def _guardar_nombre() -> None:
        try:
            from pos_uniformes.services.satellite_identity_service import set_satellite_name

            efectivo = set_satellite_name(nombre_in.text())
            nombre_in.setText(efectivo)
            QMessageBox.information(
                dialog,
                "Nombre guardado",
                f"Este satélite se llamará «{efectivo}». Se actualiza en la red en ~1 min.",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(dialog, "No se pudo guardar", str(exc))

    def _destinos_elegidos() -> list[str] | None:
        """None = todos; si no, los identificadores marcados."""
        if todos_chk.isChecked():
            return None
        elegidos: list[str] = []
        for i in range(destinos_list.count()):
            item = destinos_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                elegidos.append(item.data(Qt.ItemDataRole.UserRole))
        return elegidos or None

    def _quitar_imagen() -> None:
        estado_img.update(bytes=None, mime=None, nombre=None)
        imagen_lbl.setText("Sin imagen")
        quitar_img_btn.setVisible(False)

    def _elegir_imagen() -> None:
        path, _ = QFileDialog.getOpenFileName(
            dialog, "Elegir imagen", "", "Imágenes (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"
        )
        if not path:
            return
        try:
            from pos_uniformes.services.anuncio_image_service import preparar_imagen

            data, mime = preparar_imagen(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(dialog, "Imagen no válida", str(exc))
            return
        estado_img.update(bytes=data, mime=mime, nombre=Path(path).name)
        imagen_lbl.setText(f"{Path(path).name} — {len(data) // 1024} KB (reducida)")
        quitar_img_btn.setVisible(True)

    def _refrescar_lista() -> None:
        lista.clear()
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services import anuncio_service as asvc

            with get_session() as session:
                activos = asvc.listar_activos(session)
                for a in activos:
                    etiqueta = a.titulo or (a.mensaje or "")[:40] or "(imagen)"
                    if a.imagen is not None:
                        etiqueta += "  🖼"
                    if a.destinos:
                        destino = ", ".join(_nombre_de(x) for x in a.destinos)
                    else:
                        destino = "Todos"
                    etiqueta += f"   → {destino}"
                    item = QListWidgetItem(etiqueta)
                    item.setData(Qt.ItemDataRole.UserRole, a.id)
                    lista.addItem(item)
            if not activos:
                lista.addItem("(No hay anuncios activos)")
        except Exception:  # noqa: BLE001
            lista.addItem("(Sin conexión con la PC principal)")

    def _enviar() -> None:
        titulo = titulo_in.text().strip()
        mensaje = mensaje_in.toPlainText().strip()
        if not titulo and not mensaje and not estado_img["bytes"]:
            QMessageBox.warning(
                dialog, "Anuncio vacío", "Escribe un título o mensaje, o elige una imagen."
            )
            return
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services import anuncio_service as asvc

            with get_session() as session:
                anuncio = asvc.crear_anuncio(
                    session,
                    titulo=titulo or None,
                    mensaje=mensaje or None,
                    imagen=estado_img["bytes"],
                    imagen_mime=estado_img["mime"],
                    destinos=_destinos_elegidos(),
                    duracion_seg=duracion_in.value(),
                    creado_por="satelite",
                )
                if inmediato_chk.isChecked():
                    asvc.notificar(session, "inmediato", anuncio.id)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                dialog,
                "No se pudo enviar",
                f"¿La PC principal está encendida?\n\n{exc}",
            )
            return
        titulo_in.clear()
        mensaje_in.clear()
        _quitar_imagen()
        inmediato_chk.setChecked(False)
        resultado_lbl.setText("✅ Anuncio enviado.")
        _refrescar_lista()

    def _quitar_seleccionado() -> None:
        item = lista.currentItem()
        anuncio_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not anuncio_id:
            return
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services import anuncio_service as asvc

            with get_session() as session:
                asvc.desactivar(session, int(anuncio_id))
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(dialog, "No se pudo quitar", str(exc))
            return
        _refrescar_lista()

    def _quitar_todos() -> None:
        if (
            QMessageBox.question(
                dialog, "Quitar todos", "¿Quitar todos los anuncios activos?"
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services import anuncio_service as asvc

            with get_session() as session:
                asvc.desactivar_todos(session)
                session.commit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(dialog, "No se pudo quitar", str(exc))
            return
        _refrescar_lista()

    imagen_btn.clicked.connect(_elegir_imagen)
    quitar_img_btn.clicked.connect(_quitar_imagen)
    enviar_btn.clicked.connect(_enviar)
    quitar_btn.clicked.connect(_quitar_seleccionado)
    quitar_todos_btn.clicked.connect(_quitar_todos)
    guardar_nombre_btn.clicked.connect(_guardar_nombre)
    refrescar_sat_btn.clicked.connect(_refrescar_satelites)
    todos_chk.toggled.connect(lambda marcado: destinos_list.setEnabled(not marcado))

    # — Layout: Este satélite —
    este_layout = QVBoxLayout()
    este_hint = QLabel(
        "Ponle un nombre a esta pantalla para reconocerla al mandar anuncios."
    )
    este_hint.setWordWrap(True)
    este_layout.addWidget(este_hint)
    nombre_row = QHBoxLayout()
    nombre_row.addWidget(nombre_in, 1)
    nombre_row.addWidget(guardar_nombre_btn)
    este_layout.addLayout(nombre_row)
    este_layout.addWidget(id_lbl)
    este_box.setLayout(este_layout)

    # — Layout: Satélites —
    sat_layout = QVBoxLayout()
    sat_hint = QLabel("🟢 encendido · ⚪ apagado (sin señal reciente).")
    sat_hint.setWordWrap(True)
    sat_layout.addWidget(sat_hint)
    sat_layout.addWidget(satelites_list)
    sat_layout.addWidget(refrescar_sat_btn)
    satelites_box.setLayout(sat_layout)

    # — Layout: Crear —
    crear_layout = QVBoxLayout()
    crear_hint = QLabel(
        "Se muestra en la cartelera cuando el satélite está inactivo. Marca "
        "«Mostrar ahora» para que además salte de inmediato."
    )
    crear_hint.setWordWrap(True)
    crear_layout.addWidget(crear_hint)
    crear_layout.addWidget(titulo_in)
    crear_layout.addWidget(mensaje_in)
    img_row = QHBoxLayout()
    img_row.addWidget(imagen_btn)
    img_row.addWidget(quitar_img_btn)
    img_row.addWidget(imagen_lbl, 1)
    crear_layout.addLayout(img_row)
    crear_layout.addWidget(duracion_in)
    crear_layout.addWidget(inmediato_chk)
    crear_layout.addWidget(todos_chk)
    crear_layout.addWidget(QLabel("O elige en cuáles mostrarlo:"))
    crear_layout.addWidget(destinos_list)
    crear_layout.addWidget(enviar_btn)
    crear_layout.addWidget(resultado_lbl)
    crear_box.setLayout(crear_layout)

    # — Layout: Lista de activos —
    lista_layout = QVBoxLayout()
    lista_layout.addWidget(lista)
    lista_btn_row = QHBoxLayout()
    lista_btn_row.addWidget(quitar_btn)
    lista_btn_row.addWidget(quitar_todos_btn)
    lista_layout.addLayout(lista_btn_row)
    lista_box.setLayout(lista_layout)

    _refrescar_satelites()
    _refrescar_lista()
    return [este_box, satelites_box, crear_box, lista_box]


def open_satellite_admin_dialog(parent: QWidget) -> None:
    if not _prompt_pin(parent):
        QMessageBox.warning(parent, "PIN incorrecto", "PIN incorrecto.")
        return

    dialog = QDialog(parent)
    dialog.setWindowTitle("Administracion del satelite")
    dialog.setMinimumWidth(480)

    # — Estado actual —
    status_box = QGroupBox("Estado de conexion")
    status_form = QFormLayout()
    status_form.setSpacing(8)
    current_host_label = QLabel(settings.db_host)
    current_host_label.setObjectName("subtleLine")
    env_path_label = QLabel(str(_find_env_path()))
    env_path_label.setWordWrap(True)
    env_path_label.setObjectName("subtleLine")
    status_form.addRow("Host actual:", current_host_label)
    status_form.addRow("Archivo .env:", env_path_label)
    status_box.setLayout(status_form)

    # — Conexion —
    config_box = QGroupBox("Cambiar conexion")
    config_form = QFormLayout()
    config_form.setSpacing(8)
    host_input = QLineEdit(settings.db_host)
    host_input.setPlaceholderText("192.168.0.10")
    password_input = QLineEdit(settings.db_password)
    password_input.setEchoMode(QLineEdit.EchoMode.Password)
    password_input.setPlaceholderText("Contrasena de la base de datos")
    config_form.addRow("Host (IP PC principal):", host_input)
    config_form.addRow("Contrasena BD:", password_input)

    test_result_label = QLabel("")
    test_result_label.setWordWrap(True)
    test_btn = QPushButton("Probar conexion")
    save_conn_btn = QPushButton("Guardar y reiniciar")
    save_conn_btn.setObjectName("primaryButton")

    def handle_test() -> None:
        host = host_input.text().strip()
        if not host:
            test_result_label.setText("Ingresa una IP.")
            return
        test_result_label.setText(f"Probando {host}...")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        if probe_database_host(override_host=host):
            test_result_label.setText(f"✓ Conexion exitosa a {host}")
            test_result_label.setStyleSheet("color: green;")
        else:
            test_result_label.setText(f"✗ Sin respuesta en {host}. Verifica IP y que la PC principal este encendida.")
            test_result_label.setStyleSheet("color: red;")

    def handle_save_conn() -> None:
        host = host_input.text().strip()
        password = password_input.text().strip()
        if not host:
            QMessageBox.warning(dialog, "Datos incompletos", "Ingresa el host.")
            return
        try:
            _write_env(host, password)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Error al guardar", f"No se pudo escribir .env:\n{exc}")
            return
        QMessageBox.information(dialog, "Guardado", f"Configuracion guardada. Reiniciando hacia {host}.")
        dialog.accept()
        _restart_app()

    test_btn.clicked.connect(handle_test)
    save_conn_btn.clicked.connect(handle_save_conn)
    conn_btn_row = QHBoxLayout()
    conn_btn_row.addWidget(test_btn)
    conn_btn_row.addWidget(save_conn_btn)

    config_layout = QVBoxLayout()
    config_layout.addLayout(config_form)
    config_layout.addWidget(test_result_label)
    config_layout.addLayout(conn_btn_row)
    config_box.setLayout(config_layout)

    # — Impresora de tickets —
    printer_box = QGroupBox("Impresora de tickets")
    printer_form = QFormLayout()
    printer_form.setSpacing(8)

    cached_printer, cached_copies = load_ticket_print_settings()

    printer_combo = QComboBox()
    printer_combo.addItem("Impresora predeterminada del sistema", "")
    for p in QPrinterInfo.availablePrinters():
        printer_combo.addItem(p.printerName(), p.printerName())

    # Seleccionar la impresora guardada
    idx = printer_combo.findData(cached_printer)
    printer_combo.setCurrentIndex(idx if idx >= 0 else 0)

    copies_spin = QSpinBox()
    copies_spin.setRange(1, 5)
    copies_spin.setValue(cached_copies)

    printer_form.addRow("Impresora:", printer_combo)
    printer_form.addRow("Copias:", copies_spin)

    save_printer_btn = QPushButton("Guardar preferencias de impresion")
    save_printer_btn.setObjectName("primaryButton")

    def handle_save_printer() -> None:
        selected = str(printer_combo.currentData() or "")
        copies = copies_spin.value()
        try:
            save_ticket_print_settings(selected, copies)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Error", f"No se pudo guardar:\n{exc}")
            return
        name = printer_combo.currentText()
        QMessageBox.information(dialog, "Guardado", f"Impresora '{name}' guardada para tickets.")

    save_printer_btn.clicked.connect(handle_save_printer)

    printer_layout = QVBoxLayout()
    printer_layout.addLayout(printer_form)
    printer_layout.addWidget(save_printer_btn)
    printer_box.setLayout(printer_layout)

    # — Impresoras de etiquetas (una por tipo de rollo) —
    from pos_uniformes.services.label_printer_settings_cache_service import (
        load_label_printer_settings,
        save_label_printer_settings,
    )

    label_box = QGroupBox("Impresoras de etiquetas")
    label_form = QFormLayout()
    label_form.setSpacing(8)

    cached_normal, cached_label = load_label_printer_settings()

    def _build_label_combo(selected: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem("Autodetectar (Brother)", "")
        for p in QPrinterInfo.availablePrinters():
            combo.addItem(p.printerName(), p.printerName())
        found = combo.findData(selected)
        combo.setCurrentIndex(found if found >= 0 else 0)
        return combo

    normal_label_combo = _build_label_combo(cached_normal)
    label_label_combo = _build_label_combo(cached_label)

    label_form.addRow("Normal / Split / Continua:", normal_label_combo)
    label_form.addRow("Label (troquelada):", label_label_combo)

    save_label_btn = QPushButton("Guardar impresoras de etiquetas")
    save_label_btn.setObjectName("primaryButton")

    def handle_save_label_printers() -> None:
        normal_sel = str(normal_label_combo.currentData() or "")
        label_sel = str(label_label_combo.currentData() or "")
        try:
            save_label_printer_settings(normal_sel, label_sel)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Error", f"No se pudo guardar:\n{exc}")
            return
        QMessageBox.information(
            dialog,
            "Guardado",
            "Impresoras de etiquetas guardadas.\n"
            f"Normal/Split/Continua: {normal_label_combo.currentText()}\n"
            f"Label: {label_label_combo.currentText()}",
        )

    save_label_btn.clicked.connect(handle_save_label_printers)

    label_layout = QVBoxLayout()
    label_layout.addWidget(
        QLabel("Normal, Split y Continua salen a la primera; Label (rollo troquelado) a la segunda.")
    )
    label_layout.addLayout(label_form)
    label_layout.addWidget(save_label_btn)
    label_box.setLayout(label_layout)

    # — Impresión ESC/POS (crudo) de tickets —
    from pos_uniformes.services.escpos_settings_cache_service import (
        EscPosSettings,
        load_escpos_settings,
        save_escpos_settings,
    )

    escpos_box = QGroupBox("Impresión de tickets (ESC/POS)")
    escpos_layout = QVBoxLayout()
    escpos_help = QLabel(
        "ESC/POS manda el texto directo a la térmica (sin el driver de Windows), "
        "así la 1ª hoja no sale ancha/recortada y el corte es exacto. Si la caja o "
        "los acentos salen raros, ajusta el «Codepage» y vuelve a probar."
    )
    escpos_help.setWordWrap(True)
    _esc = load_escpos_settings()
    escpos_enabled = QCheckBox("Usar ESC/POS crudo (recomendado para térmica)")
    escpos_enabled.setChecked(_esc.enabled)
    escpos_fullcut = QCheckBox("Corte total (desmarca para corte parcial)")
    escpos_fullcut.setChecked(_esc.full_cut)
    escpos_form = QFormLayout()
    escpos_codepage = QSpinBox()
    escpos_codepage.setRange(0, 255)
    escpos_codepage.setValue(_esc.codepage)
    escpos_form.addRow("Codepage (ESC t n; 2 = CP850):", escpos_codepage)
    escpos_feed = QSpinBox()
    escpos_feed.setRange(0, 20)
    escpos_feed.setValue(_esc.feed_lines)
    escpos_form.addRow("Líneas antes del corte:", escpos_feed)

    def _escpos_actuales() -> EscPosSettings:
        return EscPosSettings(
            enabled=escpos_enabled.isChecked(),
            codepage=escpos_codepage.value(),
            encoding=_esc.encoding,
            feed_lines=escpos_feed.value(),
            full_cut=escpos_fullcut.isChecked(),
        )

    save_escpos_btn = QPushButton("Guardar ESC/POS")
    save_escpos_btn.setObjectName("primaryButton")

    def handle_save_escpos() -> None:
        try:
            save_escpos_settings(_escpos_actuales())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Error", f"No se pudo guardar:\n{exc}")
            return
        QMessageBox.information(dialog, "Guardado", "Ajustes ESC/POS guardados.")

    save_escpos_btn.clicked.connect(handle_save_escpos)

    test_escpos_btn = QPushButton("Imprimir hoja de prueba")
    test_escpos_btn.setObjectName("secondaryButton")

    def handle_test_escpos() -> None:
        printer_name = str(printer_combo.currentData() or "")
        if not printer_name:
            QMessageBox.warning(
                dialog, "Sin impresora",
                "Elige primero la impresora de tickets arriba.",
            )
            return
        prueba = (
            "┌────────────────────────────────────┐\n"
            "│           HOJA DE PRUEBA           │\n"
            "├────────────────────────────────────┤\n"
            "│         PRODUCTOS BÁSICOS          │\n"
            "│ Suéter · Falda Escocés · Camisón   │\n"
            "├────────────────────────────────────┤\n"
            "│ Talla        Exist.    Pedido      │\n"
            "│ 9-12          ____      ____       │\n"
            "│ 13-18         ____      ____       │\n"
            "└────────────────────────────────────┘\n"
        )
        try:
            from pos_uniformes.ui.helpers.escpos_ticket_print_helper import (
                print_ticket_escpos,
            )

            print_ticket_escpos(printer_name, prueba, copies=1)
            QMessageBox.information(
                dialog, "Enviado",
                "Se envió la hoja de prueba. Revisa la caja, los acentos y el corte.",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                dialog, "Error",
                f"No se pudo imprimir la prueba (¿Windows/impresora?):\n{exc}",
            )

    test_escpos_btn.clicked.connect(handle_test_escpos)

    escpos_layout.addWidget(escpos_help)
    escpos_layout.addWidget(escpos_enabled)
    escpos_layout.addWidget(escpos_fullcut)
    escpos_layout.addLayout(escpos_form)
    escpos_btn_row = QHBoxLayout()
    escpos_btn_row.addWidget(save_escpos_btn)
    escpos_btn_row.addWidget(test_escpos_btn)
    escpos_btn_row.addStretch()
    escpos_layout.addLayout(escpos_btn_row)
    escpos_box.setLayout(escpos_layout)

    # — Meilisearch —
    meili_box = QGroupBox("Meilisearch (busqueda rapida)")
    meili_layout = QVBoxLayout()
    meili_layout.setSpacing(8)

    # Diagnostico
    meili_diag_form = QFormLayout()
    meili_diag_form.setSpacing(4)
    meili_status_label = QLabel("")
    meili_status_label.setWordWrap(True)
    meili_docs_label = QLabel("")
    meili_docs_label.setObjectName("subtleLine")
    meili_binary_label = QLabel("")
    meili_binary_label.setObjectName("subtleLine")
    meili_task_label = QLabel("")
    meili_task_label.setObjectName("subtleLine")

    def refresh_meili_diagnostics() -> None:
        import shutil
        from pathlib import Path
        # Conexion
        try:
            from pos_uniformes.services.meilisearch_service import is_available, _get_client
            if is_available():
                meili_status_label.setText("✓ Conectado (127.0.0.1:7700)")
                meili_status_label.setStyleSheet("color: green; font-weight: bold;")
                # Doc count
                try:
                    client = _get_client()
                    stats = client.index("variantes").get_stats()
                    n_docs = getattr(stats, "number_of_documents", None)
                    if n_docs is None:
                        n_docs = stats.get("numberOfDocuments", "?") if isinstance(stats, dict) else "?"
                    meili_docs_label.setText(f"{n_docs} documentos indexados")
                except Exception:
                    meili_docs_label.setText("No se pudo leer stats del indice")
            else:
                meili_status_label.setText("✗ No disponible")
                meili_status_label.setStyleSheet("color: red; font-weight: bold;")
                meili_docs_label.setText("—")
        except Exception:
            meili_status_label.setText("✗ No disponible")
            meili_status_label.setStyleSheet("color: red; font-weight: bold;")
            meili_docs_label.setText("—")
        # Binario — multiplataforma
        if sys.platform == "win32":
            bin_path = Path(r"C:\Meilisearch\meilisearch.exe")
            found = bin_path.exists()
            bin_display = str(bin_path)
        else:
            bin_which = shutil.which("meilisearch")
            found = bin_which is not None
            bin_display = bin_which or "meilisearch"
        meili_binary_label.setText(
            f"✓ Binario: {bin_display}" if found else "✗ Binario no encontrado"
        )
        meili_binary_label.setStyleSheet("color: green;" if found else "color: orange;")
        # Tarea programada / servicio
        if sys.platform == "win32":
            try:
                import subprocess
                result = subprocess.run(
                    ["schtasks", "/Query", "/TN", "MeilisearchPOS", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode == 0 and "MeilisearchPOS" in result.stdout:
                    meili_task_label.setText("✓ Tarea programada 'MeilisearchPOS' activa")
                    meili_task_label.setStyleSheet("color: green;")
                else:
                    meili_task_label.setText("✗ Sin tarea programada (no arranca al encender PC)")
                    meili_task_label.setStyleSheet("color: orange;")
            except Exception:
                meili_task_label.setText("? No se pudo verificar tarea programada")
        elif sys.platform == "darwin":
            try:
                import subprocess
                result = subprocess.run(
                    ["pgrep", "-x", "meilisearch"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    meili_task_label.setText("✓ Proceso meilisearch activo")
                    meili_task_label.setStyleSheet("color: green;")
                else:
                    meili_task_label.setText("— Proceso no detectado (puede estar en otra maquina)")
                    meili_task_label.setStyleSheet("color: orange;")
            except Exception:
                meili_task_label.setText("? No se pudo verificar proceso")
        else:
            meili_task_label.setText("— Verificacion no disponible en esta plataforma")

    refresh_meili_diagnostics()

    meili_diag_form.addRow("Estado:", meili_status_label)
    meili_diag_form.addRow("Indice:", meili_docs_label)
    meili_diag_form.addRow("Binario:", meili_binary_label)
    meili_diag_form.addRow("Autostart:", meili_task_label)

    # Botones de accion
    install_btn = QPushButton("Instalar / iniciar")
    reindex_btn = QPushButton("Re-indexar catalogo")
    autostart_btn = QPushButton("Crear tarea programada")
    meili_result_label = QLabel("")
    meili_result_label.setWordWrap(True)

    def _set_meili_busy(busy: bool) -> None:
        install_btn.setEnabled(not busy)
        reindex_btn.setEnabled(not busy)
        autostart_btn.setEnabled(not busy)

    def handle_reindex() -> None:
        _set_meili_busy(True)
        meili_result_label.setText("Verificando conexion a base de datos...")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        if not probe_database_host():
            meili_result_label.setText(
                "✗ No se puede re-indexar: la PC principal no responde.\n"
                "Enciende la PC principal y vuelve a intentar."
            )
            meili_result_label.setStyleSheet("color: red;")
            _set_meili_busy(False)
            return
        meili_result_label.setText("Indexando...")
        QApplication.processEvents()
        try:
            from pos_uniformes.services.meilisearch_service import configure_index, index_from_db, _get_client
            if _get_client() is None:
                meili_result_label.setText("✗ No se pudo conectar con Meilisearch en 127.0.0.1:7700")
                meili_result_label.setStyleSheet("color: red;")
                _set_meili_busy(False)
                return
            configure_index()
            from pos_uniformes.database.connection import get_session
            with get_session() as session:
                count = index_from_db(session)
            meili_result_label.setText(f"✓ Indexados: {count} documentos")
            meili_result_label.setStyleSheet("color: green;")
        except Exception as exc:
            meili_result_label.setText(f"✗ Error: {exc}")
            meili_result_label.setStyleSheet("color: red;")
        refresh_meili_diagnostics()
        _set_meili_busy(False)

    def handle_install() -> None:
        _set_meili_busy(True)
        meili_result_label.setText("Verificando...")
        from PyQt6.QtWidgets import QApplication

        def on_progress(msg: str) -> None:
            meili_result_label.setText(msg)
            QApplication.processEvents()

        try:
            from pos_uniformes.services.meilisearch_service import ensure_installed, is_available
            result = ensure_installed(on_progress=on_progress)
            meili_result_label.setText(result)
            if is_available():
                meili_result_label.setStyleSheet("color: green;")
                refresh_meili_diagnostics()
                handle_reindex()
                return
            else:
                meili_result_label.setStyleSheet("color: orange;")
        except Exception as exc:
            meili_result_label.setText(f"✗ Error: {exc}")
            meili_result_label.setStyleSheet("color: red;")
        refresh_meili_diagnostics()
        _set_meili_busy(False)

    def handle_create_scheduled_task() -> None:
        _set_meili_busy(True)
        meili_result_label.setText("Creando tarea programada...")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        try:
            import subprocess
            bin_path = r"C:\Meilisearch\meilisearch.exe"
            args = "--no-analytics --db-path C:\\Meilisearch\\data --http-addr 127.0.0.1:7700"
            result = subprocess.run(
                [
                    "schtasks", "/Create",
                    "/TN", "MeilisearchPOS",
                    "/TR", f'"{bin_path}" {args}',
                    "/SC", "ONLOGON",
                    "/RL", "HIGHEST",
                    "/F",
                ],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                meili_result_label.setText("✓ Tarea 'MeilisearchPOS' creada — arrancara al iniciar sesion")
                meili_result_label.setStyleSheet("color: green;")
            else:
                meili_result_label.setText(f"✗ Error: {result.stderr.strip() or result.stdout.strip()}")
                meili_result_label.setStyleSheet("color: red;")
        except Exception as exc:
            meili_result_label.setText(f"✗ Error: {exc}")
            meili_result_label.setStyleSheet("color: red;")
        refresh_meili_diagnostics()
        _set_meili_busy(False)

    install_btn.clicked.connect(handle_install)
    reindex_btn.clicked.connect(handle_reindex)
    autostart_btn.clicked.connect(handle_create_scheduled_task)

    btn_row = QHBoxLayout()
    btn_row.addWidget(install_btn)
    btn_row.addWidget(reindex_btn)
    btn_row.addWidget(autostart_btn)

    meili_layout.addLayout(meili_diag_form)
    meili_layout.addLayout(btn_row)
    meili_layout.addWidget(meili_result_label)
    meili_box.setLayout(meili_layout)

    # — Modo de impresión (ajuste por máquina) —
    from pos_uniformes.services.print_routing_cache_service import (
        MODO_LOCAL,
        MODO_SATELITE,
        load_print_routing,
        save_print_routing,
    )

    routing_box = QGroupBox("Rol de impresión de esta PC")
    routing_layout = QVBoxLayout()
    routing_help = QLabel(
        "Servidor de impresión: esta PC tiene las impresoras conectadas e imprime "
        "tanto lo suyo como lo que le mandan las estaciones.\n"
        "Estación: no tiene impresoras; envía todo (tickets, etiquetas y conteo) al "
        "servidor. Las estaciones no configuran ninguna impresora."
    )
    routing_help.setWordWrap(True)

    current_modo, current_origen = load_print_routing()
    radio_local = QRadioButton("🖨  Servidor de impresión (esta PC tiene las impresoras)")
    radio_sat = QRadioButton("📡  Estación (envía todo al servidor)")
    (radio_sat if current_modo == MODO_SATELITE else radio_local).setChecked(True)

    origen_form = QFormLayout()
    origen_edit = QLineEdit(current_origen)
    origen_edit.setPlaceholderText("principal / kiosko / caja 2")
    origen_form.addRow("Nombre de esta PC:", origen_edit)

    save_routing_btn = QPushButton("Guardar rol")
    save_routing_btn.setObjectName("primaryButton")

    def handle_save_routing() -> None:
        modo = MODO_SATELITE if radio_sat.isChecked() else MODO_LOCAL
        origen = origen_edit.text().strip() or "principal"
        try:
            save_print_routing(modo, origen)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(dialog, "Error", f"No se pudo guardar:\n{exc}")
            return
        etiqueta = (
            "Estación (envía al servidor)"
            if modo == MODO_SATELITE
            else "Servidor de impresión (imprime local)"
        )
        QMessageBox.information(dialog, "Guardado", f"Esta PC ahora es: {etiqueta}.")

    save_routing_btn.clicked.connect(handle_save_routing)

    routing_layout.addWidget(routing_help)
    routing_layout.addWidget(radio_local)
    routing_layout.addWidget(radio_sat)
    routing_layout.addLayout(origen_form)
    routing_layout.addWidget(save_routing_btn)
    routing_box.setLayout(routing_layout)

    # Las estaciones no tienen impresoras: se ocultan las cajas de config de
    # impresora de tickets y de etiquetas (así no intentan autodetectar hardware
    # que no existe) y se muestra un aviso. El servidor de impresión sí las ve.
    estacion_hint = QLabel(
        "📡  Esta PC es una Estación: no detecta ni configura impresoras. "
        "Todo se imprime en el Servidor de impresión. Si esta PC tiene las "
        "impresoras conectadas, cámbiala a «Servidor de impresión» arriba."
    )
    estacion_hint.setWordWrap(True)
    estacion_hint.setObjectName("satStatus")

    def _aplicar_visibilidad_rol(es_servidor: bool) -> None:
        printer_box.setVisible(es_servidor)
        label_box.setVisible(es_servidor)
        escpos_box.setVisible(es_servidor)
        estacion_hint.setVisible(not es_servidor)

    # radio_local y radio_sat son mutuamente exclusivos (mismo padre): basta
    # escuchar el toggle del de servidor. Aplicar estado inicial según el cache.
    radio_local.toggled.connect(_aplicar_visibilidad_rol)
    _aplicar_visibilidad_rol(current_modo != MODO_SATELITE)

    # — Cerrar —
    close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close_buttons.rejected.connect(dialog.reject)

    # Rediseño en pestañas: antes eran 5 secciones apiladas (saturado en el
    # táctil, Meilisearch quedaba fuera). Ahora se agrupan en 3 pestañas
    # despejadas; cada una con su propio scroll por si la pantalla es chica.
    def _make_tab(*boxes: QWidget) -> QScrollArea:
        page_layout = QVBoxLayout()
        page_layout.setSpacing(16)
        page_layout.setContentsMargins(12, 12, 12, 12)
        for box in boxes:
            page_layout.addWidget(box)
        page_layout.addStretch()
        page = QWidget()
        page.setLayout(page_layout)
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setWidget(page)
        page_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        # Sin esto, el viewport pinta el color del SISTEMA (negro en modo
        # oscuro) detrás de las tarjetas crema.
        page_scroll.setStyleSheet(
            "QScrollArea { background: #f4ede2; }"
            "QScrollArea > QWidget > QWidget { background: #f4ede2; }"
        )
        return page_scroll

    # — Conteos (calendario admin) —
    conteo_box = QGroupBox("Calendario de conteos")
    conteo_layout = QVBoxLayout()
    conteo_hint = QLabel(
        "Configura la frecuencia de conteo por escuela y revisa cuáles ya "
        "requieren conteo (lista y calendario)."
    )
    conteo_hint.setWordWrap(True)
    open_calendario_btn = QPushButton("Abrir calendario de conteos")
    open_calendario_btn.setObjectName("primaryButton")

    def _abrir_calendario_conteos() -> None:
        from pos_uniformes.ui.dialogs.conteo_calendario_dialog import ConteoCalendarioDialog

        ConteoCalendarioDialog(dialog).exec()

    open_calendario_btn.clicked.connect(_abrir_calendario_conteos)

    subir_conteo_btn = QPushButton("Subir conteo (registrar físico)")
    subir_conteo_btn.setObjectName("secondaryButton")

    def _abrir_subir_conteo() -> None:
        from pos_uniformes.ui.dialogs.conteo_subir_dialog import ConteoSubirDialog

        ConteoSubirDialog(dialog).exec()

    subir_conteo_btn.clicked.connect(_abrir_subir_conteo)

    conteo_layout.addWidget(conteo_hint)
    conteo_layout.addWidget(open_calendario_btn)
    conteo_layout.addWidget(subir_conteo_btn)
    conteo_layout.addStretch()
    conteo_box.setLayout(conteo_layout)

    # — Anuncios / Cartelera —
    # Nunca impedir que el menú admin abra si la pestaña de anuncios falla al
    # construirse (p.ej. DB en estado raro): se omite la pestaña y ya.
    try:
        anuncios_boxes = _build_anuncios_boxes(dialog)
    except Exception:  # noqa: BLE001
        anuncios_boxes = []

    # — Actualizaciones (buscar y aplicar vía el lanzador) —
    update_box = QGroupBox("Actualizaciones")
    update_layout = QVBoxLayout()
    try:
        from pos_uniformes.services.satellite_update_service import version_local

        _version_txt = version_local()
    except Exception:  # noqa: BLE001
        _version_txt = "?"
    update_hint = QLabel(
        f"Versión instalada: {_version_txt}. Al actualizar, la app se cierra y "
        "el lanzador copia la versión nueva desde la PC principal y la reabre."
    )
    update_hint.setWordWrap(True)
    buscar_updates_btn = QPushButton("🔄 Buscar actualizaciones")
    buscar_updates_btn.setObjectName("secondaryButton")

    def _buscar_updates() -> None:
        handler = getattr(parent, "buscar_actualizaciones_interactivo", None)
        if handler is not None:
            handler(dialog)

    buscar_updates_btn.clicked.connect(_buscar_updates)
    update_layout.addWidget(update_hint)
    update_layout.addWidget(buscar_updates_btn)
    update_layout.addStretch()
    update_box.setLayout(update_layout)

    tabs = QTabWidget()
    tabs.addTab(_make_tab(status_box, config_box, update_box), "🔌  Conexión")
    tabs.addTab(
        _make_tab(routing_box, estacion_hint, printer_box, label_box, escpos_box),
        "🖨  Impresoras",
    )
    tabs.addTab(_make_tab(meili_box), "🔍  Búsqueda")
    tabs.addTab(_make_tab(conteo_box), "📋  Conteos")
    if anuncios_boxes:
        tabs.addTab(_make_tab(*anuncios_boxes), "📣  Anuncios")

    outer = QVBoxLayout()
    outer.setContentsMargins(12, 12, 12, 12)
    outer.addWidget(tabs)
    outer.addWidget(close_buttons)
    dialog.setLayout(outer)

    # Tamaño acotado a la pantalla; cada pestaña scrollea si hace falta.
    screen = dialog.screen() or QApplication.primaryScreen()
    if screen is not None:
        avail = screen.availableGeometry()
        dialog.resize(max(560, int(avail.width() * 0.5)), int(avail.height() * 0.8))
        dialog.setMaximumHeight(avail.height())

    dialog.exec()
