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

    @pyqtSlot(int, result=str)
    def getVariantesParaConteo(self, escuela_id: int) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import obtener_variantes_para_conteo

        try:
            with get_session() as session:
                variantes = obtener_variantes_para_conteo(session, escuela_id)
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

    @pyqtSlot(int, result=str)
    def getVariantesAgrupadas(self, escuela_id: int) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import obtener_variantes_agrupadas_por_producto

        try:
            with get_session() as session:
                grupos = obtener_variantes_agrupadas_por_producto(session, escuela_id)
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
            with get_session() as session:
                ajustados, omitidos = confirmar_ajustes_lote(
                    session, conteo_ids, "ADMIN"
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

    @pyqtSlot(int, result=str)
    def getConteosPendientes(self, escuela_id: int) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import obtener_conteos_pendientes

        try:
            eid = escuela_id if escuela_id > 0 else None
            with get_session() as session:
                conteos = obtener_conteos_pendientes(session, eid)
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

    @pyqtSlot(int, result=str)
    def getEstadoConteo(self, escuela_id: int) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import obtener_estado_conteo_escuela

        try:
            with get_session() as session:
                e = obtener_estado_conteo_escuela(session, escuela_id)
                return json.dumps({
                    "ok": True,
                    "escuela_nombre": e.escuela_nombre,
                    "dias_vigencia": e.dias_vigencia,
                    "total_variantes": e.total_variantes,
                    "contadas_vigentes": e.contadas_vigentes,
                    "pendientes_conteo": e.pendientes_conteo,
                    "pct_vigente": e.pct_vigente,
                    "ultimo_conteo": e.ultimo_conteo.isoformat() if e.ultimo_conteo else None,
                })
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(int, result=str)
    def getConfigConteo(self, escuela_id: int) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.database.models import ConfigConteoEscuela
        from pos_uniformes.services.conteo_service import DIAS_VIGENCIA_DEFAULT

        try:
            from sqlalchemy import select

            with get_session() as session:
                config = session.scalar(
                    select(ConfigConteoEscuela).where(
                        ConfigConteoEscuela.escuela_id == escuela_id
                    )
                )
                dias = config.dias_vigencia if config else DIAS_VIGENCIA_DEFAULT
                return json.dumps({"ok": True, "dias_vigencia": dias})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"ok": False, "error": str(exc)})

    @pyqtSlot(int, int, result=str)
    def setConfigConteo(self, escuela_id: int, dias_vigencia: int) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_service import guardar_config_conteo

        try:
            with get_session() as session:
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

    @pyqtSlot(int, str, result=str)
    def imprimirHojasConteo(self, escuela_id: int, escuela_nombre: str) -> str:
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.conteo_sheet_service import build_conteo_sheets

        try:
            with get_session() as session:
                sheets = build_conteo_sheets(
                    session, escuela_id, escuela_nombre,
                )
            if not sheets:
                return json.dumps({"ok": False, "error": "No hay productos para esta escuela."})

            from pos_uniformes.ui.dialogs.conteo_print_dialog import open_conteo_print_dialog

            parent = self.parent()
            while parent is not None and not hasattr(parent, "windowTitle"):
                parent = parent.parent()

            open_conteo_print_dialog(
                parent,
                f"Hojas de conteo — {escuela_nombre}",
                sheets,
            )
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

        # WebEngineView (lazy import to avoid crash if not installed)
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtWebChannel import QWebChannel

            self._web_view = QWebEngineView()
            layout.addWidget(self._web_view, 1)

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
            layout.addWidget(fallback, 1)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
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
