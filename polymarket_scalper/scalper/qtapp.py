"""Aplicación de escritorio en PyQt6.

Junta lo mejor de las dos vías: una ventana nativa para manejar el bot y, dentro de ella, el
panel HTML que ya existe, sin necesidad de abrir el navegador. Si falta el componente web, la
aplicación sigue funcionando y ofrece abrir el panel en el navegador.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QProcess, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPlainTextEdit,
                             QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

# El componente web debe importarse antes de crear la QApplication, o Qt falla al inicializarlo.
# SCALPER_SIN_WEB=1 lo desactiva: útil en máquinas virtuales o escritorios remotos donde
# Chromium no arranca por falta de aceleración gráfica.
if os.environ.get("SCALPER_SIN_WEB") == "1":
    QWebEngineView = None  # type: ignore[assignment]
    HAY_WEB = False
else:
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView

        HAY_WEB = True
    except ImportError:
        QWebEngineView = None  # type: ignore[assignment]
        HAY_WEB = False

PANEL_URL = "http://127.0.0.1:8787"

C = {
    "fondo": "#0f141a", "barra": "#141b23", "panel": "#1a222c", "panel2": "#202a35",
    "borde": "#2a3542", "borde2": "#37455a", "texto": "#e8edf3", "texto2": "#aab6c4", "suave": "#7c8a9a",
    "acento": "#3987e5", "acento2": "#5a9cea", "ok": "#0ca30c", "ok2": "#14b814",
    "aviso": "#fab219", "error": "#d03b3b", "error2": "#e04a4a", "log": "#0b1016",
}

QSS = f"""
QMainWindow, QWidget {{ background: {C['fondo']}; color: {C['texto']};
    font-family: "Segoe UI", "Inter", -apple-system, sans-serif; font-size: 13px; }}

#barraLateral {{ background: {C['barra']}; border-right: 1px solid {C['borde']}; }}
QLabel {{ background: transparent; }}
#titulo {{ font-size: 15px; font-weight: 600; color: {C['texto']}; }}
#subtitulo {{ font-size: 10px; color: {C['suave']}; letter-spacing: 1px; }}

QPushButton#nav {{ background: transparent; color: {C['texto2']}; border: none; border-radius: 6px;
    padding: 9px 12px; text-align: left; font-size: 13px; }}
QPushButton#nav:hover {{ background: {C['panel']}; color: {C['texto']}; }}
QPushButton#nav:checked {{ background: {C['panel']}; color: {C['texto']}; border-left: 3px solid {C['acento']}; }}

QPushButton#primario {{ background: {C['ok']}; color: white; border: none; border-radius: 6px;
    padding: 11px 14px; font-size: 13px; font-weight: 600; }}
QPushButton#primario:hover {{ background: {C['ok2']}; }}
QPushButton#detener {{ background: {C['error']}; color: white; border: none; border-radius: 6px;
    padding: 11px 14px; font-size: 13px; font-weight: 600; }}
QPushButton#detener:hover {{ background: {C['error2']}; }}
QPushButton#secundario {{ background: {C['panel']}; color: {C['texto']}; border: 1px solid {C['borde2']};
    border-radius: 6px; padding: 9px 12px; font-size: 12px; }}
QPushButton#secundario:hover {{ border-color: {C['acento']}; background: {C['panel2']}; }}
QPushButton:disabled {{ background: {C['panel']}; color: {C['suave']}; border-color: {C['borde']}; }}

#tarjeta {{ background: {C['panel']}; border: 1px solid {C['borde']}; border-radius: 8px; }}
#tarjetaEtiqueta {{ color: {C['suave']}; font-size: 11px; letter-spacing: 0.4px; }}
#tarjetaValor {{ color: {C['texto']}; font-size: 20px; font-weight: 600;
    font-family: "Consolas", "SF Mono", monospace; }}
#tarjetaNota {{ color: {C['texto2']}; font-size: 11px; }}

#encabezado {{ font-size: 17px; font-weight: 600; }}
#ayuda {{ color: {C['texto2']}; font-size: 12px; }}

QPlainTextEdit {{ background: {C['log']}; color: {C['texto2']}; border: 1px solid {C['borde']};
    border-radius: 8px; font-family: "Consolas", "SF Mono", monospace; font-size: 11px;
    padding: 10px; selection-background-color: {C['acento']}; }}
QScrollBar:vertical {{ background: {C['log']}; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {C['borde2']}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {C['suave']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: {C['log']}; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {C['borde2']}; border-radius: 5px; min-width: 24px; }}
"""


_ESPERANDO = f"""
<!doctype html><meta charset="utf-8">
<style>
  html,body {{ margin:0; height:100%; background:{C['fondo']}; color:{C['texto2']};
    font-family:"Segoe UI",system-ui,sans-serif; display:grid; place-items:center; }}
  .caja {{ text-align:center; max-width:460px; padding:32px; }}
  .titulo {{ color:{C['texto']}; font-size:17px; font-weight:600; margin-bottom:10px; }}
  p {{ font-size:13px; line-height:1.6; margin:0 0 8px; }}
  .nota {{ color:{C['suave']}; font-size:12px; margin-top:18px; }}
  .barra {{ width:180px; height:3px; background:{C['borde']}; border-radius:2px; margin:22px auto 0;
    overflow:hidden; position:relative; }}
  .barra i {{ position:absolute; inset:0; width:60px; background:{C['acento']}; border-radius:2px;
    animation:v 1.4s ease-in-out infinite; }}
  @keyframes v {{ 0% {{ left:-60px }} 100% {{ left:180px }} }}
  @media (prefers-reduced-motion: reduce) {{ .barra i {{ animation:none; left:60px }} }}
</style>
<div class="caja">
  <div class="titulo">El panel aparecerá aquí</div>
  <p>Pulsa <b>Iniciar bot</b> en la barra de la izquierda.</p>
  <p>Al arrancar, el bot empieza a recolectar el mercado y el panel se carga solo en unos segundos.</p>
  <div class="barra"><i></i></div>
  <div class="nota">Todo es simulado: no se firman órdenes ni se usa una wallet.</div>
</div>
"""


def _punto(color: str, tam: int = 10) -> QPixmap:
    pm = QPixmap(tam, tam)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, tam, tam)
    p.end()
    return pm


class Tarjeta(QFrame):
    """Una cifra con su etiqueta y una nota corta debajo."""

    def __init__(self, etiqueta: str, nota: str = ""):
        super().__init__()
        self.setObjectName("tarjeta")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 11, 14, 11)
        v.setSpacing(3)
        e = QLabel(etiqueta)
        e.setObjectName("tarjetaEtiqueta")
        self.valor = QLabel("–")
        self.valor.setObjectName("tarjetaValor")
        self.nota = QLabel(nota)
        self.nota.setObjectName("tarjetaNota")
        for w in (e, self.valor, self.nota):
            v.addWidget(w)

    def poner(self, valor: str, nota: str | None = None, color: str | None = None) -> None:
        self.valor.setText(valor)
        if nota is not None:
            self.nota.setText(nota)
        if color:
            self.valor.setStyleSheet(f"color: {color};")


class Ventana(QMainWindow):
    linea_log = pyqtSignal(str, str)

    def __init__(self, proyecto: Path, config: str = "config.yaml"):
        super().__init__()
        self.proyecto = proyecto
        self.config = config
        self.data_dir = proyecto / "data"
        self.bot: QProcess | None = None
        self.panel: QProcess | None = None
        self.setWindowTitle("Scalper Polymarket")
        self.resize(1280, 820)
        self.setMinimumSize(QSize(1000, 640))
        self.setStyleSheet(QSS)
        self._construir()
        self.linea_log.connect(self._agregar_log)
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._refrescar)
        self._reloj.start(4000)
        self._refrescar()

    # ---------------------------------------------------------------- interfaz
    def _construir(self) -> None:
        central = QWidget()
        raiz = QHBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._lateral())
        raiz.addWidget(self._contenido(), 1)
        self.setCentralWidget(central)

    def _lateral(self) -> QWidget:
        lat = QWidget()
        lat.setObjectName("barraLateral")
        lat.setFixedWidth(232)
        v = QVBoxLayout(lat)
        v.setContentsMargins(14, 18, 14, 16)
        v.setSpacing(6)

        cab = QVBoxLayout()
        cab.setSpacing(1)
        t = QLabel("Scalper Polymarket")
        t.setObjectName("titulo")
        st = QLabel("PANEL DE OPERACIÓN")
        st.setObjectName("subtitulo")
        cab.addWidget(t)
        cab.addWidget(st)
        v.addLayout(cab)
        v.addSpacing(14)

        fila = QHBoxLayout()
        fila.setSpacing(7)
        self.punto = QLabel()
        self.punto.setPixmap(_punto(C["error"]))
        self.estado = QLabel("detenido")
        self.estado.setStyleSheet(f"color: {C['texto2']}; font-size: 12px;")
        fila.addWidget(self.punto)
        fila.addWidget(self.estado)
        fila.addStretch(1)
        v.addLayout(fila)
        v.addSpacing(16)

        self.navs: list[QPushButton] = []
        for i, texto in enumerate(("Oportunidades", "Panel en vivo", "Actividad del bot", "Informes")):
            b = QPushButton(texto)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=i: self._ir(n))
            v.addWidget(b)
            self.navs.append(b)
        self.navs[0].setChecked(True)

        v.addStretch(1)
        self.b_bot = QPushButton("Iniciar bot")
        self.b_bot.setObjectName("primario")
        self.b_bot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_bot.clicked.connect(self._alternar_bot)
        v.addWidget(self.b_bot)

        self.b_informes = QPushButton("Generar informes")
        self.b_informes.setObjectName("secundario")
        self.b_informes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_informes.clicked.connect(self._generar_informes)
        v.addWidget(self.b_informes)

        b_carpeta = QPushButton("Carpeta de datos")
        b_carpeta.setObjectName("secundario")
        b_carpeta.setCursor(Qt.CursorShape.PointingHandCursor)
        b_carpeta.clicked.connect(self._abrir_carpeta)
        v.addWidget(b_carpeta)

        aviso = QLabel("Paper trading: simula con datos reales,\nsin dinero y sin wallet.")
        aviso.setWordWrap(True)
        aviso.setStyleSheet(f"color: {C['suave']}; font-size: 10px;")
        v.addSpacing(10)
        v.addWidget(aviso)
        return lat

    def _contenido(self) -> QWidget:
        cont = QWidget()
        v = QVBoxLayout(cont)
        v.setContentsMargins(18, 18, 18, 18)
        v.setSpacing(14)

        tarjetas = QHBoxLayout()
        tarjetas.setSpacing(10)
        self.tarjetas = {
            "mercados": Tarjeta("Mercados seguidos", "NBA, tenis y cripto"),
            "senales": Tarjeta("Señales detectadas", "oportunidades vistas"),
            "btc": Tarjeta("Bitcoin", "precio de referencia"),
            "ventanas": Tarjeta("Ventanas de cripto", "activas ahora"),
            "datos": Tarjeta("Último dato", "del libro de órdenes"),
        }
        for t in self.tarjetas.values():
            tarjetas.addWidget(t)
        v.addLayout(tarjetas)

        self.pilas = QStackedWidget()
        self.pilas.addWidget(self._pagina_oportunidades())
        self.pilas.addWidget(self._pagina_panel())
        self.pilas.addWidget(self._pagina_log())
        self.pilas.addWidget(self._pagina_informes())
        v.addWidget(self.pilas, 1)
        return cont

    def _titulo_pagina(self, layout: QVBoxLayout, titulo: str, ayuda: str) -> None:
        t = QLabel(titulo)
        t.setObjectName("encabezado")
        a = QLabel(ayuda)
        a.setObjectName("ayuda")
        a.setWordWrap(True)
        layout.addWidget(t)
        layout.addWidget(a)

    def _pagina_oportunidades(self) -> QWidget:
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self._titulo_pagina(v, "Oportunidades ahora mismo",
                            "Qué comprar, a qué precio y por qué, separado por mercado. Las cifras ya descuentan "
                            "las comisiones. Si no aparece nada es que ninguna supera el costo de operar.")
        self.ops = QPlainTextEdit()
        self.ops.setReadOnly(True)
        self.ops.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.ops.setPlainText("Pulsa «Iniciar bot» para que empiece a buscar.")
        v.addWidget(self.ops, 1)
        fila = QHBoxLayout()
        b = QPushButton("Actualizar ahora")
        b.setObjectName("secundario")
        b.clicked.connect(self._refrescar_oportunidades)
        fila.addWidget(b)
        nota = QLabel("Se actualiza solo cada 15 segundos mientras el bot corre.")
        nota.setObjectName("ayuda")
        fila.addWidget(nota)
        fila.addStretch(1)
        v.addLayout(fila)
        self._reloj_ops = QTimer(self)
        self._reloj_ops.timeout.connect(self._refrescar_oportunidades)
        self._reloj_ops.start(15000)
        return p

    def _refrescar_oportunidades(self) -> None:
        """Lee las señales recientes y las traduce a lenguaje llano. Es rápido: solo mira Parquet."""
        try:
            from .opportunities import formatear, listar

            texto = formatear(listar(self.data_dir, minutos=30))
        except Exception as e:  # noqa: BLE001
            texto = f"No se pudieron leer las oportunidades: {e}"
        barra = self.ops.verticalScrollBar()
        pos = barra.value()
        self.ops.setPlainText(texto)
        barra.setValue(min(pos, barra.maximum()))

    def _pagina_panel(self) -> QWidget:
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self._titulo_pagina(v, "Panel en vivo", "Resumen, resultados por señal, partidos y wallets. "
                                                "Se actualiza solo cada 10 segundos mientras el bot corre.")
        self.web: Any = None
        if HAY_WEB:
            self.web = QWebEngineView()
            self.web.setHtml(_ESPERANDO)
            v.addWidget(self.web, 1)
            self._panel_listo = False
            self._vigia = QTimer(self)
            self._vigia.timeout.connect(self._revisar_panel)
            self._vigia.start(2000)
            barra = QHBoxLayout()
            b = QPushButton("Recargar")
            b.setObjectName("secundario")
            b.clicked.connect(self._cargar_panel)
            b2 = QPushButton("Abrir en el navegador")
            b2.setObjectName("secundario")
            b2.clicked.connect(lambda: webbrowser.open(PANEL_URL))
            barra.addWidget(b)
            barra.addWidget(b2)
            barra.addStretch(1)
            v.addLayout(barra)
        else:
            aviso = QLabel("El panel no puede mostrarse dentro de esta ventana.\n\n"
                           "Falta el componente web de Qt, o tu equipo no puede ejecutarlo (suele pasar en "
                           "máquinas virtuales y escritorios remotos).\n\n"
                           "Se instala con:  pip install PyQt6-WebEngine\n\n"
                           "En cualquier caso el panel funciona igual en el navegador, con el mismo contenido.")
            aviso.setObjectName("ayuda")
            aviso.setWordWrap(True)
            v.addWidget(aviso)
            b = QPushButton("Abrir el panel en el navegador")
            b.setObjectName("secundario")
            b.clicked.connect(lambda: webbrowser.open(PANEL_URL))
            v.addWidget(b)
            v.addStretch(1)
        return p

    def _pagina_log(self) -> QWidget:
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self._titulo_pagina(v, "Actividad del bot", "Lo que está haciendo ahora mismo. "
                                                    "Los avisos salen en ámbar y los errores en rojo.")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(4000)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log.appendHtml(
            f"<span style='color:{C['suave']}'>El bot está detenido.<br><br>"
            f"Pulsa «Iniciar bot» para empezar a recolectar el mercado y simular operaciones.<br>"
            f"Aquí verás su actividad línea por línea.</span>")
        v.addWidget(self.log, 1)
        return p

    def _pagina_informes(self) -> QWidget:
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self._titulo_pagina(v, "Informes", "Datos guardados, el estudio del arrastre entre ventanas de cripto, "
                                           "resultados por tipo de señal, wallets, modelos aprendidos y disco.")
        self.informes = QPlainTextEdit()
        self.informes.setReadOnly(True)
        self.informes.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.informes.appendHtml(f"<span style='color:{C['suave']}'>Pulsa «Generar informes» para verlos.</span>")
        v.addWidget(self.informes, 1)
        return p

    def _cargar_panel(self) -> None:
        if self.web is not None:
            self.web.setUrl(QUrl(PANEL_URL))

    def _revisar_panel(self) -> None:
        """Carga el panel en cuanto responde; hasta entonces deja la página de espera."""
        if self.web is None:
            return
        import socket

        try:
            with socket.create_connection(("127.0.0.1", 8787), timeout=0.3):
                pass
        except OSError:
            if self._panel_listo:                      # se cayó: volver a la página de espera
                self._panel_listo = False
                self.web.setHtml(_ESPERANDO)
            return
        if not self._panel_listo:
            self._panel_listo = True
            self._cargar_panel()

    def _ir(self, n: int) -> None:
        self.pilas.setCurrentIndex(n)
        for i, b in enumerate(self.navs):
            b.setChecked(i == n)

    # ---------------------------------------------------------------- procesos
    def _lanzar(self, args: list[str], al_recibir: Any) -> QProcess:
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        p.setWorkingDirectory(str(self.proyecto))
        entorno = p.processEnvironment()
        from PyQt6.QtCore import QProcessEnvironment

        entorno = QProcessEnvironment.systemEnvironment()
        entorno.insert("PYTHONUTF8", "1")
        entorno.insert("PYTHONUNBUFFERED", "1")
        p.setProcessEnvironment(entorno)
        p.readyReadStandardOutput.connect(al_recibir)
        p.start(sys.executable, ["-m", "scalper.cli", *args])
        return p

    def _alternar_bot(self) -> None:
        if self.bot is not None and self.bot.state() != QProcess.ProcessState.NotRunning:
            self._detener(self.bot, "bot")
            self.bot = None
        else:
            self.log.clear()
            self._ir(2)
            self.bot = self._lanzar(["-c", self.config, "--log-file", "logs/bot.log", "paper"], self._leer_bot)
            self.bot.finished.connect(lambda *_: self._refrescar())
            QTimer.singleShot(2500, self._asegurar_panel)
        self._refrescar()

    def _asegurar_panel(self) -> None:
        """El panel web se levanta solo junto al bot: es lo que alimenta la primera pestaña."""
        if self.panel is None or self.panel.state() == QProcess.ProcessState.NotRunning:
            self.panel = self._lanzar(["-c", self.config, "--log-file", "logs/panel.log", "dashboard"], self._leer_panel)
            if self.web is not None:
                QTimer.singleShot(2500, lambda: self.web.setUrl(QUrl(PANEL_URL)))

    def _detener(self, p: QProcess, nombre: str) -> None:
        """Cierre limpio: la misma interrupción que Ctrl+C, para que el bot guarde los datos."""
        self.linea_log.emit(f"— deteniendo {nombre}, guardando datos… —", "ok")
        pid = int(p.processId())
        try:
            if sys.platform == "win32":
                p.terminate()
            else:
                os.kill(pid, signal.SIGINT)
        except Exception:  # noqa: BLE001
            p.terminate()
        if not p.waitForFinished(25000):
            self.linea_log.emit(f"— {nombre} no respondió a tiempo; cierre forzado —", "aviso")
            p.kill()
            p.waitForFinished(3000)

    def _leer_bot(self) -> None:
        self._volcar(self.bot, "")

    def _leer_panel(self) -> None:
        self._volcar(self.panel, "[panel] ")

    def _volcar(self, p: QProcess | None, prefijo: str) -> None:
        if p is None:
            return
        datos = bytes(p.readAllStandardOutput()).decode("utf-8", errors="replace")
        for linea in datos.splitlines():
            if linea.strip():
                self.linea_log.emit(prefijo + linea, self._color(linea))
                self._extraer(linea)

    @staticmethod
    def _color(linea: str) -> str:
        b = linea.lower()
        if "error" in b or "falló" in b or "traceback" in b:
            return "error"
        if "warning" in b or "desconect" in b or "aviso" in b:
            return "aviso"
        if "conectado" in b or "cierre " in b or linea.startswith("—"):
            return "ok"
        return "normal"

    def _agregar_log(self, linea: str, clase: str) -> None:
        # Ojo: los nombres de los métodos conectados a una señal deben ser ASCII.
        # PyQt6 falla al resolver el slot si el nombre lleva acentos o eñes.
        color = {"error": C["error"], "aviso": C["aviso"], "ok": C["ok2"], "normal": C["texto2"]}[clase]
        escapada = linea.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.log.appendHtml(f"<span style='color:{color}'>{escapada}</span>")

    def _extraer(self, linea: str) -> None:
        t = self.tarjetas
        try:
            if "mercados activos=" in linea:
                t["mercados"].poner(linea.split("mercados activos=")[1].split()[0])
            elif "discovery:" in linea:
                t["mercados"].poner(linea.split("discovery:")[1].split()[0])
            if "btc=" in linea:
                t["btc"].poner("$" + linea.split("btc=")[1].split()[0])
            if "updown=" in linea:
                v = linea.split("updown=")[1].split()[0]
                s = linea.split("strikes=")[1].split()[0] if "strikes=" in linea else "0"
                t["ventanas"].poner(v, f"{s} con precio de apertura")
            if "'signals':" in linea:
                t["senales"].poner(linea.split("'signals':")[1].split(",")[0].strip())
        except (IndexError, ValueError):
            pass

    # ---------------------------------------------------------------- acciones
    def _generar_informes(self) -> None:
        self._ir(3)
        self.informes.clear()
        self.informes.appendHtml(f"<span style='color:{C['suave']}'>Generando informes…</span>")
        self.b_informes.setEnabled(False)
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setWorkingDirectory(str(self.proyecto))

        def terminado() -> None:
            texto = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
            self.informes.clear()
            self.informes.setPlainText(texto or "No se pudo generar el informe.")
            self.b_informes.setEnabled(True)

        proc.finished.connect(lambda *_: terminado())
        proc.start(sys.executable, ["-m", "scalper.cli", "-c", self.config, "overview"])

    def _abrir_carpeta(self) -> None:
        d = self.data_dir if self.data_dir.exists() else self.proyecto
        if sys.platform == "win32":
            os.startfile(str(d))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(d)])
        else:
            subprocess.Popen(["xdg-open", str(d)])

    # ---------------------------------------------------------------- estado
    def _corriendo(self) -> bool:
        return self.bot is not None and self.bot.state() != QProcess.ProcessState.NotRunning

    def _refrescar(self) -> None:
        corriendo = self._corriendo()
        self.b_bot.setText("Detener bot" if corriendo else "Iniciar bot")
        self.b_bot.setObjectName("detener" if corriendo else "primario")
        self.b_bot.setStyleSheet("")           # fuerza a releer el QSS con el nuevo objectName
        self.punto.setPixmap(_punto(C["ok"] if corriendo else C["error"]))
        self.estado.setText("funcionando" if corriendo else "detenido")
        if corriendo:
            self._refrescar_oportunidades()
        t = _dato_mas_reciente(self.data_dir)
        if t is None:
            self.tarjetas["datos"].poner("sin datos", "aún no hay nada guardado", C["error"])
        else:
            import time as _t

            seg = int(_t.time() - t)
            color = C["ok"] if seg < 120 else C["aviso"] if seg < 900 else C["error"]
            self.tarjetas["datos"].poner(f"{seg} s" if seg < 120 else f"{seg // 60} min",
                                         "al día" if seg < 120 else "el bot no está escribiendo", color)

    def closeEvent(self, ev: Any) -> None:  # noqa: N802
        if self._corriendo():
            r = QMessageBox.question(self, "Cerrar", "El bot está funcionando.\n\n"
                                                     "Se detendrá guardando los datos pendientes. ¿Cerrar?")
            if r != QMessageBox.StandardButton.Yes:
                ev.ignore()
                return
        for p, n in ((self.panel, "panel"), (self.bot, "bot")):
            if p is not None and p.state() != QProcess.ProcessState.NotRunning:
                self._detener(p, n)
        ev.accept()


def _dato_mas_reciente(data_dir: Path) -> float | None:
    mejor = None
    for tabla in ("book_deltas", "quotes", "crypto_prices"):
        d = data_dir / tabla
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.parquet"), key=lambda x: x.stat().st_mtime, reverse=True)[:1]:
            mejor = p.stat().st_mtime if mejor is None else max(mejor, p.stat().st_mtime)
    return mejor


def disponible() -> bool:
    try:
        import PyQt6.QtWidgets  # noqa: F401
    except ImportError:
        return False
    return True


def lanzar(proyecto: Path, config: str = "config.yaml", cerrar_tras_ms: int | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Scalper Polymarket")
    app.setFont(QFont("Segoe UI" if sys.platform == "win32" else "Helvetica", 10))
    v = Ventana(proyecto, config)
    v.show()
    if cerrar_tras_ms is not None:
        QTimer.singleShot(cerrar_tras_ms, app.quit)
    return app.exec()
