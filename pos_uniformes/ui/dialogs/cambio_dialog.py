"""Cambio de prenda desde la venta encontrada por su folio (2026-11-12).

A la izquierda lo que el cliente regresa (de lo que se llevó en esa venta),
a la derecha lo que se lleva (se escanea), y abajo la cuenta al momento:
paga la diferencia, o le queda a favor en su Monedero, o queda parejo.

La pantalla solo arma el cambio y enseña la cuenta (la misma función pura
del servicio); registrar —Libreta, stock y Monedero— lo hace quien la abre.

2026-11-12 (Daniel: «solucionemos estos»): lo vendido en Liquidación sale
marcado «Liquidación · sin cambio» y no se puede elegir para regresar; con el
gafete del dueño sí (la misma autorización que el plazo vencido).
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
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pos_uniformes.services import cambio_service as cs
from pos_uniformes.ui.dialogs.venta_folio_dialog import (
    BORDE,
    CAFE,
    CREMA,
    GRIS,
    TINTA,
    VINO,
    _etiqueta,
    _ficha,
    _tarjeta,
)

_CERO = Decimal("0.00")
_BTN_PASO = (
    "QPushButton { background: #f8f2e9; color: #73341c; border: 1.5px solid #ddd0c0;"
    "  border-radius: 10px; font-size: 20px; font-weight: 800; min-width: 40px; min-height: 40px; }"
    "QPushButton:pressed { background: #e8dbc7; }"
    "QPushButton:disabled { color: #cbbfae; border-color: #ebe3d6; }"
)
_BTN_PAGO = (
    "QPushButton { background: #ffffff; color: #2c2a27; border: 2px solid #ddd0c0;"
    "  border-radius: 12px; min-height: 44px; padding: 0 16px; font-size: 15px; font-weight: 700; }"
    "QPushButton:checked { background: #f7e3d8; color: #73341c; border: 3px solid #a84f2d; }"
)


def _dinero(valor: Decimal) -> str:
    return f"${valor:,.2f}"


def _scroll(contenido: QWidget, alto: int) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")
    scroll.setWidget(contenido)
    scroll.setMinimumHeight(alto)
    return scroll


class CambioDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        datos_venta: dict,
        renglones: list[cs.RenglonVendido],
        abono: Decimal,
        ya_quitado: Decimal,
        dias: int,
        cliente: tuple[int, str] | None,
        buscar_producto: Callable[[str], dict],
        elegir_cliente: Callable[[], tuple[int, str] | None],
        es_dueno: Callable[[str], bool],
        registrar: Callable[[dict], str | None],
    ) -> None:
        super().__init__(parent)
        self._renglones = renglones
        self._abono, self._ya = abono, ya_quitado
        self._dias = dias
        self._cliente = cliente
        self._buscar_producto = buscar_producto
        self._elegir_cliente = elegir_cliente
        self._es_dueno = es_dueno
        self._registrar = registrar
        self.regresa: dict[int, int] = {}
        self.lleva: list[dict] = []
        self.tarjeta = False
        self.autorizado = dias <= cs.PLAZO_DIAS   # el plazo está bien (o lo autorizó el dueño)
        self.dueno = False                        # el dueño escaneó su gafete
        self._hay_liquidacion = any(r.liquidacion and r.disponibles for r in renglones)

        self.setWindowTitle(f"Cambio · Folio {datos_venta['folio']}")
        self.setMinimumWidth(920)
        self.setStyleSheet(f"QDialog {{ background: {CREMA}; }}")
        ly = QVBoxLayout(self)
        ly.setContentsMargins(24, 20, 24, 18)
        ly.setSpacing(12)

        ly.addWidget(_etiqueta("CAMBIO DE PRENDA", f"color: {GRIS}; font-size: 12px; font-weight: 800; letter-spacing: 2px;"))
        fila = QHBoxLayout()
        fila.addWidget(_etiqueta(f"Folio {datos_venta['folio']}", f"color: {CAFE}; font-size: 26px; font-weight: 900;"))
        fila.addStretch(1)
        quien = f"Venta del {datos_venta['cuando']} · atendió <b>{datos_venta['atendio']}</b>"
        fila.addWidget(_etiqueta(quien, f"color: {TINTA}; font-size: 14px;"))
        ly.addLayout(fila)

        # ── Plazo ──
        self.aviso_plazo = QFrame()
        self.aviso_plazo.setObjectName("plazo")
        plazo = QHBoxLayout(self.aviso_plazo)
        plazo.setContentsMargins(16, 10, 16, 10)
        self.texto_plazo = _etiqueta("", "font-size: 14px; font-weight: 700;")
        self.texto_plazo.setWordWrap(True)
        plazo.addWidget(self.texto_plazo, 1)
        self.gafete = QLineEdit()
        self.gafete.setPlaceholderText("Gafete del dueño…")
        self.gafete.setEchoMode(QLineEdit.EchoMode.Password)
        self.gafete.setFixedWidth(200)
        self.gafete.setStyleSheet("background: #ffffff; border: 2px solid #e2c48a; border-radius: 10px; min-height: 36px; padding: 0 10px; font-size: 15px;")
        self.gafete.returnPressed.connect(self._autorizar)
        plazo.addWidget(self.gafete)
        ly.addWidget(self.aviso_plazo)
        self.aviso_plazo.setVisible(dias > cs.PLAZO_DIAS or self._hay_liquidacion)

        # ── Regresa | Se lleva ──
        columnas = QHBoxLayout()
        columnas.setSpacing(14)
        marco, izq = _tarjeta()
        izq.addWidget(_etiqueta("↩  REGRESA", f"color: {CAFE}; font-size: 13px; font-weight: 900; letter-spacing: 1px;"))
        lista = QWidget()
        filas = QVBoxLayout(lista)
        filas.setContentsMargins(0, 0, 0, 0)
        filas.setSpacing(0)
        self._cantidades: dict[int, QLabel] = {}
        self._botones: dict[int, tuple[QPushButton, QPushButton]] = {}
        for r in renglones:
            filas.addWidget(self._renglon_regresa(r))
        filas.addStretch(1)
        izq.addWidget(_scroll(lista, 220))
        columnas.addWidget(marco, 1)

        marco, der = _tarjeta()
        der.addWidget(_etiqueta("→  SE LLEVA", f"color: {CAFE}; font-size: 13px; font-weight: 900; letter-spacing: 1px;"))
        self.escaner = QLineEdit()
        self.escaner.setPlaceholderText("Escanea la prenda nueva…")
        self.escaner.setStyleSheet(
            f"background: #ffffff; color: {TINTA}; border: 2px solid #ddd0c0; border-radius: 12px;"
            " min-height: 44px; padding: 0 14px; font-size: 16px;"
        )
        self.escaner.returnPressed.connect(self._escanear)
        der.addWidget(self.escaner)
        self._lista_lleva = QWidget()
        self._filas_lleva = QVBoxLayout(self._lista_lleva)
        self._filas_lleva.setContentsMargins(0, 0, 0, 0)
        self._filas_lleva.setSpacing(0)
        der.addWidget(_scroll(self._lista_lleva, 170))
        columnas.addWidget(marco, 1)
        ly.addLayout(columnas, 1)

        # ── La cuenta ──
        marco, cuenta = _tarjeta()
        self._fila_regresa = self._fila_cuenta(cuenta, "Regresa (lo que pagó)")
        self._fila_monedero = self._fila_cuenta(cuenta, "Monedero que ganó por eso")
        self._fila_lleva = self._fila_cuenta(cuenta, "Se lleva (precio de hoy)")
        linea = QFrame()
        linea.setFixedHeight(1)
        linea.setStyleSheet(f"background: {BORDE};")
        cuenta.addWidget(linea)
        resultado = QHBoxLayout()
        self.resultado = _etiqueta("", f"color: {CAFE}; font-size: 24px; font-weight: 900;")
        resultado.addWidget(self.resultado)
        resultado.addStretch(1)
        self.btn_efectivo = QPushButton("💵 Efectivo")
        self.btn_tarjeta = QPushButton("💳 Tarjeta")
        for b in (self.btn_efectivo, self.btn_tarjeta):
            b.setCheckable(True)
            b.setStyleSheet(_BTN_PAGO)
            resultado.addWidget(b)
        self.btn_efectivo.setChecked(True)
        self.btn_efectivo.clicked.connect(lambda: self._pago(False))
        self.btn_tarjeta.clicked.connect(lambda: self._pago(True))
        self.ficha_cliente = _ficha("", "#f1e3e8", VINO)
        resultado.addWidget(self.ficha_cliente)
        self.btn_cliente = QPushButton("👤 Elegir cliente")
        self.btn_cliente.setStyleSheet(_BTN_PAGO)
        self.btn_cliente.clicked.connect(self._pedir_cliente)
        resultado.addWidget(self.btn_cliente)
        cuenta.addLayout(resultado)
        self.nota = _etiqueta("", f"color: {GRIS}; font-size: 13px;")
        self.nota.setWordWrap(True)
        cuenta.addWidget(self.nota)
        ly.addWidget(marco)

        # ── Botones ──
        botones = QHBoxLayout()
        botones.setSpacing(12)
        cancelar = QPushButton("Cancelar")
        cancelar.setStyleSheet(
            f"QPushButton {{ background: #f8f2e9; color: {CAFE}; border: 1.5px solid #ddd0c0;"
            "  border-radius: 14px; min-height: 52px; padding: 0 22px; font-size: 16px; font-weight: 800; }"
            "QPushButton:pressed { background: #e8dbc7; }"
        )
        cancelar.clicked.connect(self.reject)
        botones.addWidget(cancelar)
        self.btn_hacer = QPushButton("✔  Hacer cambio")
        self.btn_hacer.setStyleSheet(
            f"QPushButton {{ background: {VINO}; color: #ffffff; border: none;"
            "  border-radius: 14px; min-height: 52px; padding: 0 22px; font-size: 16px; font-weight: 800; }"
            "QPushButton:pressed { background: #521629; }"
            "QPushButton:disabled { background: #cdb9c0; }"
        )
        self.btn_hacer.clicked.connect(self._hacer)
        botones.addWidget(self.btn_hacer, 1)
        ly.addLayout(botones)

        self._pintar()
        self.escaner.setFocus()

    # ─── Piezas ──────────────────────────────────────────────────────────

    def _renglon_regresa(self, r: cs.RenglonVendido) -> QWidget:
        w = QWidget()
        w.setObjectName("renglon")
        borde = f"border-top: 1px solid {BORDE};" if r.renglon else ""
        w.setStyleSheet(f"QWidget#renglon {{ background: transparent; {borde} }}")
        fila = QHBoxLayout(w)
        fila.setContentsMargins(0, 8, 0, 8)
        fila.setSpacing(8)
        texto = QVBoxLayout()
        texto.setSpacing(2)
        nombre = _etiqueta(r.nombre, f"color: {TINTA}; font-size: 15px; font-weight: 700;")
        nombre.setWordWrap(True)
        texto.addWidget(nombre)
        detalle = f"T. {r.talla} · {_dinero(r.valor_pieza.quantize(Decimal('0.01')))} c/u" if r.talla else \
            f"{_dinero(r.valor_pieza.quantize(Decimal('0.01')))} c/u"
        if r.ya_cambiadas:
            detalle += f" · ya cambiada{'s' if r.ya_cambiadas != 1 else ''} {r.ya_cambiadas}"
        texto.addWidget(_etiqueta(detalle, f"color: {GRIS}; font-size: 13px;"))
        if r.liquidacion:
            texto.addWidget(_etiqueta("Liquidación · sin cambio", f"color: {VINO}; font-size: 13px; font-weight: 800;"))
        fila.addLayout(texto, 1)
        menos, mas = QPushButton("−"), QPushButton("+")
        for b in (menos, mas):
            b.setStyleSheet(_BTN_PASO)
        cantidad = _etiqueta("0", f"color: {TINTA}; font-size: 18px; font-weight: 900;")
        cantidad.setFixedWidth(34)
        cantidad.setAlignment(Qt.AlignmentFlag.AlignCenter)
        menos.clicked.connect(lambda: self._mover(r.renglon, -1))
        mas.clicked.connect(lambda: self._mover(r.renglon, +1))
        fila.addWidget(menos)
        fila.addWidget(cantidad)
        fila.addWidget(mas)
        self._cantidades[r.renglon] = cantidad
        self._botones[r.renglon] = (menos, mas)
        return w

    def _mover(self, renglon: int, paso: int) -> None:
        r = self._renglones[renglon]
        if paso > 0 and r.liquidacion and not self.dueno:
            return   # Liquidación: sin cambio, salvo con el gafete del dueño
        nueva = min(max(self.regresa.get(renglon, 0) + paso, 0), r.disponibles)
        if nueva:
            self.regresa[renglon] = nueva
        else:
            self.regresa.pop(renglon, None)
        self._pintar()

    def _escanear(self) -> None:
        sku = self.escaner.text().strip()
        self.escaner.clear()
        if not sku:
            return
        try:
            item = self._buscar_producto(sku)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Prenda no encontrada", str(exc))
            return
        self.agregar(item)

    def agregar(self, item: dict) -> None:
        igual = next((it for it in self.lleva if it["sku"] == item["sku"]), None)
        if igual is not None:
            igual["cantidad"] += 1
        else:
            self.lleva.append({**item, "cantidad": 1})
        self._pintar_lleva()
        self._pintar()

    def _quitar(self, sku: str) -> None:
        igual = next((it for it in self.lleva if it["sku"] == sku), None)
        if igual is None:
            return
        igual["cantidad"] -= 1
        if igual["cantidad"] <= 0:
            self.lleva.remove(igual)
        self._pintar_lleva()
        self._pintar()

    def _pintar_lleva(self) -> None:
        while self._filas_lleva.count():
            hijo = self._filas_lleva.takeAt(0).widget()
            if hijo is not None:
                hijo.setParent(None)   # se va ya, no hasta el siguiente ciclo
                hijo.deleteLater()
        if not self.lleva:
            vacio = _etiqueta("Nada todavía. Si no se lleva nada, todo queda a favor en su Monedero.",
                              f"color: {GRIS}; font-size: 13px;")
            vacio.setWordWrap(True)
            self._filas_lleva.addWidget(vacio)
        for i, it in enumerate(self.lleva):
            w = QWidget()
            w.setObjectName("renglon")
            borde = f"border-top: 1px solid {BORDE};" if i else ""
            w.setStyleSheet(f"QWidget#renglon {{ background: transparent; {borde} }}")
            fila = QHBoxLayout(w)
            fila.setContentsMargins(0, 8, 0, 8)
            fila.setSpacing(8)
            nombre = _etiqueta(it["nombre"], f"color: {TINTA}; font-size: 15px; font-weight: 700;")
            nombre.setWordWrap(True)
            fila.addWidget(nombre, 1)
            if it.get("talla"):
                fila.addWidget(_ficha(f"T. {it['talla']}", "#efe4d4", CAFE))
            fila.addWidget(_etiqueta(f"×{it['cantidad']}", f"color: {GRIS}; font-size: 15px; font-weight: 700;"))
            precio = _etiqueta(_dinero(Decimal(str(it["precio"])) * it["cantidad"]), f"color: {TINTA}; font-size: 15px; font-weight: 800;")
            precio.setMinimumWidth(86)
            precio.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            fila.addWidget(precio)
            quitar = QPushButton("✕")
            quitar.setStyleSheet(_BTN_PASO)
            quitar.clicked.connect(lambda _=False, sku=it["sku"]: self._quitar(sku))
            fila.addWidget(quitar)
            self._filas_lleva.addWidget(w)
        self._filas_lleva.addStretch(1)

    # ─── La cuenta ───────────────────────────────────────────────────────

    def _fila_cuenta(self, ly: QVBoxLayout, texto: str) -> tuple[QWidget, QLabel]:
        w = QWidget()
        fila = QHBoxLayout(w)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.addWidget(_etiqueta(texto, f"color: {TINTA}; font-size: 15px;"))
        fila.addStretch(1)
        valor = _etiqueta("", f"color: {TINTA}; font-size: 16px; font-weight: 800;")
        fila.addWidget(valor)
        ly.addWidget(w)
        return w, valor

    def calcular(self) -> cs.Cuenta:
        valor_regresa = sum((self._renglones[i].valor_pieza * q for i, q in self.regresa.items()), Decimal(0))
        quitar = cs.cashback_proporcional(self._abono, self._ya, self._renglones, self.regresa)
        valor_lleva = sum((Decimal(str(it["precio"])) * it["cantidad"] for it in self.lleva), Decimal(0))
        return cs.cuenta(valor_regresa, quitar, valor_lleva)

    def _pintar(self) -> None:
        for i, etiqueta in self._cantidades.items():
            n = self.regresa.get(i, 0)
            etiqueta.setText(str(n))
            menos, mas = self._botones[i]
            menos.setEnabled(n > 0)
            r = self._renglones[i]
            mas.setEnabled(n < r.disponibles and (self.dueno or not r.liquidacion))
        if not self.lleva and not self._filas_lleva.count():
            self._pintar_lleva()
        c = self.calcular()
        self._fila_regresa[1].setText(_dinero(c.valor_regresa))
        self._fila_monedero[0].setVisible(c.cashback_quitado > 0)
        self._fila_monedero[1].setText(f"−{_dinero(c.cashback_quitado)}")
        self._fila_lleva[1].setText(_dinero(c.valor_lleva))
        paga = c.a_pagar > 0
        favor = c.a_favor > 0
        if not self.regresa:
            self.resultado.setText("Elige qué regresa")
        elif paga:
            self.resultado.setText(f"Paga {_dinero(c.a_pagar)}")
        elif favor:
            self.resultado.setText(f"A favor {_dinero(c.a_favor)} → Monedero")
        else:
            self.resultado.setText("Queda parejo")
        self.btn_efectivo.setVisible(paga)
        self.btn_tarjeta.setVisible(paga)
        self.ficha_cliente.setVisible(favor and self._cliente is not None)
        if self._cliente is not None:
            self.ficha_cliente.setText(f"👤 {self._cliente[1]}")
        self.btn_cliente.setVisible(favor and self._cliente is None)
        notas = []
        if favor and self._cliente is None:
            notas.append("La venta no tiene cliente: elígelo o regístralo para abonarle lo que queda a favor.")
        if self._abono > 0 and c.cashback_quitado > 0:
            notas.append("Se le quita el Monedero que ganó por lo que regresa.")
        self.nota.setText(" ".join(notas))
        self.nota.setVisible(bool(notas))
        self._pintar_plazo()
        self.btn_hacer.setEnabled(bool(self.regresa) and self.autorizado and (not favor or self._cliente is not None))

    def _pintar_plazo(self) -> None:
        if self.autorizado and (self.dueno or not self._hay_liquidacion):
            self.aviso_plazo.setStyleSheet("QFrame#plazo { background: #e3f1e6; border-radius: 12px; }")
            if self._dias > cs.PLAZO_DIAS:
                self.texto_plazo.setText(f"✓ Esta venta tiene {self._dias} días: el dueño autorizó el cambio.")
            else:
                self.texto_plazo.setText("✓ El dueño autorizó el cambio de la prenda en Liquidación.")
            self.texto_plazo.setStyleSheet("background: transparent; color: #2f5d3a; font-size: 14px; font-weight: 700;")
            self.gafete.setVisible(False)
        else:
            self.aviso_plazo.setStyleSheet("QFrame#plazo { background: #fbefd5; border-radius: 12px; }")
            partes = []
            if not self.autorizado:
                partes.append(f"Esta venta tiene {self._dias} días y el plazo de cambio es de {cs.PLAZO_DIAS}.")
            if self._hay_liquidacion and not self.dueno:
                partes.append("Las prendas en Liquidación no tienen cambio ni devolución.")
            partes.append("Solo el dueño lo puede autorizar: escanea su gafete.")
            self.texto_plazo.setText(" ".join(partes))
            self.texto_plazo.setStyleSheet("background: transparent; color: #8a5a00; font-size: 14px; font-weight: 700;")

    def _autorizar(self) -> None:
        codigo = self.gafete.text()
        self.gafete.clear()
        if self._es_dueno(codigo):
            self.autorizado = True
            self.dueno = True
            self._pintar()
            self.escaner.setFocus()
        else:
            QMessageBox.warning(self, "Autorización del dueño", "Ese gafete no es del dueño.")

    def _pago(self, tarjeta: bool) -> None:
        self.tarjeta = tarjeta
        self.btn_efectivo.setChecked(not tarjeta)
        self.btn_tarjeta.setChecked(tarjeta)

    def _pedir_cliente(self) -> None:
        elegido = self._elegir_cliente()
        if elegido is not None:
            self._cliente = elegido
            self._pintar()

    def _hacer(self) -> None:
        c = self.calcular()
        error = self._registrar({
            "regresa": dict(self.regresa),
            "lleva": [dict(it) for it in self.lleva],
            "cliente_id": self._cliente[0] if self._cliente else None,
            "pago_tarjeta": self.tarjeta and c.a_pagar > 0,
            "autorizo_dueno": self.dueno and (
                self._dias > cs.PLAZO_DIAS or any(self._renglones[i].liquidacion for i in self.regresa)
            ),
        })
        if error:
            QMessageBox.warning(self, "No se hizo el cambio", error)
            return
        self.accept()
