"""💼 Mi pago: la cuenta del pago del dueño (VEND-1), en el kiosko (2026-11-19).

Libreta del dueño → menú «💼 Caja ▾» → «💼 Mi pago». Solo VEND-1.

- Los pagos del mes (7, 14, 21 y 28) con su estado: pagado (fecha y monto),
  toca hoy, pendiente o atrasado, y el desglose de cada uno.
- «Ya me pagaron» (fecha y monto editables; el calculado por omisión) y
  «Deshacer pago».
- Los días de más con su destino, para cambiarlo.
- La configuración: monto, valor del día, fechas de pago e inicio.

Es solo la cuenta: nada de esto sale del cajón ni toca el corte. La lógica
vive en `services/pago_dueno_service.py`; aquí solo se pinta y se pregunta.

También vive aquí `despues_de_marcar_dueno`, lo que el calendario del dueño
llama tras marcar un día suyo: si quedó un día de más, pregunta «¿Te lo
pagamos o te lo guardamos?».
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services import pago_dueno_service as pd

logger = logging.getLogger(__name__)

_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")

_ESTILO = """
QDialog#miPago { background: #f4ede2; }
QDialog#miPago QLabel { color: #2c2a27; background: transparent; }
QDialog#miPago QScrollArea { background: transparent; border: none; }
QDialog#miPago QScrollArea > QWidget > QWidget { background: transparent; }
QFrame#miPagoCard { background: #fbf7f0; border: 1px solid #e6dccb; border-radius: 12px; }
QDialog#miPago QLabel#miPagoSeccion { color: #7b2d14; font-size: 12px; font-weight: 800; letter-spacing: 1px; }
QDialog#miPago QLabel#miPagoResumen { font-size: 15px; font-weight: 700; }
QDialog#miPago QLabel#miPagoNota { color: #8a8177; font-size: 12px; }
QDialog#miPago QLabel#miPagoTitulo { font-size: 16px; font-weight: 800; }
QDialog#miPago QLabel#miPagoMonto { font-size: 18px; font-weight: 800; }
QDialog#miPago QLabel#miPagoDesglose { color: #5f564c; font-size: 13px; }
QDialog#miPago QLabel#miPagoEstado { border-radius: 9px; padding: 3px 10px; font-size: 12px; font-weight: 800; }
QDialog#miPago QLabel#miPagoEstado[estado="pagado"] { background: #d9ecd0; color: #3d6b2f; }
QDialog#miPago QLabel#miPagoEstado[estado="toca_hoy"] { background: #f7e3d8; color: #a84f2d; }
QDialog#miPago QLabel#miPagoEstado[estado="pendiente"] { background: #ece6dc; color: #5f564c; }
QDialog#miPago QLabel#miPagoEstado[estado="atrasado"] { background: #f6d3cb; color: #a33b25; }
QDialog#miPago QPushButton { background: #ffffff; color: #2c2a27; border: 1.5px solid #ddd0c0; border-radius: 10px;
                             min-height: 38px; padding: 0 12px; font-size: 13px; font-weight: 700; }
QDialog#miPago QPushButton:disabled { color: #b5aa9c; background: #f4eee4; border-color: #e6dccd; }
QDialog#miPago QPushButton#miPagoPrimario { background: #3d6b2f; color: #ffffff; border: none; }
QDialog#miPago QPushButton#miPagoPrimario:disabled { background: #c9d6c2; color: #f4f7f2; }
QDialog#miPago QDoubleSpinBox, QDialog#miPago QDateEdit, QDialog#miPago QLineEdit {
    background: #ffffff; color: #2c2a27; border: 1px solid #d9cdb8; border-radius: 8px; padding: 4px 8px; min-height: 30px; }
"""

ESTADOS_TEXTO = {
    pd.PAGADO: "Pagado",
    pd.TOCA_HOY: "Toca hoy",
    pd.PENDIENTE: "Pendiente",
    pd.ATRASADO: "Atrasado",
}

DESTINO_TEXTO = {
    pd.PAGAR: "Se paga en su pago",
    pd.ACUMULAR: "Guardado como día a favor",
}


# ─── Textos (puros, probados) ────────────────────────────────────────────


def _dias(n: int) -> str:
    return f"{n} día" if n == 1 else f"{n} días"


def _fechas(fechas: list[date]) -> str:
    return ", ".join(pd.fecha_corta(f) for f in fechas)


TEXTO_SIN_DESCANSO = (
    "⚠ Tu descanso fijo no está guardado en el calendario, así que no se cuentan "
    "días de más. Guárdalo (martes) en tu horario del calendario."
)


def titulo_pago(p: pd.DesglosePago) -> str:
    """'3 de 4 · sáb 21-nov'."""
    return f"{p.etiqueta} · {pd.fecha_corta(p.fecha_programada, con_dia=True)}"


def texto_estado(p: pd.DesglosePago, hoy: date) -> str:
    """'Pagado el 19-nov · $2,500', 'Toca hoy', 'Pendiente' o 'Atrasado'."""
    estado = p.estado(hoy)
    if estado == pd.PAGADO and p.registro is not None:
        return f"Pagado el {pd.fecha_corta(p.registro.fecha_pago)} · {pd.dinero_texto(p.registro.monto)}"
    return ESTADOS_TEXTO[estado]


def lineas_desglose(p: pd.DesglosePago) -> list[str]:
    """El desglose de un pago, en palabras de la tienda."""
    lineas = [
        f"Cubre del {pd.fecha_corta(p.desde)} al {pd.fecha_corta(p.hasta)}",
        f"Base: {pd.dinero_texto(p.base)}",
    ]
    if p.dias_extra_pagados:
        lineas.append(
            f"+ {_dias(len(p.dias_extra_pagados))} de más: {pd.dinero_texto(p.monto_extra)}"
            f" ({_fechas(p.dias_extra_pagados)})"
        )
    if p.faltas_descontadas:
        lineas.append(
            f"− {len(p.faltas_descontadas)} falta(s): {pd.dinero_texto(p.descuento_faltas)}"
            f" ({_fechas(p.faltas_descontadas)})"
        )
    if p.faltas_cubiertas:
        lineas.append(
            f"Falta(s) cubierta(s) con días a favor: {_fechas(p.faltas_cubiertas)} (no se descuentan)"
        )
    guardados = [f for f in p.dias_extra_acumulados if f not in p.dias_extra_sin_decidir]
    if guardados:
        lineas.append(f"Días de más guardados: {_fechas(guardados)}")
    if p.dias_extra_sin_decidir:
        lineas.append(f"Días de más sin decidir (se guardan): {_fechas(p.dias_extra_sin_decidir)}")
    pagado = monto_de_la_tarjeta(p)
    if pagado != p.monto:
        # Lo que de verdad se pagó no es lo calculado (monto editado, o algo
        # cambió después de registrarlo): se ven las dos cifras.
        lineas.append(f"Calculado: {pd.dinero_texto(p.monto)}")
        lineas.append(f"Pagado: {pd.dinero_texto(pagado)}")
    else:
        lineas.append(f"Total: {pd.dinero_texto(p.monto)}")
    return lineas


def monto_de_la_tarjeta(p: pd.DesglosePago) -> Decimal:
    """La cifra grande: lo que de verdad se pagó si ya está registrado; si no,
    lo calculado."""
    if p.pagado and p.registro is not None:
        return p.registro.monto
    return p.monto


def texto_resumen(rec: pd.Recordatorio | None) -> str:
    """El renglón de arriba: próximo pago, último pago y días a favor."""
    if rec is None:
        return "La cuenta de tu pago todavía no está configurada."
    p = rec.proximo
    ultimo = pd.fecha_corta(rec.ultimo_pago) if rec.ultimo_pago else "ninguno"
    partes = [
        f"Próximo: {titulo_pago(p)} · {pd.dinero_texto(p.monto)} ({pd.cuando_toca(rec.dias_faltan).lower()})",
        f"Último pago: {ultimo} · Días a favor: {rec.dias_a_favor}",
    ]
    if rec.atrasados:
        partes.append("Atrasados: " + ", ".join(
            f"{a.etiqueta} ({pd.fecha_corta(a.fecha_programada)})" for a in rec.atrasados
        ))
    return "\n".join(partes)


def texto_dia_extra(e: pd.DiaExtra) -> str:
    destino = "Sin decidir (se guarda)" if e.sin_decidir else DESTINO_TEXTO[e.destino]
    return f"{pd.fecha_corta(e.fecha, con_dia=True)} · {destino}"


def leer_dias_de_pago(texto: str) -> tuple[int, ...]:
    """'7, 14, 21, 28' → (7, 14, 21, 28). ValueError si algo no es un día válido."""
    partes = [t for t in texto.replace(";", ",").replace(" ", ",").split(",") if t.strip()]
    try:
        dias = [int(t) for t in partes]
    except ValueError as exc:
        raise ValueError("Las fechas de pago son números del 1 al 28, separados por comas.") from exc
    return pd.dias_de_pago_validos(dias)


def _mes_siguiente(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def _qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _de_qdate(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


def _sesion():
    from pos_uniformes.database.connection import get_session

    return get_session()


# ─── Pregunta del calendario ─────────────────────────────────────────────


def preguntar_destino(parent: QWidget | None, fecha: date, valor_dia: Decimal, actual: str | None) -> str | None:
    """«¿Te lo pagamos o te lo guardamos?» → 'pagar' / 'acumular' / None (luego)."""
    caja = QMessageBox(parent)
    caja.setIcon(QMessageBox.Icon.Question)
    caja.setWindowTitle("Día de más")
    caja.setText(
        f"Trabajaste el {pd.fecha_corta(fecha, con_dia=True)} en tu descanso.\n\n"
        "¿Te lo pagamos o te lo guardamos?\n\n"
        f"Págamelo: suma {pd.dinero_texto(valor_dia)} a tu pago de esa semana.\n"
        "Guárdamelo: queda como un día a favor para cubrir una falta."
    )
    pagar = caja.addButton("💵 Págamelo", QMessageBox.ButtonRole.AcceptRole)
    guardar = caja.addButton("📦 Guárdamelo", QMessageBox.ButtonRole.AcceptRole)
    luego = caja.addButton("Luego", QMessageBox.ButtonRole.RejectRole)
    caja.setDefaultButton(pagar if actual == pd.PAGAR else guardar)
    caja.setEscapeButton(luego)
    caja.exec()
    elegido = caja.clickedButton()
    if elegido is pagar:
        return pd.PAGAR
    if elegido is guardar:
        return pd.ACUMULAR
    return None


def despues_de_marcar_dueno(
    parent: QWidget | None, fecha: date, tipo: str, *, session_factory=None, preguntar=None,
) -> str | None:
    """Lo que hace el calendario del dueño tras marcar o quitar un día SUYO.

    1. Borra las decisiones que quedaron sin día de más (se quitó la marca o
       se movió el descanso): así no revive un «págamelo» viejo.
    2. Si marcó «Sí trabajó» y el día es de más, pregunta y guarda.

    Devuelve el destino guardado, o None. Nunca rompe el calendario."""
    from pos_uniformes.services.calendario_empleadas_service import TRABAJO

    sf = session_factory or _sesion
    try:
        with sf() as session:
            pd.limpiar_decisiones_huerfanas(session)
            if tipo != TRABAJO or not pd.es_dia_extra(session, fecha):
                return None
            actual = pd.decision_dia_extra(session, fecha)
            config = pd.cargar_config(session)
            valor_dia = config.valor_dia if config is not None else pd.VALOR_DIA_DEFAULT
    except Exception:  # noqa: BLE001 — la marca ya quedó; la cuenta es aparte
        logger.exception("Mi pago: no se pudo revisar el día de más")
        return None
    destino = (preguntar or preguntar_destino)(parent, fecha, valor_dia, actual)
    if destino is None:
        return None
    try:
        with sf() as session:
            pd.decidir_dia_extra(session, fecha, destino)
    except Exception:  # noqa: BLE001
        logger.exception("Mi pago: no se guardó el destino del día de más")
        QMessageBox.warning(parent, "No se guardó", "No se guardó si se paga o se guarda. Cámbialo en 💼 Mi pago.")
        return None
    return destino


# ─── El diálogo ──────────────────────────────────────────────────────────


class _YaMePagaronDialog(QDialog):
    """Fecha real y monto (el calculado por omisión)."""

    def __init__(self, parent: QWidget | None, p: pd.DesglosePago, hoy: date):
        super().__init__(parent)
        self.setWindowTitle("Ya me pagaron")
        ly = QVBoxLayout(self)
        titulo = QLabel(f"Pago {titulo_pago(p)}")
        titulo.setStyleSheet("font-size: 16px; font-weight: 800;")
        ly.addWidget(titulo)
        form = QFormLayout()
        self.fecha = QDateEdit(_qdate(hoy))
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        self.fecha.setMaximumDate(_qdate(hoy))      # no se apunta un pago que no ha pasado
        form.addRow("¿Qué día te pagaron?", self.fecha)
        self.monto = QDoubleSpinBox()
        self.monto.setRange(0, 1_000_000)
        self.monto.setDecimals(2)
        self.monto.setPrefix("$ ")
        self.monto.setValue(float(p.monto))
        form.addRow("¿Cuánto?", self.monto)
        ly.addLayout(form)
        nota = QLabel(f"Lo calculado es {pd.dinero_texto(p.monto)}. Es solo la cuenta: no sale del cajón.")
        nota.setWordWrap(True)
        nota.setStyleSheet("color: #8a8177; font-size: 12px;")
        ly.addWidget(nota)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        ly.addWidget(botones)

    def valores(self) -> tuple[date, Decimal]:
        return _de_qdate(self.fecha.date()), Decimal(str(self.monto.value())).quantize(Decimal("0.01"))


class MiPagoDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, quien: str = pd.EMPLOYEE_CODE,
                 session_factory=None, hoy: date | None = None):
        super().__init__(parent)
        self.setObjectName("miPago")
        self.setWindowTitle("💼 Mi pago")
        self.setStyleSheet(_ESTILO)
        self.resize(760, 760)
        self._quien = str(quien or "").strip().upper()
        self._sf = session_factory or _sesion
        self._hoy = hoy or date.today()
        self._year, self._month = self._hoy.year, self._hoy.month
        self._config: pd.ConfigPagoDueno | None = None
        self.pagos: list[pd.DesglosePago] = []
        self.extras: list[pd.DiaExtra] = []
        self._config_pintada = False   # la configuración guardada ya está en los campos

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        cuerpo = QWidget()
        self._ly = QVBoxLayout(cuerpo)
        self._ly.setContentsMargins(20, 16, 20, 10)
        self._ly.setSpacing(10)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(cuerpo)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        raiz.addWidget(area, 1)

        aviso = QLabel("Es solo la cuenta de tu pago: no sale del cajón ni cambia el corte.")
        aviso.setObjectName("miPagoNota")
        aviso.setWordWrap(True)
        self._ly.addWidget(aviso)
        self.resumen = QLabel("")
        self.resumen.setObjectName("miPagoResumen")
        self.resumen.setWordWrap(True)
        self._ly.addWidget(self.resumen)
        self.aviso_descanso = QLabel(TEXTO_SIN_DESCANSO)
        self.aviso_descanso.setObjectName("miPagoNota")
        self.aviso_descanso.setWordWrap(True)
        self.aviso_descanso.setVisible(False)
        self._ly.addWidget(self.aviso_descanso)

        # Pagos del mes, con flechas.
        nav = QHBoxLayout()
        self.btn_mes_prev = QPushButton("◀")
        self.btn_mes_next = QPushButton("▶")
        for b in (self.btn_mes_prev, self.btn_mes_next):
            b.setFixedWidth(48)
            b.setAutoDefault(False)
        self.btn_mes_prev.clicked.connect(lambda: self._mover_mes(-1))
        self.btn_mes_next.clicked.connect(lambda: self._mover_mes(1))
        self.mes_label = QLabel("")
        self.mes_label.setObjectName("miPagoSeccion")
        self.mes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self.btn_mes_prev)
        nav.addWidget(self.mes_label, 1)
        nav.addWidget(self.btn_mes_next)
        self._ly.addLayout(nav)
        self._pagos_box = QVBoxLayout()
        self._pagos_box.setSpacing(8)
        self._ly.addLayout(self._pagos_box)

        # Días de más.
        seccion = QLabel("DÍAS DE MÁS")
        seccion.setObjectName("miPagoSeccion")
        self._ly.addWidget(seccion)
        self._extras_box = QVBoxLayout()
        self._extras_box.setSpacing(6)
        self._ly.addLayout(self._extras_box)

        # Configuración.
        self._ly.addWidget(self._seccion_config())
        self._ly.addStretch(1)

        pie = QHBoxLayout()
        pie.setContentsMargins(20, 6, 20, 14)
        self.status = QLabel("")
        self.status.setObjectName("miPagoNota")
        self.status.setWordWrap(True)
        pie.addWidget(self.status, 1)
        cerrar = QPushButton("Cerrar")
        cerrar.setAutoDefault(False)
        cerrar.clicked.connect(self.accept)
        pie.addWidget(cerrar)
        raiz.addLayout(pie)
        self.recargar(pintar_config=True)

    # ── armado ──
    def _seccion_config(self) -> QFrame:
        card = QFrame()
        card.setObjectName("miPagoCard")
        ly = QVBoxLayout(card)
        ly.setContentsMargins(14, 10, 14, 12)
        t = QLabel("CONFIGURACIÓN")
        t.setObjectName("miPagoSeccion")
        ly.addWidget(t)
        form = QFormLayout()
        self.cfg_monto = QDoubleSpinBox()
        self.cfg_monto.setRange(0, 1_000_000)
        self.cfg_monto.setPrefix("$ ")
        self.cfg_monto.setValue(float(pd.MONTO_DEFAULT))
        form.addRow("Monto de cada pago:", self.cfg_monto)
        self.cfg_valor_dia = QDoubleSpinBox()
        self.cfg_valor_dia.setRange(0, 100_000)
        self.cfg_valor_dia.setPrefix("$ ")
        self.cfg_valor_dia.setValue(float(pd.VALOR_DIA_DEFAULT))
        form.addRow("Valor de un día:", self.cfg_valor_dia)
        self.cfg_dias = QLineEdit(", ".join(str(d) for d in pd.DIAS_DE_PAGO_DEFAULT))
        self.cfg_dias.setPlaceholderText("7, 14, 21, 28")
        form.addRow("Días de pago (1 al 28):", self.cfg_dias)
        self.cfg_inicio = QDateEdit(_qdate(self._hoy))
        self.cfg_inicio.setCalendarPopup(True)
        self.cfg_inicio.setDisplayFormat("dd/MM/yyyy")
        form.addRow("La cuenta empieza el:", self.cfg_inicio)
        self.cfg_activo = QCheckBox("Llevar la cuenta (y recordarla en el corte)")
        self.cfg_activo.setChecked(True)
        form.addRow("", self.cfg_activo)
        ly.addLayout(form)
        self.btn_guardar_config = QPushButton("Guardar configuración")
        self.btn_guardar_config.setObjectName("miPagoPrimario")
        self.btn_guardar_config.setAutoDefault(False)
        self.btn_guardar_config.clicked.connect(self._guardar_config)
        ly.addWidget(self.btn_guardar_config)
        return card

    @staticmethod
    def _limpiar(box: QVBoxLayout) -> None:
        while box.count():
            item = box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def recargar(self, *, pintar_config: bool = False) -> None:
        """Vuelve a leer y pinta. La configuración solo se repinta al abrir y
        al guardarla (`pintar_config`), para no borrar lo que se está editando."""
        rec = None
        sin_descanso = False
        try:
            with self._sf() as session:
                pd.limpiar_decisiones_huerfanas(session)
                self._config = pd.cargar_config(session)
                vigente = self._config is not None and self._config.vigente
                self.pagos = pd.pagos_del_mes_db(session, self._year, self._month) if vigente else []
                self.extras = pd.lista_dias_extra(session, max(self._hoy, self._fin_de_mes())) if vigente else []
                rec = pd.recordatorio(session, self._hoy) if vigente else None
                sin_descanso = pd.falta_descanso(session) if vigente else False
        except Exception:  # noqa: BLE001
            logger.exception("Mi pago: no se pudo cargar")
            self.status.setText("Sin conexión con la PC principal.")
            self.pagos, self.extras = [], []
        self.resumen.setText(texto_resumen(rec))
        self.aviso_descanso.setVisible(sin_descanso)
        if pintar_config or not self._config_pintada:
            self._pintar_config()
        self._pintar_pagos()
        self._pintar_extras()

    def _fin_de_mes(self) -> date:
        y, m = _mes_siguiente(self._year, self._month, 1)
        return date(y, m, 1) - timedelta(days=1)

    def _pintar_config(self) -> None:
        c = self._config
        if c is None:
            return
        self._config_pintada = True
        self.cfg_monto.setValue(float(c.monto_por_pago))
        self.cfg_valor_dia.setValue(float(c.valor_dia))
        self.cfg_dias.setText(", ".join(str(d) for d in c.dias_de_pago))
        if c.fecha_inicio is not None:
            self.cfg_inicio.setDate(_qdate(c.fecha_inicio))
        self.cfg_activo.setChecked(bool(c.activo))

    def _pintar_pagos(self) -> None:
        self._limpiar(self._pagos_box)
        self.mes_label.setText(f"PAGOS DE {_MESES[self._month - 1].upper()} {self._year}")
        if not self.pagos:
            vacio = QLabel(
                "Configura la cuenta abajo para ver tus pagos." if not (self._config and self._config.vigente)
                else "Ningún pago de este mes cae desde el inicio de la cuenta."
            )
            vacio.setObjectName("miPagoNota")
            vacio.setWordWrap(True)
            self._pagos_box.addWidget(vacio)
            return
        for p in self.pagos:
            self._pagos_box.addWidget(self._tarjeta_pago(p))

    def _tarjeta_pago(self, p: pd.DesglosePago) -> QFrame:
        card = QFrame()
        card.setObjectName("miPagoCard")
        ly = QVBoxLayout(card)
        ly.setContentsMargins(14, 10, 14, 10)
        fila = QHBoxLayout()
        titulo = QLabel(titulo_pago(p))
        titulo.setObjectName("miPagoTitulo")
        fila.addWidget(titulo)
        estado = QLabel(texto_estado(p, self._hoy))
        estado.setObjectName("miPagoEstado")
        estado.setProperty("estado", p.estado(self._hoy))
        fila.addWidget(estado)
        fila.addStretch(1)
        monto = QLabel(pd.dinero_texto(monto_de_la_tarjeta(p)))
        monto.setObjectName("miPagoMonto")
        fila.addWidget(monto)
        ly.addLayout(fila)
        desglose = QLabel("\n".join(lineas_desglose(p)))
        desglose.setObjectName("miPagoDesglose")
        desglose.setWordWrap(True)
        ly.addWidget(desglose)
        botones = QHBoxLayout()
        botones.addStretch(1)
        if p.pagado:
            b = QPushButton("Deshacer pago")
            b.clicked.connect(lambda _c=False, pago=p: self._deshacer(pago))
        else:
            b = QPushButton("💵 Ya me pagaron")
            b.setObjectName("miPagoPrimario")
            b.clicked.connect(lambda _c=False, pago=p: self._ya_me_pagaron(pago))
        b.setAutoDefault(False)
        botones.addWidget(b)
        ly.addLayout(botones)
        card.boton = b          # para las pruebas
        card.monto = monto
        return card

    def _pintar_extras(self) -> None:
        self._limpiar(self._extras_box)
        if not self.extras:
            vacio = QLabel("No hay días de más. Se apuntan en el calendario con «Sí trabajó» en tu descanso.")
            vacio.setObjectName("miPagoNota")
            vacio.setWordWrap(True)
            self._extras_box.addWidget(vacio)
            return
        for e in self.extras:
            fila_w = QWidget()
            fila = QHBoxLayout(fila_w)
            fila.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(texto_dia_extra(e))
            fila.addWidget(lbl, 1)
            pagar = QPushButton("💵 Págamelo")
            guardar = QPushButton("📦 Guárdamelo")
            for b, destino in ((pagar, pd.PAGAR), (guardar, pd.ACUMULAR)):
                b.setAutoDefault(False)
                b.setEnabled(e.sin_decidir or e.destino != destino)
                b.clicked.connect(lambda _c=False, f=e.fecha, d=destino: self._decidir(f, d))
                fila.addWidget(b)
            self._extras_box.addWidget(fila_w)

    # ── acciones ──
    def _mover_mes(self, delta: int) -> None:
        self._year, self._month = _mes_siguiente(self._year, self._month, delta)
        self.recargar()

    def _ya_me_pagaron(self, p: pd.DesglosePago) -> None:
        dlg = _YaMePagaronDialog(self, p, self._hoy)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        fecha_pago, monto = dlg.valores()
        self.registrar(p.fecha_programada, fecha_pago, monto)

    def registrar(self, fecha_programada: date, fecha_pago: date, monto: Decimal | None) -> bool:
        try:
            with self._sf() as session:
                hecho = pd.registrar_pago(session, fecha_programada, fecha_pago, monto, self._quien, hoy=self._hoy)
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "No se guardó", str(exc))
            return False
        except Exception:  # noqa: BLE001
            logger.exception("Mi pago: no se registró el pago")
            QMessageBox.warning(self, "No se guardó", "Inténtalo otra vez.")
            return False
        self.status.setText(
            f"Pago {hecho.etiqueta} guardado: {pd.dinero_texto(hecho.registro.monto)} "
            f"el {pd.fecha_corta(fecha_pago)}."
        )
        self.recargar()
        return True

    def _deshacer(self, p: pd.DesglosePago) -> None:
        r = QMessageBox.question(
            self, "Deshacer pago",
            f"¿Deshacer el pago {titulo_pago(p)}?\n\nVuelve a quedar como pendiente.",
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        self.deshacer(p.fecha_programada)

    def deshacer(self, fecha_programada: date) -> bool:
        try:
            with self._sf() as session:
                hecho = pd.deshacer_pago(session, fecha_programada, self._quien)
        except (ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "No se deshizo", str(exc))
            return False
        except Exception:  # noqa: BLE001
            logger.exception("Mi pago: no se deshizo el pago")
            QMessageBox.warning(self, "No se deshizo", "Inténtalo otra vez.")
            return False
        self.status.setText("Pago deshecho." if hecho else "Ese pago ya no estaba registrado.")
        self.recargar()
        return hecho

    def _decidir(self, fecha: date, destino: str) -> None:
        try:
            with self._sf() as session:
                pd.decidir_dia_extra(session, fecha, destino)
        except ValueError as exc:
            QMessageBox.warning(self, "No se guardó", str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Mi pago: no se guardó el destino")
            QMessageBox.warning(self, "No se guardó", "Inténtalo otra vez.")
            return
        self.status.setText(
            f"{pd.fecha_corta(fecha)}: " + ("se paga en su pago." if destino == pd.PAGAR else "queda como día a favor.")
        )
        self.recargar()

    def _guardar_config(self) -> None:
        try:
            dias = leer_dias_de_pago(self.cfg_dias.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Revisa las fechas", str(exc))
            return
        try:
            with self._sf() as session:
                pd.guardar_config(
                    session,
                    fecha_inicio=_de_qdate(self.cfg_inicio.date()),
                    monto_por_pago=Decimal(str(self.cfg_monto.value())),
                    valor_dia=Decimal(str(self.cfg_valor_dia.value())),
                    dias_de_pago=dias,
                    activo=self.cfg_activo.isChecked(),
                )
        except ValueError as exc:
            QMessageBox.warning(self, "No se guardó", str(exc))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Mi pago: no se guardó la configuración")
            QMessageBox.warning(self, "No se guardó", "Inténtalo otra vez.")
            return
        self.status.setText("Configuración guardada.")
        self.recargar(pintar_config=True)


def abrir_mi_pago(parent: QWidget | None, quien: str | None) -> bool:
    """Lo que dispara el menú «💼 Caja ▾». Solo VEND-1. True si se abrió."""
    if str(quien or "").strip().upper() != pd.EMPLOYEE_CODE:
        QMessageBox.information(parent, "Mi pago", "Esta cuenta es solo del dueño.")
        return False
    MiPagoDialog(parent, quien=pd.EMPLOYEE_CODE).exec()
    return True
