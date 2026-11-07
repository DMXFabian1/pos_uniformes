"""La pestaña Analítica del POS, rehecha sobre la Libreta (2026-11-07).

Daniel: «mejoremos la pestaña de analítica» → «hazlo completo». Arriba el
periodo como en la Libreta (◀ ▶ con Hoy / Semana / Mes / 30 días / Manual),
cuatro tarjetas con su comparación contra el periodo anterior, el cobrado por
día en barras, lo que se va a acabar, los cortes por escuela, prenda, talla,
hora, empleada y producto con una barrita de proporción, la demanda no
atendida y la afluencia.

Ctrl+Shift+R asoma lo real (sin los ajustes del dueño en sus cortes), como en
la Libreta y en Cortes.

Los cálculos viven en `services/analitica_tablero_service.py`; aquí solo se
arma y se pinta.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from PyQt6.QtCore import QDate, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QKeySequence, QPainter, QShortcut
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services import analitica_tablero_service as tb

logger = logging.getLogger(__name__)

VINO = "#6b1f3a"
TERRACOTA = "#a84f2d"
CREMA = "#f5ebe0"
TEXTO = "#2c2a27"
SUAVE = "#8a8177"
VERDE = "#1c7c54"
ROJO = "#b3261e"

ESTILO = f"""
QWidget#analiticaRaiz {{ background: transparent; }}
QLabel#anaTitulo {{ font-size: 22px; font-weight: 800; color: {TEXTO}; background: transparent; }}
QLabel#anaSub {{ font-size: 13px; color: {SUAVE}; background: transparent; }}
QPushButton#anaPeriodo {{ background: #ffffff; color: {TEXTO}; border: 1px solid #ddd0c0; border-radius: 14px;
                          padding: 6px 14px; font-weight: 700; }}
QPushButton#anaPeriodo:checked {{ background: {VINO}; color: #ffffff; border-color: {VINO}; }}
QPushButton#anaFlecha {{ background: #ffffff; color: {VINO}; border: 1px solid #ddd0c0; border-radius: 10px;
                         min-width: 34px; padding: 6px 0; font-weight: 800; }}
QLabel#anaFecha {{ font-size: 16px; font-weight: 800; color: {TEXTO}; background: transparent; padding: 0 8px; }}
QFrame#anaCard {{ background: #fffdf9; border: 1px solid #e6dccb; border-radius: 14px; }}
QFrame#anaCard[acento="true"] {{ background: {VINO}; border: none; }}
QLabel#anaCardTitulo {{ font-size: 11px; font-weight: 800; letter-spacing: 1px; color: {SUAVE}; background: transparent; }}
QLabel#anaCardValor {{ font-size: 28px; font-weight: 800; color: {TEXTO}; background: transparent; }}
QLabel#anaCardPie {{ font-size: 12px; color: {SUAVE}; background: transparent; }}
QFrame#anaCard[acento="true"] QLabel#anaCardTitulo {{ color: #e9cfd6; }}
QFrame#anaCard[acento="true"] QLabel#anaCardValor {{ color: #ffffff; }}
QFrame#anaCard[acento="true"] QLabel#anaCardPie {{ color: #f3dde3; }}
QLabel#anaCambio {{ font-size: 13px; font-weight: 800; background: transparent; }}
QLabel#anaCambio[tono="sube"] {{ color: {VERDE}; }}
QLabel#anaCambio[tono="baja"] {{ color: {ROJO}; }}
QLabel#anaCambio[tono="igual"], QLabel#anaCambio[tono="nuevo"] {{ color: {SUAVE}; }}
QFrame#anaCard[acento="true"] QLabel#anaCambio {{ color: #ffffff; }}
QFrame#anaSeccion {{ background: #fffdf9; border: 1px solid #e6dccb; border-radius: 14px; }}
QLabel#anaSeccionTitulo {{ font-size: 12px; font-weight: 800; letter-spacing: 1px; color: {VINO}; background: transparent; }}
QLabel#anaNota {{ font-size: 12px; color: {SUAVE}; background: transparent; }}
"""


# ─── Piezas chicas ──────────────────────────────────────────────────────────

class _Tarjeta(QFrame):
    def __init__(self, titulo: str, *, acento: bool = False) -> None:
        super().__init__()
        self.setObjectName("anaCard")
        self.setProperty("acento", "true" if acento else "false")
        ly = QVBoxLayout(self)
        ly.setContentsMargins(16, 12, 16, 12)
        ly.setSpacing(2)
        t = QLabel(titulo.upper())
        t.setObjectName("anaCardTitulo")
        self.valor = QLabel("—")
        self.valor.setObjectName("anaCardValor")
        self.cambio = QLabel("")
        self.cambio.setObjectName("anaCambio")
        self.pie = QLabel("")
        self.pie.setObjectName("anaCardPie")
        self.pie.setWordWrap(True)
        ly.addWidget(t)
        ly.addWidget(self.valor)
        ly.addWidget(self.cambio)
        ly.addWidget(self.pie)

    def poner(self, valor: str, cambio: tuple[str, str], comparado: str, pie: str = "") -> None:
        self.valor.setText(valor)
        texto, tono = cambio
        if texto == "—":
            self.cambio.setText("")          # ni ahora ni antes: no hay nada que comparar
        elif tono == "nuevo":
            self.cambio.setText(f"nuevo vs {comparado}")
        else:
            self.cambio.setText(f"{texto} vs {comparado}")
        self.cambio.setProperty("tono", tono)
        self.cambio.style().unpolish(self.cambio)
        self.cambio.style().polish(self.cambio)
        self.pie.setText(pie)
        self.pie.setVisible(bool(pie))


class Barras(QWidget):
    """Barras verticales sencillas: una por día (u hora), con su etiqueta abajo."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(170)
        self.datos: list[tuple[str, float, str]] = []   # (etiqueta, valor, texto del valor)

    def poner(self, datos: list[tuple[str, float, str]]) -> None:
        self.datos = list(datos)
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802 — nombre de Qt
        if not self.datos:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ancho, alto = self.width(), self.height()
        abajo, arriba = 22, 18
        tope = max((v for _e2, v, _t in self.datos), default=0) or 1
        n = len(self.datos)
        paso = ancho / n
        barra = max(4.0, min(42.0, paso * 0.62))
        f = QFont(self.font())
        f.setPointSize(8 if n > 16 else 9)
        p.setFont(f)
        mas_alto = max(range(n), key=lambda i: self.datos[i][1])
        for i, (etiqueta, valor, texto) in enumerate(self.datos):
            x = i * paso + (paso - barra) / 2
            h = (alto - abajo - arriba) * (valor / tope)
            color = QColor(VINO if i == mas_alto and valor > 0 else TERRACOTA)
            if valor < 0:
                h = 0          # un día que no ha llegado: solo su etiqueta
            elif valor == 0:
                color = QColor("#e6dccb")
                h = 2
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            if h > 0:
                p.drawRoundedRect(QRectF(x, alto - abajo - h, barra, h), 3, 3)
            p.setPen(QColor(SUAVE))
            # Con muchos días, solo algunas etiquetas para que no se encimen.
            cada = 1 if n <= 16 else (2 if n <= 31 else 4)
            if i % cada == 0 or i == n - 1:
                p.drawText(QRectF(i * paso, alto - abajo + 4, paso * cada, 16),
                           int(Qt.AlignmentFlag.AlignLeft), etiqueta)
            if i == mas_alto and valor > 0:
                p.setPen(QColor(VINO))
                p.drawText(QRectF(x - 40, alto - abajo - h - 16, barra + 80, 14),
                           int(Qt.AlignmentFlag.AlignHCenter), texto)
        p.end()


class _BarraEnCelda(QStyledItemDelegate):
    """La columna de piezas con una barrita de proporción detrás del número."""

    def paint(self, painter, option, index) -> None:
        proporcion = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(proporcion, float) and proporcion > 0:
            r = option.rect.adjusted(2, 6, -2, -6)
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(168, 79, 45, 55))
            painter.drawRoundedRect(QRectF(r.x(), r.y(), r.width() * proporcion, r.height()), 3, 3)
            painter.restore()
        super().paint(painter, option, index)


def _seccion(titulo: str, nota: str = "") -> tuple[QFrame, QVBoxLayout]:
    caja = QFrame()
    caja.setObjectName("anaSeccion")
    ly = QVBoxLayout(caja)
    ly.setContentsMargins(16, 12, 16, 14)
    ly.setSpacing(8)
    t = QLabel(titulo.upper())
    t.setObjectName("anaSeccionTitulo")
    ly.addWidget(t)
    if nota:
        n = QLabel(nota)
        n.setObjectName("anaNota")
        n.setWordWrap(True)
        ly.addWidget(n)
    return caja, ly


def _pesos(valor) -> str:
    return f"${Decimal(valor):,.2f}"


def _pesos_cortos(valor) -> str:
    v = Decimal(valor)
    return f"${v / 1000:,.1f}k" if v >= 10000 else f"${v:,.0f}"


# ─── Armado ─────────────────────────────────────────────────────────────────

def construir(window) -> QWidget:
    """Arma la pestaña y cuelga de `window` lo que el refresco necesita."""
    from pos_uniformes.ui.helpers.analytics_demanda_helper import construir as construir_demanda
    from pos_uniformes.ui.helpers.analytics_libreta_helper import construir as construir_cortes

    raiz = QWidget()
    raiz.setObjectName("analiticaRaiz")
    raiz.setStyleSheet(ESTILO)
    ly = QVBoxLayout(raiz)
    ly.setSpacing(12)

    estado = {"clave": tb.SEMANA, "ancla": date.today(), "real": False}
    window._ana_estado = estado

    # Cabecera: título, periodo y fecha con flechas.
    cab = QHBoxLayout()
    textos = QVBoxLayout()
    textos.setSpacing(0)
    titulo = QLabel("Analítica")
    titulo.setObjectName("anaTitulo")
    window.ana_sub = QLabel("Lo que se vendió en el kiosko, desde la Libreta.")
    window.ana_sub.setObjectName("anaSub")
    textos.addWidget(titulo)
    textos.addWidget(window.ana_sub)
    cab.addLayout(textos, 1)
    grupo = QButtonGroup(raiz)
    grupo.setExclusive(True)
    window.ana_periodos = {}
    for clave, texto in ((tb.HOY, "Hoy"), (tb.SEMANA, "Semana"), (tb.MES, "Mes"), (tb.TREINTA, "30 días"), (tb.MANUAL, "Manual")):
        b = QPushButton(texto)
        b.setObjectName("anaPeriodo")
        b.setCheckable(True)
        b.setChecked(clave == estado["clave"])
        b.clicked.connect(lambda _c=False, k=clave: _elegir_periodo(window, k))
        grupo.addButton(b)
        window.ana_periodos[clave] = b
        cab.addWidget(b)
    ly.addLayout(cab)

    fila_fecha = QHBoxLayout()
    window.ana_prev = QPushButton("◀")
    window.ana_prev.setObjectName("anaFlecha")
    window.ana_prev.clicked.connect(lambda: _mover(window, -1))
    window.ana_fecha = QLabel("")
    window.ana_fecha.setObjectName("anaFecha")
    window.ana_next = QPushButton("▶")
    window.ana_next.setObjectName("anaFlecha")
    window.ana_next.clicked.connect(lambda: _mover(window, 1))
    window.ana_desde = QDateEdit()
    window.ana_hasta = QDateEdit()
    for editor in (window.ana_desde, window.ana_hasta):
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("dd/MM/yyyy")
        editor.setDate(QDate.currentDate())
        editor.dateChanged.connect(lambda _d: _refrescar_con_sesion(window))
        editor.setVisible(False)
    window.ana_exportar = QPushButton("⬇  Exportar CSV")
    window.ana_exportar.setObjectName("anaPeriodo")
    window.ana_exportar.clicked.connect(lambda: exportar_csv(window))
    fila_fecha.addWidget(window.ana_prev)
    fila_fecha.addWidget(window.ana_fecha)
    fila_fecha.addWidget(window.ana_next)
    fila_fecha.addWidget(window.ana_desde)
    fila_fecha.addWidget(window.ana_hasta)
    fila_fecha.addStretch(1)
    fila_fecha.addWidget(window.ana_exportar)
    ly.addLayout(fila_fecha)

    # Las cuatro tarjetas.
    tarjetas = QHBoxLayout()
    tarjetas.setSpacing(10)
    window.ana_cobrado = _Tarjeta("Cobrado", acento=True)
    window.ana_operaciones = _Tarjeta("Operaciones")
    window.ana_ticket = _Tarjeta("Ticket promedio")
    window.ana_piezas = _Tarjeta("Piezas")
    for t in (window.ana_cobrado, window.ana_operaciones, window.ana_ticket, window.ana_piezas):
        tarjetas.addWidget(t, 1)
    ly.addLayout(tarjetas)

    # Cobrado por día + se va a acabar, lado a lado.
    medio = QHBoxLayout()
    medio.setSpacing(12)
    caja, cly = _seccion("Cobrado por día", "La barra más alta va en vino.")
    window.ana_barras_titulo = caja.findChild(QLabel, "anaSeccionTitulo")
    window.ana_barras = Barras()
    cly.addWidget(window.ana_barras, 1)
    window.ana_afluencia = QLabel("")
    window.ana_afluencia.setObjectName("anaNota")
    window.ana_afluencia.setVisible(False)
    cly.addWidget(window.ana_afluencia)
    medio.addWidget(caja, 3)
    caja, cly = _seccion(
        "Se va a acabar",
        f"Lo que se vendió en los últimos {tb.DIAS_DE_RITMO} días y, a ese ritmo, no alcanza "
        f"{tb.SEMANAS_DE_ALERTA:.0f} semanas. Primero lo que ya no hay.",
    )
    window.ana_acabarse = QTableWidget(0, 5)
    window.ana_acabarse.setHorizontalHeaderLabels(["Prenda", "Talla", "Vendidas", "Hay", "Alcanza"])
    window.ana_acabarse.setObjectName("dataTable")
    window.ana_acabarse.verticalHeader().setVisible(False)
    window.ana_acabarse.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    window.ana_acabarse.setAlternatingRowColors(True)
    window.ana_acabarse.setMinimumHeight(200)
    enc = window.ana_acabarse.horizontalHeader()
    enc.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    for col in range(1, 5):
        enc.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    cly.addWidget(window.ana_acabarse)
    window.ana_acabarse_vacio = QLabel("Nada en riesgo: todo lo que se vende alcanza.")
    window.ana_acabarse_vacio.setObjectName("anaNota")
    cly.addWidget(window.ana_acabarse_vacio)
    medio.addWidget(caja, 2)
    ly.addLayout(medio)

    # Los cortes de siempre (escuela, prenda, talla, hora, empleada, producto).
    cortes = construir_cortes(window)
    cortes.setTitle("Qué se vendió")
    window.libreta_analytics_resumen_label.setVisible(False)   # lo dicen las tarjetas
    window.libreta_analytics_pago_label.setVisible(False)
    from pos_uniformes.ui.helpers.analytics_libreta_helper import TABLAS

    delegado = _BarraEnCelda(raiz)
    for atributo, _t, _c in TABLAS:
        getattr(window, atributo).setItemDelegateForColumn(1, delegado)
    ly.addWidget(cortes)

    ly.addWidget(construir_demanda(window))

    # Ctrl+Shift+R: lo real, como en la Libreta y en Cortes.
    QShortcut(QKeySequence("Ctrl+Shift+R"), raiz, activated=lambda: _alternar_real(window))
    return raiz


# ─── Acciones ───────────────────────────────────────────────────────────────

def _elegir_periodo(window, clave: str) -> None:
    window._ana_estado["clave"] = clave
    window._ana_estado["ancla"] = date.today()
    _refrescar_con_sesion(window)


def _mover(window, pasos: int) -> None:
    e = window._ana_estado
    nueva = tb.mover(e["clave"], e["ancla"], pasos)
    if nueva > date.today():
        return
    e["ancla"] = nueva
    _refrescar_con_sesion(window)


def _alternar_real(window) -> None:
    window._ana_estado["real"] = not window._ana_estado["real"]
    _refrescar_con_sesion(window)


def _refrescar_con_sesion(window) -> None:
    try:
        from pos_uniformes.database.connection import get_session

        with get_session() as session:
            refrescar(window, session)
    except Exception:  # noqa: BLE001 — sin base, la pestaña se queda como estaba
        logger.exception("Analítica: no se pudo refrescar")


# ─── Pintar ─────────────────────────────────────────────────────────────────

def refrescar(window, session) -> None:
    """Lee el periodo elegido y pinta todo. Nunca rompe la pestaña."""
    from pos_uniformes.ui.helpers.analytics_demanda_helper import cargar_y_pintar as cargar_demanda
    from pos_uniformes.ui.helpers.analytics_libreta_helper import pintar as pintar_cortes

    e = window._ana_estado
    manual = (window.ana_desde.date().toPyDate(), window.ana_hasta.date().toPyDate())
    try:
        t = tb.cargar(session, e["clave"], e["ancla"], manual=manual, real=e["real"])
    except Exception:  # noqa: BLE001
        logger.exception("Analítica: no se pudo leer la Libreta")
        session.rollback()
        return
    pintar(window, t)
    pintar_cortes(window, list(t.filas))
    _barritas(window)
    ini, fin = tb.limites(t.desde, t.hasta)
    cargar_demanda(window, session, ini, fin)
    # Sin señales, las dos tablas vacías solo ocupan media pantalla: se dice
    # en un renglón y se esconden.
    vacias = all(getattr(window, a).rowCount() == 0 for a in ("demanda_pedir_table", "demanda_buscado_table"))
    for a in ("demanda_pedir_table", "demanda_buscado_table"):
        getattr(window, a).parentWidget().setVisible(not vacias)


def pintar(window, t: "tb.Tablero") -> None:
    e = window._ana_estado
    for clave, b in window.ana_periodos.items():
        b.setChecked(clave == t.clave)
    manual = t.clave == tb.MANUAL
    window.ana_desde.setVisible(manual)
    window.ana_hasta.setVisible(manual)
    window.ana_prev.setVisible(not manual)
    window.ana_next.setVisible(not manual)
    window.ana_next.setEnabled(tb.mover(t.clave, e["ancla"], 1) <= date.today())
    window.ana_fecha.setText(tb.texto_periodo(t.clave, t.desde, t.hasta))
    window.ana_sub.setText(
        "Lo que se vendió en el kiosko, desde la Libreta."
        + ("   ·   CON LO REAL (Ctrl+Shift+R para volver)" if t.real else "")
    )

    if t.hasta_la_hora:
        comparado = "ayer a esta hora"
    else:
        comparado = tb.nombre_comparacion(t.clave) + (" (mismos días)" if t.a_medias else "")
    a, b = t.ahora, t.antes
    window.ana_cobrado.poner(
        _pesos(a.cobrado), tb.cambio(a.cobrado, b.cobrado), comparado,
        f"efectivo {_pesos(a.efectivo)} + tarjeta {_pesos(a.tarjeta_neto)}",
    )
    window.ana_operaciones.poner(str(a.operaciones), tb.cambio(a.operaciones, b.operaciones), comparado,
                                 f"{a.ventas} venta{'s' if a.ventas != 1 else ''}")
    window.ana_ticket.poner(_pesos(a.ticket_promedio), tb.cambio(a.ticket_promedio, b.ticket_promedio), comparado,
                            "por venta")
    window.ana_piezas.poner(str(a.piezas), tb.cambio(a.piezas, b.piezas), comparado, "ventas y apartados")

    # Barras: por día; si es un solo día, por hora (piezas).
    if t.dias:
        window.ana_barras_titulo.setText("COBRADO POR DÍA")
        dias = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
        etiqueta = (lambda d: f"{dias[d.weekday()]} {d.day}") if len(t.dias) <= 7 else (lambda d: str(d.day))
        hoy = t.hoy or date.today()
        # Los días que no han llegado van sin barra (valor −1), no en cero.
        window.ana_barras.poner([
            (etiqueta(d.dia), float(d.cobrado) if d.dia <= hoy else -1.0, _pesos_cortos(d.cobrado))
            for d in t.dias
        ])
    else:
        window.ana_barras_titulo.setText("PIEZAS POR HORA")
        por_hora: dict[int, int] = {}
        for f in t.filas:
            por_hora[f.hora] = por_hora.get(f.hora, 0) + int(f.cantidad)
        horas = range(9, 20)
        window.ana_barras.poner([(f"{h}", float(por_hora.get(h, 0)), f"{por_hora.get(h, 0)} pzas") for h in horas])

    afl = t.afluencia
    if afl is not None and getattr(afl, "entradas", 0):
        conv = f" · conversión {afl.conversion:.0f} %" if afl.conversion is not None else ""
        window.ana_afluencia.setText(f"👣 Entraron {afl.entradas} personas{conv}")
        window.ana_afluencia.setVisible(True)
    else:
        window.ana_afluencia.setVisible(False)

    tabla = window.ana_acabarse
    tabla.setRowCount(len(t.acabarse))
    for fila, p in enumerate(t.acabarse):
        nombre = p.nombre + (f" · {p.escuela}" if p.escuela and p.escuela not in p.nombre else "")
        valores = (nombre, p.talla, str(p.vendidas), str(p.existencia), p.texto_semanas)
        for col, texto in enumerate(valores):
            item = QTableWidgetItem(texto)
            if col == 4:
                item.setForeground(QColor(ROJO if p.existencia <= 0 or (p.semanas or 0) < 1 else "#a35a00"))
                fuente = item.font()
                fuente.setBold(True)
                item.setFont(fuente)
            if col in (2, 3):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            tabla.setItem(fila, col, item)
    window.ana_acabarse_vacio.setVisible(not t.acabarse)
    tabla.setVisible(bool(t.acabarse))


def _barritas(window) -> None:
    """Guarda en cada celda de piezas su proporción contra la mayor de la tabla."""
    from pos_uniformes.ui.helpers.analytics_libreta_helper import TABLAS

    for atributo, _t, _c in TABLAS:
        tabla = getattr(window, atributo)
        valores = []
        for fila in range(tabla.rowCount()):
            item = tabla.item(fila, 1)
            try:
                valores.append(int(item.text()) if item else 0)
            except ValueError:
                valores.append(0)
        tope = max(valores, default=0) or 1
        for fila, v in enumerate(valores):
            item = tabla.item(fila, 1)
            if item is not None:
                item.setData(Qt.ItemDataRole.UserRole, v / tope)


def exportar_csv(window) -> str | None:
    """Las líneas vendidas del periodo, a CSV en exports/analytics/. Devuelve la ruta."""
    import csv
    from datetime import datetime
    from pathlib import Path

    from PyQt6.QtWidgets import QMessageBox

    from pos_uniformes.database.connection import get_session
    from pos_uniformes.services.analitica_libreta_service import filas_de_periodo

    e = window._ana_estado
    manual = (window.ana_desde.date().toPyDate(), window.ana_hasta.date().toPyDate())
    desde, hasta = tb.rango(e["clave"], e["ancla"], manual)
    ini, fin = tb.limites(desde, hasta)
    try:
        with get_session() as session:
            filas = filas_de_periodo(session, ini, fin)
    except Exception as exc:  # noqa: BLE001
        QMessageBox.warning(window, "Exportar", f"No se pudo leer la Libreta:\n{exc}")
        return None
    carpeta = Path(__file__).resolve().parents[2] / "exports" / "analytics"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"ventas_{desde:%Y%m%d}_{hasta:%Y%m%d}_{datetime.now():%H%M%S}.csv"
    with ruta.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["fecha", "hora", "tipo", "sku", "producto", "talla", "escuela", "prenda",
                    "cantidad", "precio", "importe", "empleada", "tarjeta"])
        for f in filas:
            w.writerow([f.momento.date().isoformat(), f.momento.strftime("%H:%M"), f.tipo, f.sku, f.nombre,
                        f.talla, f.escuela, f.tipo_pieza, f.cantidad, f.precio, f.importe,
                        f.employee_name or f.employee_code, "sí" if f.tarjeta else "no"])
    QMessageBox.information(window, "Exportado", f"{len(filas)} renglones en:\n{ruta}")
    return str(ruta)
