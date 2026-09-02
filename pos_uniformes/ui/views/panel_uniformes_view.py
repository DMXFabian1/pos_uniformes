"""Vista que embebe el Panel de Uniformes dentro de la app via QWebEngineView.

Genera el HTML con subprocess y lo muestra en un QWebEngineView.
Incluye un bridge JS↔Python (QWebChannel) para operaciones de conteo de inventario.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal, pyqtSlot, QObject
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pos_uniformes.ui.main_window import MainWindow


# ---------------------------------------------------------------------------
# Background worker for panel generation
# ---------------------------------------------------------------------------

class _PanelGeneratorWorker(QThread):
    finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, script_path: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._script = script_path

    def run(self) -> None:
        try:
            result = subprocess.run(
                [sys.executable, str(self._script)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                self.finished.emit(False, result.stderr[:500])
            else:
                self.finished.emit(True, result.stdout.strip())
        except Exception as exc:  # noqa: BLE001
            self.finished.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Bridge JS ↔ Python via QWebChannel
# ---------------------------------------------------------------------------

class PanelBridge(QObject):
    """Métodos expuestos al JavaScript del panel via QWebChannel."""

    def __init__(self, parent: QObject | None = None, window: object | None = None) -> None:
        super().__init__(parent)
        self._window = window

    @staticmethod
    def _parse_key(key: str | int) -> tuple[int, int | None]:
        """Parsea 'eid:nid' → (escuela_id, nivel_id|None)."""
        s = str(key)
        if ":" in s:
            parts = s.split(":")
            eid = int(parts[0])
            nid = int(parts[1]) if len(parts) > 1 and parts[1] and parts[1] != "0" else None
            return eid, nid
        return int(s), None

    @pyqtSlot(str, result=str)
    def getVariantesParaConteo(self, key: str) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import (
            obtener_variantes_basicos_para_conteo,
            obtener_variantes_para_conteo,
        )

        try:
            with get_session() as session:
                if key == "basicos":
                    variantes = obtener_variantes_basicos_para_conteo(session)
                else:
                    eid, nid = self._parse_key(key)
                    variantes = obtener_variantes_para_conteo(session, eid, nivel_id=nid)
                data = [
                    {
                        "variante_id": v.variante_id,
                        "sku": v.sku,
                        "producto_nombre": v.producto_nombre,
                        "talla": v.talla,
                        "color": v.color,
                        "stock_actual": v.stock_actual,
                        "ultimo_conteo_at": v.ultimo_conteo_at.isoformat() if v.ultimo_conteo_at else None,
                        "dias_desde_conteo": v.dias_desde_conteo,
                        "requiere_conteo": v.requiere_conteo,
                    }
                    for v in variantes
                ]
                return json.dumps({"ok": True, "data": data})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(str, result=str)
    def getVariantesAgrupadas(self, key: str) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import (
            obtener_variantes_agrupadas_por_producto,
            obtener_variantes_basicos_agrupadas,
        )

        try:
            with get_session() as session:
                if key == "basicos":
                    grupos = obtener_variantes_basicos_agrupadas(session)
                else:
                    eid, nid = self._parse_key(key)
                    grupos = obtener_variantes_agrupadas_por_producto(session, eid, nivel_id=nid)
                data = []
                for g in grupos:
                    data.append({
                        "producto_nombre": g["producto_nombre"],
                        "tipo_pieza": g["tipo_pieza"],
                        "virtual": g["virtual"],
                        "variantes": [
                            {
                                "variante_id": v.variante_id,
                                "sku": v.sku,
                                "talla": v.talla,
                                "color": v.color,
                                "stock_actual": v.stock_actual,
                                "stock_bodega": v.stock_bodega,
                                "stock_piso": v.stock_piso,
                                "stock_tienda": v.stock_tienda,
                                "ultimo_conteo_at": v.ultimo_conteo_at.isoformat() if v.ultimo_conteo_at else None,
                                "dias_desde_conteo": v.dias_desde_conteo,
                                "requiere_conteo": v.requiere_conteo,
                            }
                            for v in g["variantes"]
                        ],
                    })
                return json.dumps({"ok": True, "data": data})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(str, result=str)
    def guardarConteo(self, data_json: str) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import (
            ConteoInput,
            registrar_conteos_lote,
        )

        try:
            payload = json.loads(data_json)
            conteos = [
                ConteoInput(
                    variante_id=int(c["variante_id"]),
                    stock_fisico=int(c["stock_fisico"]),
                    notas=c.get("notas"),
                )
                for c in payload["conteos"]
            ]
            contado_por = payload["contado_por"]

            with get_session() as session:
                resultado = registrar_conteos_lote(session, conteos, contado_por)
                session.commit()
                return json.dumps({
                    "ok": True,
                    "total": resultado.total_contados,
                    "con_diferencia": resultado.con_diferencia,
                    "sin_diferencia": resultado.sin_diferencia,
                })
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(str, result=str)
    def confirmarAjuste(self, conteo_ids_json: str) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import confirmar_ajustes_lote

        try:
            conteo_ids = json.loads(conteo_ids_json)
            usuario = "ADMIN"
            if self._window is not None:
                usuario = (
                    getattr(self._window, "current_full_name", "")
                    or getattr(self._window, "current_username", "")
                    or "ADMIN"
                )
            with get_session() as session:
                ajustados, omitidos = confirmar_ajustes_lote(
                    session, conteo_ids, usuario
                )
                session.commit()

                # Refrescar inventario en la tabla principal
                if ajustados > 0 and self._window is not None:
                    try:
                        self._window._invalidate_listing_snapshot_caches(
                            catalog=False, inventory=True,
                        )
                        self._window._refresh_inventory_table()
                    except Exception:
                        pass

                return json.dumps({
                    "ok": True,
                    "ajustados": ajustados,
                    "omitidos": omitidos,
                })
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(int, int, result=str)
    def getConteosPendientes(self, escuela_id: int, nivel_id: int = 0) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import obtener_conteos_pendientes

        try:
            eid = escuela_id if escuela_id > 0 else None
            nid = nivel_id if nivel_id > 0 else None
            with get_session() as session:
                conteos = obtener_conteos_pendientes(session, eid, nivel_id=nid)
                data = [
                    {
                        "id": c.id,
                        "variante_id": c.variante_id,
                        "sku": c.variante.sku if c.variante else "?",
                        "producto": c.variante.producto.nombre if c.variante and c.variante.producto else "?",
                        "stock_sistema": c.stock_sistema,
                        "stock_fisico": c.stock_fisico,
                        "diferencia": c.diferencia,
                        "contado_por": c.contado_por,
                        "contado_at": c.contado_at.isoformat() if c.contado_at else None,
                    }
                    for c in conteos
                ]
                return json.dumps({"ok": True, "data": data})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(str, result=str)
    def getEstadoConteo(self, key: str) -> str:
        from datetime import datetime, timezone

        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import (
            obtener_estado_conteo_basicos,
            obtener_estado_conteo_escuela,
        )

        try:
            with get_session() as session:
                if key == "basicos":
                    e = obtener_estado_conteo_basicos(session)
                else:
                    eid, nid = self._parse_key(key)
                    e = obtener_estado_conteo_escuela(session, eid, nivel_id=nid)

                # Días desde el último conteo (None = nunca contado).
                dias_sin_contar = None
                if e.ultimo_conteo is not None:
                    ultimo = e.ultimo_conteo
                    if ultimo.tzinfo is None:
                        ultimo = ultimo.replace(tzinfo=timezone.utc)
                    dias_sin_contar = max(0, (datetime.now(timezone.utc) - ultimo).days)

                return json.dumps({
                    "ok": True,
                    "escuela_nombre": e.escuela_nombre,
                    "dias_vigencia": e.dias_vigencia,
                    "total_variantes": e.total_variantes,
                    "contadas_vigentes": e.contadas_vigentes,
                    "pendientes_conteo": e.pendientes_conteo,
                    "pct_vigente": e.pct_vigente,
                    "ultimo_conteo": e.ultimo_conteo.isoformat() if e.ultimo_conteo else None,
                    "dias_sin_contar": dias_sin_contar,
                })
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(str, result=str)
    def getConfigConteo(self, key: str) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.database.models import ConfigConteoEscuela
        from pos_uniformes.services.conteo_service import DIAS_VIGENCIA_DEFAULT

        try:
            from sqlalchemy import select

            eid, _ = self._parse_key(key)
            with get_session() as session:
                config = session.scalar(
                    select(ConfigConteoEscuela).where(
                        ConfigConteoEscuela.escuela_id == eid
                    )
                )
                dias = config.dias_vigencia if config else DIAS_VIGENCIA_DEFAULT
                return json.dumps({"ok": True, "dias_vigencia": dias})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(int, int, result=str)
    def setConfigConteo(self, escuela_id: int, dias_vigencia: int) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import (
            ESCUELA_ID_BASICOS,
            guardar_config_conteo,
            guardar_dias_vigencia_basicos,
        )

        try:
            with get_session() as session:
                if escuela_id == ESCUELA_ID_BASICOS:
                    guardar_dias_vigencia_basicos(session, dias_vigencia)
                else:
                    guardar_config_conteo(session, escuela_id, dias_vigencia)
                session.commit()
                return json.dumps({"ok": True})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(int, int, result=str)
    def getHistorialConteos(self, escuela_id: int, limite: int) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import obtener_historial_conteos

        try:
            with get_session() as session:
                conteos = obtener_historial_conteos(session, escuela_id, limite or 50)
                data = [
                    {
                        "id": c.id,
                        "sku": c.variante.sku if c.variante else "?",
                        "producto": c.variante.producto.nombre if c.variante and c.variante.producto else "?",
                        "stock_sistema": c.stock_sistema,
                        "stock_fisico": c.stock_fisico,
                        "diferencia": c.diferencia,
                        "ajustado": c.ajustado,
                        "contado_por": c.contado_por,
                        "contado_at": c.contado_at.isoformat() if c.contado_at else None,
                        "notas": c.notas,
                    }
                    for c in conteos
                ]
                return json.dumps({"ok": True, "data": data})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(int, result=str)
    def toggleDisponibilidadOculta(self, variante_id: int) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.database.models import Variante
        from sqlalchemy import select

        try:
            with get_session() as session:
                v = session.scalar(
                    select(Variante).where(Variante.id == variante_id)
                )
                if v is None:
                    return json.dumps({"ok": False, "error": "Variante no encontrada"})
                v.disponibilidad_oculta = not v.disponibilidad_oculta
                session.commit()
                return json.dumps({"ok": True, "oculta": v.disponibilidad_oculta})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(str, str, str, str, result=str)
    def imprimirHojasConteo(self, key: str, escuela_nombre: str,
                            nivel_nombre: str = "", escuela_num: str = "") -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_sheet_service import (
            build_conteo_sheets,
            build_conteo_sheets_basicos,
        )

        try:
            with get_session() as session:
                if key == "basicos":
                    # nivel_nombre carries tipo_pieza filter for básicos
                    tp_filter = nivel_nombre if nivel_nombre else None
                    sheets = build_conteo_sheets_basicos(session, tipo_pieza=tp_filter)
                else:
                    eid, nid = self._parse_key(key)
                    sheets = build_conteo_sheets(
                        session, eid, escuela_nombre, nivel_id=nid,
                        nivel_nombre=nivel_nombre or None,
                        escuela_num=escuela_num or None,
                    )
            if not sheets:
                return json.dumps({"ok": False, "error": "No hay productos para imprimir."})

            from pos_uniformes.ui.dialogs.conteo_print_dialog import open_conteo_print_dialog

            parent = self.parent()
            while parent is not None and not hasattr(parent, "windowTitle"):
                parent = parent.parent()

            titulo = "Hojas de conteo — Productos Básicos" if key == "basicos" else f"Hojas de conteo — {escuela_nombre}"
            open_conteo_print_dialog(parent, titulo, sheets)
            return json.dumps({"ok": True})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(str, result=str)
    def imprimirPedido(self, data_json: str) -> str:
        from pos_uniformes.services.pedido_sheet_service import build_pedido_sheets

        try:
            items = json.loads(data_json)
            sheets = build_pedido_sheets(items)
            if not sheets:
                return json.dumps({"ok": False, "error": "No hay items para imprimir."})

            from pos_uniformes.ui.dialogs.conteo_print_dialog import open_conteo_print_dialog

            parent = self.parent()
            while parent is not None and not hasattr(parent, "windowTitle"):
                parent = parent.parent()

            open_conteo_print_dialog(parent, "Pedido de mercancía", sheets)
            return json.dumps({"ok": True})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(str, result=str)
    def copiarPedido(self, data_json: str) -> str:
        from PyQt6.QtWidgets import QApplication

        from pos_uniformes.services.pedido_sheet_service import build_pedido_texto

        try:
            items = json.loads(data_json)
            texto = build_pedido_texto(items)
            if not texto:
                return json.dumps({"ok": False, "error": "No hay items."})
            clipboard = QApplication.clipboard()
            clipboard.setText(texto)
            return json.dumps({"ok": True})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class PanelUniformesWidget(QWidget):
    """Widget principal: toolbar + QWebEngineView."""

    def __init__(self, window: MainWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._worker: _PanelGeneratorWorker | None = None
        self._loaded = False

        base = Path(__file__).resolve().parent.parent.parent
        self._script_path = base / "scripts" / "generar_panel_uniformes.py"
        self._html_path = base / "panel_uniformes.html"

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(12, 8, 12, 8)

        _btn_style = (
            "QPushButton { color: #333; background: #fff; border: 1px solid #ccc;"
            " border-radius: 4px; padding: 4px 10px; font-size: 13px; }"
            "QPushButton:hover { background: #e8e8e8; }"
            "QPushButton:pressed { background: #ddd; }"
        )

        self._regen_btn = QPushButton("🔄 Regenerar")
        self._regen_btn.setFixedWidth(130)
        self._regen_btn.setStyleSheet(_btn_style)
        self._regen_btn.clicked.connect(self._regenerar)
        toolbar.addWidget(self._regen_btn)

        self._open_browser_btn = QPushButton("🌐 Abrir en navegador")
        self._open_browser_btn.setFixedWidth(170)
        self._open_browser_btn.setStyleSheet(_btn_style)
        self._open_browser_btn.clicked.connect(self._open_in_browser)
        toolbar.addWidget(self._open_browser_btn)

        toolbar.addStretch()

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #888; font-size: 12px;")
        toolbar.addWidget(self._status_label)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar)
        toolbar_widget.setStyleSheet("background: #f5f5f5; border-bottom: 1px solid #ddd;")
        layout.addWidget(toolbar_widget)

        # El QWebEngineView NO se crea aquí: instanciarlo arranca el proceso
        # de Chromium (cientos de ms + ~100MB) en el arranque aunque nadie
        # abra el panel. Se crea perezoso en showEvent.
        self._web_view = None
        self._web_view_attempted = False

    def _ensure_web_view(self) -> None:
        """Crea el QWebEngineView + bridge la primera vez que se necesita."""
        if self._web_view_attempted:
            return
        self._web_view_attempted = True
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtWebChannel import QWebChannel

            self._web_view = QWebEngineView()
            self.layout().addWidget(self._web_view, 1)

            # Setup QWebChannel bridge
            channel = QWebChannel(self._web_view.page())
            self._bridge = PanelBridge(self, window=self._window)
            channel.registerObject("bridge", self._bridge)
            self._web_view.page().setWebChannel(channel)

        except Exception as exc:
            self._web_view = None
            fallback = QLabel(f"PyQt6-WebEngine no disponible:\n{exc}")
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback.setStyleSheet("font-size: 16px; color: #999; padding: 40px;")
            self.layout().addWidget(fallback, 1)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self._ensure_web_view()
        if not self._loaded and self._web_view is not None:
            self._loaded = True
            # If HTML exists and is recent (< 5 min), load directly; else regenerate
            if self._html_path.exists():
                age = datetime.now().timestamp() - self._html_path.stat().st_mtime
                if age < 300:
                    self._load_html()
                    return
            self._regenerar()

    def _regenerar(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return  # ya está generando

        self._regen_btn.setEnabled(False)
        self._status_label.setText("Generando panel...")

        if self._web_view is not None:
            self._web_view.setHtml(
                "<html><body style='display:flex;justify-content:center;align-items:center;"
                "height:100vh;font-family:sans-serif;color:#888'>"
                "<div><h2>Generando panel de uniformes...</h2>"
                "<p>Esto toma unos segundos.</p></div></body></html>"
            )

        self._worker = _PanelGeneratorWorker(self._script_path, self)
        self._worker.finished.connect(self._on_generation_done)
        self._worker.start()

    def _on_generation_done(self, success: bool, message: str) -> None:
        self._regen_btn.setEnabled(True)
        if success:
            now_str = datetime.now().strftime("%H:%M:%S")
            self._status_label.setText(f"Actualizado a las {now_str}")
            self._load_html()
        else:
            self._status_label.setText("Error al generar")
            if self._web_view is not None:
                self._web_view.setHtml(
                    f"<html><body style='padding:40px;font-family:sans-serif'>"
                    f"<h2 style='color:#c62828'>Error al generar panel</h2>"
                    f"<pre>{message}</pre></body></html>"
                )

    def _load_html(self) -> None:
        if self._web_view is None:
            return
        url = QUrl.fromLocalFile(str(self._html_path))
        self._web_view.setUrl(url)

    def _open_in_browser(self) -> None:
        import webbrowser

        if self._html_path.exists():
            webbrowser.open(self._html_path.as_uri())


# ---------------------------------------------------------------------------
# Public builder (pattern used by all views)
# ---------------------------------------------------------------------------

def build_panel_uniformes_tab(window: MainWindow) -> QWidget:
    return PanelUniformesWidget(window)
