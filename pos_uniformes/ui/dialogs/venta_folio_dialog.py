"""La venta encontrada por su folio (QR del ticket), con la cara del kiosko.

Daniel (2026-11-12): «hay que hacerlo que se vea bonito». Una tarjeta en vez
del aviso gris: el folio grande arriba, quién y cuándo, lo que se llevó como
lista, el total con cómo se pagó en fichas, y botones grandes para tocar.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

CREMA = "#f4ede2"
TARJETA = "#fffdf9"
BORDE = "#e6dccd"
TINTA = "#2c2a27"
GRIS = "#8a7a68"
CAFE = "#73341c"
VINO = "#6b1f3a"

_CERO = Decimal("0")


def _d(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))


def datos_de_venta(v) -> dict:
    """Lo que la ventana enseña, ya resuelto (se prueba sin pantalla)."""
    from pos_uniformes.services.folio_venta_service import folio_corto

    try:
        local = v.created_at.astimezone() if v.created_at.tzinfo else v.created_at
        cuando = local.strftime("%d/%m/%Y · %H:%M")
    except Exception:  # noqa: BLE001
        cuando = ""
    total = _d(v.monto_total)
    monedero = _d(v.monto_monedero)
    resto = max(total - monedero, _CERO)
    pagos = []
    if resto > 0:
        pagos.append(("💳 Tarjeta" if v.pago_tarjeta else "💵 Efectivo", resto))
    if monedero > 0:
        pagos.append(("👛 Monedero", monedero))
    articulos = []
    for d in v.detalle or []:
        cantidad = int(d.get("cantidad", 0) or 0)
        precio = _d(d.get("precio"))
        articulos.append({
            "nombre": str(d.get("nombre", "") or "").strip() or str(d.get("sku", "")),
            "talla": str(d.get("talla", "") or "").strip(),
            "cantidad": cantidad,
            "importe": (precio * cantidad).quantize(Decimal("0.01")),
        })
    piezas = sum(a["cantidad"] for a in articulos)
    return {
        "folio": folio_corto(v.operacion_uuid) if v.operacion_uuid else "—",
        "tipo": f"{str(v.tipo).capitalize()} #{v.id}",
        "cuando": cuando,
        "atendio": str(v.employee_name or v.employee_code or ""),
        "cliente": str(v.cliente or "").strip(),
        "articulos": articulos,
        "piezas": piezas,
        "total": total,
        "pagos": pagos,
        "descuento_empleada": bool(v.descuento_empleada),
    }


def _etiqueta(texto: str, estilo: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet(f"background: transparent; {estilo}")
    return lbl


def _ficha(texto: str, fondo: str, color: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet(
        f"background: {fondo}; color: {color}; border-radius: 11px;"
        " padding: 4px 12px; font-size: 14px; font-weight: 700;"
    )
    return lbl


def _tarjeta() -> tuple[QFrame, QVBoxLayout]:
    marco = QFrame()
    marco.setObjectName("tarjeta")
    marco.setStyleSheet(
        f"QFrame#tarjeta {{ background: {TARJETA}; border: 1px solid {BORDE}; border-radius: 16px; }}"
    )
    ly = QVBoxLayout(marco)
    ly.setContentsMargins(18, 14, 18, 14)
    ly.setSpacing(8)
    return marco, ly


class VentaFolioDialog(QDialog):
    def __init__(self, venta, parent=None, *, al_reimprimir: Callable[[], None] | None = None) -> None:
        super().__init__(parent)
        self._al_reimprimir = al_reimprimir
        datos = datos_de_venta(venta)
        self.setWindowTitle(f"Venta {datos['folio']}")
        self.setMinimumWidth(500)
        self.setStyleSheet(f"QDialog {{ background: {CREMA}; }}")

        ly = QVBoxLayout(self)
        ly.setContentsMargins(24, 22, 24, 20)
        ly.setSpacing(14)

        # ── Encabezado: el folio manda ──
        ly.addWidget(_etiqueta("VENTA ENCONTRADA", f"color: {GRIS}; font-size: 12px; font-weight: 800; letter-spacing: 2px;"))
        fila = QHBoxLayout()
        fila.setSpacing(10)
        self.folio = _etiqueta(f"Folio {datos['folio']}", f"color: {CAFE}; font-size: 28px; font-weight: 900;")
        fila.addWidget(self.folio)
        fila.addStretch(1)
        fila.addWidget(_ficha(datos["tipo"], "#efe4d4", CAFE), 0, Qt.AlignmentFlag.AlignVCenter)
        ly.addLayout(fila)
        quien = f"{datos['cuando']}  ·  atendió <b>{datos['atendio']}</b>" if datos["cuando"] else f"Atendió <b>{datos['atendio']}</b>"
        ly.addWidget(_etiqueta(quien, f"color: {TINTA}; font-size: 15px;"))
        if datos["cliente"] or datos["descuento_empleada"]:
            fichas = QHBoxLayout()
            fichas.setSpacing(8)
            if datos["cliente"]:
                fichas.addWidget(_ficha(f"👤 {datos['cliente']}", "#f1e3e8", VINO))
            if datos["descuento_empleada"]:
                fichas.addWidget(_ficha("Descuento de empleada", "#fbefd5", "#8a5a00"))
            fichas.addStretch(1)
            ly.addLayout(fichas)

        # ── Lo que se llevó ──
        marco, art = _tarjeta()
        art.addWidget(_etiqueta(
            f"LO QUE SE LLEVÓ · {datos['piezas']} pieza{'s' if datos['piezas'] != 1 else ''}",
            f"color: {GRIS}; font-size: 12px; font-weight: 800; letter-spacing: 1px;",
        ))
        lista = QWidget()
        lista.setStyleSheet("background: transparent;")
        filas = QVBoxLayout(lista)
        filas.setContentsMargins(0, 0, 0, 0)
        filas.setSpacing(0)
        for i, a in enumerate(datos["articulos"] or [{"nombre": "(sin artículos)", "talla": "", "cantidad": 0, "importe": None}]):
            renglon = QWidget()
            borde = f"border-top: 1px solid {BORDE};" if i else ""
            renglon.setObjectName("renglon")
            renglon.setStyleSheet(f"QWidget#renglon {{ background: transparent; {borde} }}")
            r = QHBoxLayout(renglon)
            r.setContentsMargins(0, 9, 0, 9)
            r.setSpacing(10)
            nombre = _etiqueta(a["nombre"], f"color: {TINTA}; font-size: 16px; font-weight: 700;")
            nombre.setWordWrap(True)
            r.addWidget(nombre, 1)
            # Talla y cantidad de ancho fijo: la columna de precios queda derecha.
            talla = _ficha(f"T. {a['talla']}", "#efe4d4", CAFE) if a["talla"] else QLabel("")
            talla.setFixedWidth(72)
            talla.setAlignment(Qt.AlignmentFlag.AlignCenter)
            r.addWidget(talla)
            cantidad = _etiqueta(f"×{a['cantidad']}" if a["cantidad"] else "", f"color: {GRIS}; font-size: 15px; font-weight: 700;")
            cantidad.setFixedWidth(36)
            cantidad.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            r.addWidget(cantidad)
            if a["importe"] is not None:
                precio = _etiqueta(f"${a['importe']:,.2f}", f"color: {TINTA}; font-size: 16px; font-weight: 800;")
                precio.setMinimumWidth(96)
                precio.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                r.addWidget(precio)
            filas.addWidget(renglon)
        if len(datos["articulos"]) > 5:
            # Una venta grande no empuja los botones fuera de la pantalla.
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")
            scroll.setWidget(lista)
            scroll.setMinimumHeight(260)
            art.addWidget(scroll)
        else:
            art.addWidget(lista)
        ly.addWidget(marco)

        # ── Total y cómo pagó ──
        marco, tot = _tarjeta()
        fila_total = QHBoxLayout()
        fila_total.addWidget(_etiqueta("Total", f"color: {TINTA}; font-size: 18px; font-weight: 800;"))
        fila_total.addStretch(1)
        self.total = _etiqueta(f"${datos['total']:,.2f}", f"color: {CAFE}; font-size: 26px; font-weight: 900;")
        fila_total.addWidget(self.total)
        tot.addLayout(fila_total)
        if datos["pagos"]:
            fichas = QHBoxLayout()
            fichas.setSpacing(8)
            fichas.addWidget(_etiqueta("Pagó con", f"color: {GRIS}; font-size: 14px;"))
            for nombre, monto in datos["pagos"]:
                fichas.addWidget(_ficha(f"{nombre} ${monto:,.2f}", "#eef2ea", "#2f5d3a"))
            fichas.addStretch(1)
            tot.addLayout(fichas)
        ly.addWidget(marco)

        # ── Botones ──
        botones = QHBoxLayout()
        botones.setSpacing(12)
        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.setStyleSheet(
            f"QPushButton {{ background: #f8f2e9; color: {CAFE}; border: 1.5px solid #ddd0c0;"
            "  border-radius: 14px; min-height: 52px; padding: 0 22px; font-size: 16px; font-weight: 800; }"
            "QPushButton:pressed { background: #e8dbc7; }"
        )
        self.btn_cerrar.clicked.connect(self.reject)
        botones.addWidget(self.btn_cerrar)
        self.btn_reimprimir = QPushButton("🖨  Reimprimir ticket")
        self.btn_reimprimir.setStyleSheet(
            f"QPushButton {{ background: {VINO}; color: #ffffff; border: none;"
            "  border-radius: 14px; min-height: 52px; padding: 0 22px; font-size: 16px; font-weight: 800; }"
            "QPushButton:pressed { background: #521629; }"
        )
        self.btn_reimprimir.setVisible(al_reimprimir is not None and str(venta.tipo) in ("venta", "apartado"))
        self.btn_reimprimir.clicked.connect(self._reimprimir)
        self.btn_reimprimir.setDefault(True)
        botones.addWidget(self.btn_reimprimir, 1)
        ly.addLayout(botones)

    def _reimprimir(self) -> None:
        self.accept()
        if self._al_reimprimir is not None:
            self._al_reimprimir()
