"""Monedero en Venta rápida: identificar al cliente, ver su saldo, usarlo y
mostrar el cashback.

Las reglas viven en services/monedero_service.py; aquí solo hay pantalla.

- Se identifica escaneando el QR del cliente (`CLI-…`) en el mismo campo de
  los productos, o buscándolo por nombre/teléfono con «👛 Cliente».
- Buscarlo por nombre liga la venta (gana cashback) y deja consultar, pero
  para USAR saldo hay que escanear su QR.
- Usar saldo exige conexión: la venta se confirma en línea en una sola
  transacción ANTES de imprimir. Sin conexión no hay canje, ni con
  autorización.
- Sin usar saldo la venta sigue por la cola local de siempre; el cashback se
  acredita al subir (si se escaneó sin red, queda «pendiente»).
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

_logger = logging.getLogger(__name__)

_CERO = Decimal("0.00")
#: Lo que cabe del nombre junto a «Cliente:» en el ticket de 38 columnas.
_LARGO_NOMBRE = 25
_RE_QR_CLIENTE = re.compile(r"CLI-[A-Z0-9]+")


def lineas_ticket_monedero(info: dict, tk_row) -> list[str]:
    """Renglones del monedero bajo el total del ticket.

    info: cliente, nivel, canje, por_cobrar, metodo, cashback, cashback_pendiente, saldo
    y, si se pagó con tarjeta, tasa y base_tarjeta (regla B)."""
    lineas: list[str] = []
    # Quién es y en qué nivel va (Daniel, 2026-11-11). El nombre se corta para
    # que quepa en el renglón.
    if info.get("cliente"):
        lineas.append(tk_row("Cliente:", str(info["cliente"])[:_LARGO_NOMBRE]))
    if info.get("nivel"):
        lineas.append(tk_row("Nivel:", str(info["nivel"])[:_LARGO_NOMBRE]))
    canje = Decimal(str(info.get("canje") or 0))
    if canje > 0:
        lineas.append(tk_row("Pagado con monedero:", f"-${canje:,.2f}"))
        metodo = info.get("metodo") or "Efectivo"
        lineas.append(tk_row(f"{metodo}:", f"${Decimal(str(info.get('por_cobrar') or 0)):,.2f}"))
    cashback = Decimal(str(info.get("cashback") or 0))
    if cashback > 0:
        # Si va por la cola se abona al sincronizar (segundos): al cliente se
        # le dice igual lo que acumuló (Daniel, 2026-11-11).
        lineas.append(tk_row("Acumulado en esta compra:", f"${cashback:,.2f}"))
        if info.get("base_tarjeta") is not None:
            # Regla B (Daniel, 2026-11-12): con tarjeta se gana sobre lo que
            # deja la terminal; el ticket lo dice para que no parezca error.
            tasa = Decimal(str(info.get("tasa") or 0)).normalize()
            base = Decimal(str(info["base_tarjeta"]))
            lineas.append(tk_row(f"  {tasa:f} % sobre:", f"${base:,.2f} (tarjeta)"))
    if info.get("saldo") is not None:
        lineas.append(tk_row("Saldo en monedero:", f"${Decimal(str(info['saldo'])):,.2f}"))
    return lineas


MENSAJE_CONFIRMACION_INCIERTA = (
    "Se perdió la conexión mientras se confirmaba la venta: puede que SÍ haya quedado registrada.\n\n"
    "No cobres de otra forma todavía. Cuando vuelva la conexión, cobra otra vez con saldo "
    "SIN cambiar el carrito: si ya quedó registrada se imprime sin descontar el saldo dos veces."
)


def _es_error_de_red(exc: BaseException) -> bool:
    from sqlalchemy import exc as sa_exc

    return isinstance(exc, (sa_exc.OperationalError, sa_exc.InterfaceError, sa_exc.DisconnectionError))

#: Cuando no se puede revisar el cobro con saldo (revisión de deuda, 2026-11-12).
MENSAJE_SALDO_SIN_REVISAR = (
    "No se pudo revisar el cobro con saldo del Monedero, así que no se usó.\n\n"
    "Inténtalo otra vez. Si sigue, quita «Usar saldo» y cobra normal; el saldo se queda para otra compra."
)


class MonederoVentaMixin:
    """Se mezcla en QuickSaleWidget. Usa de él: _items, _compute_totals,
    _refresh_totals, _vaciar_carrito, _normalize_scan, satellite, etc."""

    # ─── Identificación ──────────────────────────────────────────────────

    def _es_qr_cliente(self, raw: str) -> bool:
        return bool(_RE_QR_CLIENTE.fullmatch(self._codigo_cliente_de(raw)))

    def _codigo_cliente_de(self, raw: str) -> str:
        from pos_uniformes.services.sale_selected_client_service import normalize_scanned_client_code

        return normalize_scanned_client_code(self._normalize_scan(raw))

    def _en_linea(self) -> bool:
        return bool(getattr(self.satellite, "_db_online", True))

    def _identificar_cliente(self, codigo: str, *, por_qr: bool, cliente_id: int | None = None) -> None:
        """Liga el cliente a la venta en curso y lee su monedero."""
        if not self._en_linea():
            self._cliente_sin_conexion(codigo, por_qr)
            return
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.database.models import Cliente
            from pos_uniformes.services import monedero_service as mon
            from pos_uniformes.services.sale_selected_client_service import find_active_sale_client_by_code

            with get_session() as session:
                cliente = (
                    session.get(Cliente, int(cliente_id))
                    if cliente_id is not None
                    else find_active_sale_client_by_code(session, codigo)
                )
                if cliente is None or not cliente.activo:
                    self._flash_scan_hint(f"Cliente {codigo} no encontrado")
                    return
                r = mon.resumen_cliente(session, cliente.id)
        except Exception as exc:  # noqa: BLE001
            if _es_error_de_red(exc):
                self._avisar_sin_conexion()
                self._cliente_sin_conexion(codigo, por_qr)
                return
            _logger.exception("Monedero: no se pudo leer al cliente %s", codigo)
            QMessageBox.warning(self, "Monedero", f"No se pudo leer el monedero del cliente.\n\n{exc}")
            return
        self._cliente = {
            "id": r.cliente_id,
            "codigo": r.codigo,
            "nombre": r.nombre,
            "por_qr": bool(por_qr),
            "en_linea": True,
            "tiene_monedero": r.tiene_monedero,
            "estado": r.estado,
            "disponible": r.disponible,
            "tasa": r.tasa,
            "descuento_disponible": getattr(r, "descuento_disponible", None),
            "programa": getattr(r, "programa", None),
            "proximo_vencimiento": r.proximo_vencimiento,
            "monto_proximo_vencimiento": r.monto_proximo_vencimiento,
        }
        self._usar_saldo = False
        self._usar_descuento_programa = False
        self._refresh_totals()
        self._flash_scan_hint(f"Cliente: {r.nombre}")

    def _cliente_sin_conexion(self, codigo: str, por_qr: bool) -> None:
        if not codigo or not por_qr:
            QMessageBox.information(self, "Monedero", "Sin conexión al servidor: no se puede buscar al cliente.")
            return
        # Se guarda el código: al subir la venta se liga al cliente y gana su
        # cashback. El saldo no se puede ver ni usar.
        self._cliente = {
            "id": None, "codigo": codigo, "nombre": codigo, "por_qr": True, "en_linea": False,
            "tiene_monedero": False, "estado": "activo", "disponible": _CERO, "tasa": None,
            "descuento_disponible": None,
            "proximo_vencimiento": None, "monto_proximo_vencimiento": _CERO,
        }
        self._usar_saldo = False
        self._usar_descuento_programa = False
        self._refresh_totals()
        self._flash_scan_hint("Sin conexión: el cashback se acreditará al sincronizar")

    def _on_buscar_cliente(self) -> None:
        texto, ok = QInputDialog.getText(self, "Buscar cliente", "Nombre, teléfono o código del cliente:")
        texto = (texto or "").strip()
        if not ok or not texto:
            return
        if not self._en_linea():
            QMessageBox.information(self, "Monedero", "Sin conexión al servidor: no se puede buscar al cliente.")
            return
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services import monedero_service as mon

            with get_session() as session:
                encontrados = [(c.id, c.codigo_cliente, c.nombre, c.telefono or "") for c in mon.buscar_clientes(session, texto, 30)]
        except Exception as exc:  # noqa: BLE001
            if _es_error_de_red(exc):
                self._avisar_sin_conexion()
            QMessageBox.warning(self, "Monedero", f"No se pudo buscar al cliente.\n\n{exc}")
            return
        if not encontrados:
            QMessageBox.information(self, "Buscar cliente", "No se encontró ningún cliente activo.")
            return
        if len(encontrados) == 1:
            elegido = encontrados[0]
        else:
            etiquetas = [f"{nombre} · {codigo}" + (f" · {tel}" if tel else "") for _id, codigo, nombre, tel in encontrados]
            etiqueta, ok = QInputDialog.getItem(self, "Buscar cliente", "Elige al cliente:", etiquetas, 0, False)
            if not ok:
                return
            elegido = encontrados[etiquetas.index(etiqueta)]
        self._identificar_cliente(elegido[1], por_qr=False, cliente_id=elegido[0])

    def _quitar_cliente(self) -> None:
        self._cliente = None
        self._usar_saldo = False
        self._usar_descuento_programa = False
        self._refresh_totals()

    # ─── Cálculos ────────────────────────────────────────────────────────

    def _puede_usar_saldo(self) -> bool:
        c = self._cliente
        return bool(
            c and c["en_linea"] and c["por_qr"] and c["estado"] == "activo" and c["disponible"] > 0
        )

    def _canje_actual(self, total: Decimal) -> Decimal:
        if not self._usar_saldo or not self._puede_usar_saldo() or not self._items:
            return _CERO
        from pos_uniformes.services.monedero_service import canje_ajustado

        return canje_ajustado(total, self._cliente["disponible"])

    # ─── E5-A: Mayorista, descuento o Monedero ───────────────────────────

    def _pct_descuento_programa(self) -> Decimal | None:
        """El % de mayoreo de ESTA venta, o None si va al Monedero."""
        fijo = getattr(self, "_descuento_programa_fijo", None)
        if fijo:
            return Decimal(str(fijo))
        c = getattr(self, "_cliente", None)
        if not c or not getattr(self, "_usar_descuento_programa", False):
            return None
        pct = c.get("descuento_disponible")
        return Decimal(str(pct)) if pct else None

    def _marca_promo_para_libreta(self, item: dict) -> dict:
        """La Libreta necesita saber qué renglones no llevaron el de mayoreo."""
        from pos_uniformes.services.fidelizacion import descuento_programa_service as dps

        return {dps.LLAVE_PROMO: True} if self._pct_descuento_programa() and dps.es_promo_3pz(item) else {}

    def _etiqueta_descuento_ticket(self) -> str:
        pct = self._pct_descuento_programa()
        if not pct:
            return "Descuento:"
        # Con su % para que el cliente vea qué se le aplicó (Daniel, 2026-11-11).
        return f"Desc. mayoreo {pct.normalize():f} %:"

    def _toggle_descuento_programa(self) -> None:
        c = self._cliente
        self._usar_descuento_programa = bool(
            self._btn_descuento_programa.isChecked() and c and c.get("descuento_disponible")
        )
        self._refresh_totals()

    def _base_cashback_del_motor(self, total: Decimal, canje: Decimal, tarjeta: bool) -> Decimal | None:
        """La base del Monedero que calculó el motor para este carrito, o None
        si no la hay o no corresponde a este total y este saldo (2026-11-12:
        el abono del servidor sale de esa misma base, así lo impreso
        coincide con lo abonado)."""
        if getattr(self, "_calculo_fijo", None) is not None or getattr(self, "_reimpresion_legada", False):
            return None  # reimpresión: no se vuelve a decidir con las reglas de hoy
        if not getattr(self, "_items", None) or not hasattr(self, "_calculo_motor"):
            return None
        try:
            calculo = self._calculo_motor(pago_tarjeta=bool(tarjeta))
        except Exception:  # noqa: BLE001 — se usa la cuenta de antes
            return None
        if calculo is None or calculo.monedero is None:
            return None
        if calculo.total != Decimal(str(total)) or calculo.saldo_usado != Decimal(str(canje)):
            return None
        return calculo.monedero.base

    def _base_cashback(self, total: Decimal, canje: Decimal, tarjeta: bool = False) -> Decimal:
        """Sobre cuánto gana Monedero esta compra, con la misma regla que el
        abono del servidor (`monedero_service.base_cashback_de_venta`): la
        base del motor del carrito siempre que exista y corresponda a este
        total y saldo, con o sin saldo (2026-11-12, Daniel: «los centavos no
        ganan»: los del redondeo que caen en una prenda rebajada no suman).
        Sin cálculo del motor, la cuenta de antes."""
        del_motor = self._base_cashback_del_motor(total, canje, tarjeta)
        if del_motor is not None:
            return del_motor
        return self._base_cashback_legada(total, canje, tarjeta)

    def _base_cashback_legada(self, total: Decimal, canje: Decimal, tarjeta: bool = False) -> Decimal:
        """La cuenta de antes del motor (cobrado − saldo − rebajado)."""
        from pos_uniformes.services.beneficios.motor import base_monedero_con_comision, neto_con_comision
        from pos_uniformes.services.libreta_service import TERMINAL_COMMISSION_PERCENT
        from pos_uniformes.services.monedero_service import importe_elegible

        pagado = importe_elegible(total, canje)
        # E7: lo que va en Oferta o Liquidación no suma Monedero.
        base = max(pagado - self._importe_rebajado_carrito(), _CERO)
        if tarjeta and pagado > 0:
            # Regla B (Daniel, 2026-11-12): con tarjeta, sobre lo que deja la terminal.
            comision = max(pagado - neto_con_comision(pagado, TERMINAL_COMMISSION_PERCENT), _CERO)
            base = base_monedero_con_comision(base, pagado, comision)
        return base

    def _cashback_estimado(self, total: Decimal, canje: Decimal, tarjeta: bool = False) -> Decimal:
        c = self._cliente
        if not c or not c.get("tasa") or c["estado"] != "activo":
            return _CERO
        if self._pct_descuento_programa():
            return _CERO  # eligió descuento: esta compra no suma Monedero
        if getattr(self, "_discount_active", False):
            return _CERO  # D1: con descuento de empleada tampoco
        from pos_uniformes.services.monedero_service import calcular_cashback

        return calcular_cashback(self._base_cashback(total, canje, tarjeta), c["tasa"])

    def _datos_cliente_para_cola(self, tipo: str, total: Decimal, tarjeta: bool = False) -> dict:
        """Lo que la cola necesita para ligar la venta al cliente."""
        c = self._cliente
        if not c:
            return {}
        estimado = self._cashback_estimado(total, _CERO, tarjeta) if tipo == "venta" else _CERO
        return {
            "cliente_id": c["id"],
            "cliente_codigo": c["codigo"],
            "cashback_estimado": str(estimado),
        }

    def _monedero_para_ticket(self, total: Decimal, tarjeta: bool) -> dict | None:
        """Renglones del ticket de una venta SIN canje (va por la cola).

        Si el cliente tiene Monedero: lo que acumuló en esta compra y cómo le
        queda el saldo (el de al identificarlo más lo de hoy). Sin conexión el
        saldo no se conoce y solo va lo acumulado."""
        c = self._cliente
        if not c:
            return None
        estimado = self._cashback_estimado(total, _CERO, tarjeta)
        saldo = None
        if c.get("en_linea") and c.get("tiene_monedero") and c.get("estado") == "activo":
            saldo = Decimal(str(c.get("disponible") or 0)) + estimado
        if estimado <= 0 and saldo is None:
            return None
        info = {**self._cliente_para_ticket(), "cashback": estimado, "cashback_pendiente": True, "saldo": saldo}
        if tarjeta and estimado > 0:
            info.update(tasa=c.get("tasa"), base_tarjeta=self._base_cashback(total, _CERO, True))
        return info

    def _cliente_para_ticket(self) -> dict:
        """Nombre y nivel del cliente para la parte del Monedero del ticket.
        Sin conexión solo se sabe el código: no se imprime."""
        c = self._cliente
        if not c or not c.get("en_linea"):
            return {}
        return {"cliente": c.get("nombre") or None, "nivel": c.get("programa") or None}

    # ─── Barra del cliente ───────────────────────────────────────────────

    def _build_cliente_bar(self) -> QFrame:
        """La ficha del cliente en la caja (más «pro», Daniel 2026-11-12).

        Arriba su inicial, nombre y código (y «Quitar»); luego dos datos
        grandes, «Saldo» y «Gana en esta compra»; abajo las acciones. El texto
        de siempre sigue armándose en `_cliente_label` (oculto) para las
        pruebas y para quien lo lea por accesibilidad."""
        bar = QFrame()
        bar.setObjectName("clienteBar")
        bar.setStyleSheet(_FICHA_CLIENTE)
        caja = QVBoxLayout()
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(12)

        cabeza = QHBoxLayout()
        cabeza.setSpacing(12)
        self._cliente_inicial = QLabel("")
        self._cliente_inicial.setObjectName("fcInicial")
        self._cliente_inicial.setFixedSize(46, 46)
        self._cliente_inicial.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cabeza.addWidget(self._cliente_inicial)
        quien = QVBoxLayout()
        quien.setSpacing(1)
        self._cliente_nombre = QLabel("")
        self._cliente_nombre.setObjectName("fcNombre")
        quien.addWidget(self._cliente_nombre)
        self._cliente_codigo = QLabel("")
        self._cliente_codigo.setObjectName("fcCodigo")
        quien.addWidget(self._cliente_codigo)
        cabeza.addLayout(quien, 1)
        btn_quitar = QPushButton("Quitar")
        btn_quitar.setObjectName("fcQuitar")
        btn_quitar.setToolTip("Quitar al cliente de esta venta")
        btn_quitar.setAutoDefault(False)
        btn_quitar.clicked.connect(self._quitar_cliente)
        cabeza.addWidget(btn_quitar, 0, Qt.AlignmentFlag.AlignTop)
        caja.addLayout(cabeza)

        datos = QHBoxLayout()
        datos.setSpacing(10)

        def _dato(titulo: str):
            marco = QFrame()
            marco.setObjectName("fcDato")
            ly = QVBoxLayout(marco)
            ly.setContentsMargins(14, 10, 14, 10)
            ly.setSpacing(2)
            t = QLabel(titulo)
            t.setObjectName("fcDatoTitulo")
            valor = QLabel("")
            valor.setObjectName("fcDatoValor")
            nota = QLabel("")
            nota.setObjectName("fcDatoNota")
            nota.setWordWrap(True)
            for w in (t, valor, nota):
                ly.addWidget(w)
            datos.addWidget(marco, 1)
            return marco, t, valor, nota

        self._dato_saldo = _dato("SALDO")
        self._dato_gana = _dato("GANA EN ESTA COMPRA")
        caja.addLayout(datos)

        self._cliente_label = QLabel("")
        self._cliente_label.setTextFormat(Qt.TextFormat.RichText)
        self._cliente_label.setVisible(False)
        caja.addWidget(self._cliente_label)

        ly = QHBoxLayout()
        ly.setSpacing(8)
        caja.addLayout(ly)
        self._btn_usar_saldo = QPushButton("Usar saldo")
        self._btn_usar_saldo.setObjectName("fcPrincipal")
        self._btn_usar_saldo.setCheckable(True)
        self._btn_usar_saldo.setAutoDefault(False)
        self._btn_usar_saldo.clicked.connect(self._toggle_usar_saldo)
        ly.addWidget(self._btn_usar_saldo, 1)
        # E5-A: solo para programas que lo permiten (Mayorista).
        self._btn_descuento_programa = QPushButton("🏷 Descuento")
        self._btn_descuento_programa.setObjectName("fcPrincipal")
        self._btn_descuento_programa.setCheckable(True)
        self._btn_descuento_programa.setAutoDefault(False)
        self._btn_descuento_programa.setToolTip(
            "Precio de mayoreo en esta compra. Si lo usas, esta compra no suma a su Monedero."
        )
        self._btn_descuento_programa.clicked.connect(self._toggle_descuento_programa)
        self._btn_descuento_programa.setVisible(False)
        ly.addWidget(self._btn_descuento_programa, 1)
        btn_mov = QPushButton("Movimientos")
        btn_mov.setObjectName("fcSecundario")
        btn_mov.setAutoDefault(False)
        btn_mov.clicked.connect(self._ver_movimientos)
        self._btn_movimientos = btn_mov
        ly.addWidget(btn_mov, 1)
        bar.setLayout(caja)
        bar.setVisible(False)
        self._cliente_bar = bar
        return bar

    def _pintar_cliente_bar(self) -> None:
        bar = getattr(self, "_cliente_bar", None)
        if bar is None:
            return
        c = self._cliente
        bar.setVisible(c is not None)
        if c is None:
            return
        _s, _d, total = self._compute_totals()
        canje = self._canje_actual(total)
        nombre = str(c["nombre"])
        self._cliente_inicial.setText((nombre.strip()[:1] or "?").upper())
        self._cliente_nombre.setText(nombre)
        self._cliente_codigo.setText(str(c["codigo"]))
        _m, _t, saldo_valor, saldo_nota = self._dato_saldo
        _m2, _t2, gana_valor, gana_nota = self._dato_gana

        partes = [f"👛 <b>{nombre}</b> · {c['codigo']}"]
        saldo_nota.setText("")
        if not c["en_linea"]:
            partes.append("<span style='color:#9a5b00'>sin conexión: saldo no disponible</span>")
            saldo_valor.setText("—")
            saldo_nota.setText("Sin conexión")
        elif c["estado"] != "activo":
            partes.append(f"<span style='color:#a12'>monedero {c['estado']}</span>")
            saldo_valor.setText("—")
            saldo_nota.setText(f"Monedero {c['estado']}")
        else:
            partes.append(f"Saldo <b>${c['disponible']:,.2f}</b>")
            saldo_valor.setText(f"${c['disponible']:,.2f}")
            if c.get("proximo_vencimiento") and c.get("monto_proximo_vencimiento", _CERO) > 0:
                vence = c["proximo_vencimiento"].astimezone().strftime("%d/%m/%Y")
                partes.append(f"<span style='color:#8a7a68'>${c['monto_proximo_vencimiento']:,.2f} vence {vence}</span>")
                saldo_nota.setText(f"${c['monto_proximo_vencimiento']:,.2f} vence {vence}")
        saldo_nota.setVisible(bool(saldo_nota.text()))

        pct_mayoreo = self._pct_descuento_programa()
        con_empleada = bool(getattr(self, "_discount_active", False))
        gana_valor.setText("—")
        gana_nota.setText("")
        if pct_mayoreo:
            partes.append(f"<b>Precio de mayoreo −{pct_mayoreo.normalize():f} %</b> · no suma Monedero")
            gana_valor.setText(f"−{pct_mayoreo.normalize():f} %")
            gana_nota.setText("Precio de mayoreo · no suma Monedero")
        elif con_empleada:
            partes.append("<span style='color:#8a7a68'>con precio especial no suma Monedero</span>")
            gana_nota.setText("Con precio especial no suma")
        if self._items and not pct_mayoreo and not con_empleada:
            estimado = self._cashback_estimado(total, canje)
            if estimado > 0:
                partes.append(f"Gana <b>${estimado:,.2f}</b>")
                gana_valor.setText(f"${estimado:,.2f}")
                con_tarjeta = self._cashback_estimado(total, canje, True)
                if con_tarjeta != estimado:
                    # Regla B: la empleada sabe antes de cobrar cuánto gana con tarjeta.
                    partes[-1] += f" · <span style='color:#8a7a68'>con tarjeta ${con_tarjeta:,.2f}</span>"
                    gana_nota.setText(f"Con tarjeta ${con_tarjeta:,.2f}")
            elif not c.get("tasa") and c["en_linea"]:
                partes.append("<span style='color:#8a7a68'>cashback no configurado</span>")
                gana_nota.setText("Cashback no configurado")
        elif not self._items and not pct_mayoreo and not con_empleada:
            gana_nota.setText("Escanea productos")
        gana_nota.setVisible(bool(gana_nota.text()))
        self._cliente_label.setText("<br>".join(partes))

        puede = self._puede_usar_saldo()
        self._btn_usar_saldo.setEnabled(puede)
        self._btn_usar_saldo.setChecked(self._usar_saldo and puede)
        self._btn_usar_saldo.setText("✓  Usando saldo" if self._btn_usar_saldo.isChecked() else "Usar saldo")
        if c["en_linea"] and not c["por_qr"] and c["disponible"] > 0:
            self._btn_usar_saldo.setToolTip("Para usar saldo escanea el QR del cliente")
        else:
            self._btn_usar_saldo.setToolTip("")
        self._btn_movimientos.setEnabled(bool(c["en_linea"] and c["tiene_monedero"]))
        disponible = c.get("descuento_disponible") if c["en_linea"] else None
        self._btn_descuento_programa.setVisible(bool(disponible))
        if disponible:
            from pos_uniformes.services.fidelizacion import descuento_programa_service as dps

            self._btn_descuento_programa.setText(dps.texto_boton(disponible))
            self._btn_descuento_programa.setChecked(bool(getattr(self, "_usar_descuento_programa", False)))

    def _toggle_usar_saldo(self) -> None:
        self._usar_saldo = bool(self._btn_usar_saldo.isChecked()) and self._puede_usar_saldo()
        self._refresh_totals()

    def _ver_movimientos(self) -> None:
        c = self._cliente
        if not c or not c["id"]:
            return
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services import monedero_service as mon

            with get_session() as session:
                monedero = mon.monedero_de_cliente(session, c["id"])
                filas = [] if monedero is None else [
                    (f.movimiento.created_at, f.etiqueta, Decimal(f.movimiento.monto), f.saldo_contable,
                     f.movimiento.expira_at)
                    for f in mon.historial(session, monedero.id)[:100]
                ]
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Monedero", f"No se pudieron leer los movimientos.\n\n{exc}")
            return
        mostrar_movimientos(self, f"Monedero de {c['nombre']}", filas)

    # ─── Venta con saldo (en línea) ──────────────────────────────────────

    def _cobrar_con_monedero(self, tarjeta: bool, con_copia: bool, *, sin_ticket: bool = False) -> None:
        """Confirma la venta con saldo en la base ANTES de imprimir.

        Si no hay conexión o el saldo ya no alcanza, no se registra nada y el
        carrito queda igual para cobrarlo de otra forma."""
        from pos_uniformes.services import monedero_service as mon

        _s, _d, total = self._compute_totals()
        total = Decimal(str(total)).quantize(Decimal("0.01"))
        canje = self._canje_actual(total)
        c = self._cliente
        if canje <= 0 or not c:
            return
        if not self._en_linea():
            QMessageBox.warning(self, "Monedero", mon.MENSAJE_SIN_CONEXION)
            return
        import uuid as _uuid

        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.libreta_service import registrar_venta_con_monedero

        origen = None
        try:
            from pos_uniformes.services.satellite_identity_service import get_satellite_id

            origen = get_satellite_id()
        except Exception:  # noqa: BLE001
            pass
        # M2: el motor decide UNA vez (con el pago) y la fotografía viaja al
        # servidor, que recalcula antes de cobrar el saldo (T3).
        from datetime import datetime as _dt
        from datetime import timezone as _tz

        # Sin fotografía el servidor no revisa (T3) y el saldo se cobraría a
        # ciegas: antes pasaba en silencio si el motor fallaba o no coincidía
        # con la pantalla. Ahora no se cobra con saldo (revisión de deuda,
        # 2026-11-12); la venta se puede cobrar sin usarlo.
        try:
            entrada, calculo = self._calculo_y_entrada(pago_tarjeta=bool(tarjeta), fecha=_dt.now(_tz.utc))
        except Exception:  # noqa: BLE001 — se avisa abajo
            _logger.exception("Motor de beneficios: no se cobra con saldo sin el cálculo")
            calculo = None
        if calculo is None or calculo.total != total or calculo.saldo_usado != canje:
            if calculo is not None:
                _logger.warning(
                    "Monedero: el motor (%s, saldo %s) no coincide con la pantalla (%s, saldo %s)",
                    calculo.total, calculo.saldo_usado, total, canje,
                )
            QMessageBox.warning(self, "Monedero", MENSAJE_SALDO_SIN_REVISAR)
            return
        from pos_uniformes.services.beneficios_carrito import detalle_por_renglon

        renglones = detalle_por_renglon(self._items, calculo)
        foto = self._fotografia_motor(entrada, calculo)
        items = [
            {"sku": it["sku"], "nombre": it["nombre"], "talla": it["talla"],
             "cantidad": int(it["cantidad"]), "precio": str(it["precio"]),
             **({"linea_uid": it["linea_uid"]} if it.get("linea_uid") else {}),
             **self._marca_promo_para_libreta(it), **self._marca_pct_empleada(it),
             **self._marca_rebaja_para_libreta(it)}
            for it in renglones
        ]
        pct_mayoreo = self._pct_descuento_programa()
        # Identidad de ESTA venta: la misma en cada reintento del mismo cobro.
        # Si la red se cae mientras se confirma, no se sabe si la base alcanzó
        # a guardar; al reintentar con la misma identidad la base devuelve la
        # venta ya registrada en vez de cobrar el saldo otra vez.
        huella = (
            # Sin el monto de saldo: si se reescanea el QR tras un corte, el
            # saldo leído ya trae descontado el canje anterior y cambiaría.
            int(c["id"]), str(total), bool(tarjeta), bool(self._discount_active), str(pct_mayoreo or ""),
            tuple((it["sku"], it["cantidad"], it["precio"], it.get("desc_empleada_pct")) for it in items),
        )
        previa = getattr(self, "_monedero_op", None)
        if previa is None or previa[0] != huella:
            self._monedero_op = (huella, str(_uuid.uuid4()))
        operacion_uuid = self._monedero_op[1]
        confirmando = False
        try:
            with get_session() as session:
                try:
                    _venta, _mov, cashback = registrar_venta_con_monedero(
                        session,
                        employee_code=str(self._employee_code or ""),
                        employee_name=str(self._employee_name or self._employee_code or ""),
                        items=items,
                        monto_total=total,
                        monto_monedero=canje,
                        cliente_id=int(c["id"]),
                        operacion_uuid=operacion_uuid,
                        pago_tarjeta=bool(tarjeta),
                        descuento_empleada=bool(self._discount_active),
                        origen=origen,
                        descuento_programa=pct_mayoreo,
                        calculo=foto,
                        **self._datos_compradora_para_cola(),
                    )
                    cashback_monto = Decimal(cashback.monto) if cashback is not None else _CERO
                    # Regla B: la base con la que el servidor abonó (ya sin la comisión).
                    base_tarjeta = (
                        Decimal(str(cashback.base_calculo))
                        if cashback is not None and tarjeta and getattr(cashback, "base_calculo", None) is not None
                        else None
                    )
                    # Lo que la base cobró de verdad (en un reintento es lo
                    # del primer intento, no lo que hoy calcula la pantalla).
                    canje = Decimal(str(_venta.monto_monedero or 0)).quantize(Decimal("0.01"))
                    confirmando = True
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                # Ya quedó registrada: nada de aquí en adelante la deshace.
                self._monedero_op = None
                try:
                    saldo = mon.resumen_cliente(session, int(c["id"])).disponible
                except Exception:  # noqa: BLE001 — solo es el saldo impreso
                    _logger.exception("Monedero: venta registrada, no se pudo leer el saldo")
                    saldo = None
        except Exception as exc:  # noqa: BLE001
            if confirmando and _es_error_de_red(exc):
                self._avisar_sin_conexion()
                QMessageBox.warning(self, "Monedero", MENSAJE_CONFIRMACION_INCIERTA)
            elif _es_error_de_red(exc):
                self._avisar_sin_conexion()
                QMessageBox.warning(self, "Monedero", mon.MENSAJE_SIN_CONEXION)
            elif type(exc).__name__ == "CalculoCambio":
                # T3: el servidor calculó otro cobro; se ve antes de cobrar.
                self._refrescar_contexto_motor()
                self._refresh_totals()
                QMessageBox.warning(self, "El total cambió", str(exc))
            elif isinstance(exc, (mon.MonederoError, PermissionError)):
                QMessageBox.warning(self, "Monedero", str(exc))
                self._identificar_cliente(c["codigo"], por_qr=c["por_qr"], cliente_id=c["id"])
            else:
                _logger.exception("Monedero: falló la venta con saldo")
                QMessageBox.warning(self, "Monedero", f"No se registró la venta.\n\n{exc}")
            return

        info = {
            **self._cliente_para_ticket(),
            "canje": canje,
            "por_cobrar": total - canje,
            "metodo": "Tarjeta" if tarjeta else "Efectivo",
            "cashback": cashback_monto,
            **({"tasa": cashback.tasa_snapshot, "base_tarjeta": base_tarjeta} if base_tarjeta is not None else {}),
            "saldo": saldo,
        }
        tickets: list[str] = []
        if not sin_ticket:
            # El folio (QR) es la identidad con la que quedó registrada.
            tickets.append(self._build_venta_text(monedero=info, folio=operacion_uuid))
            if self._discount_active:
                tickets.append(self._build_employee_copy_text(terminal_commission=tarjeta))
            elif con_copia:
                tickets.append(self._build_venta_text(
                    store_copy=True, terminal_commission=tarjeta, monedero=info, folio=operacion_uuid
                ))
        # Ya quedó registrada: el carrito se vacía aunque no se imprima.
        self._vaciar_carrito()
        if sin_ticket:
            self._avisar_sin_ticket()
        else:
            from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets

            route_tickets(self, "Ticket de venta", tickets)
        self._scan_input.setFocus()


def mostrar_movimientos(parent, titulo: str, filas: list[tuple]) -> None:
    """Tabla de movimientos: fecha, concepto, monto, saldo, vence."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(titulo)
    dlg.resize(640, 460)
    ly = QVBoxLayout(dlg)
    tabla = QTableWidget(len(filas), 5)
    tabla.setHorizontalHeaderLabels(["Fecha", "Concepto", "Monto", "Saldo", "Vence"])
    tabla.verticalHeader().setVisible(False)
    tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    for i, (cuando, concepto, monto, saldo, vence) in enumerate(filas):
        tabla.setItem(i, 0, QTableWidgetItem(cuando.astimezone().strftime("%d/%m/%Y %H:%M") if cuando else ""))
        tabla.setItem(i, 1, QTableWidgetItem(concepto))
        m = QTableWidgetItem(f"{'+' if monto > 0 else '-'}${abs(monto):,.2f}")
        m.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tabla.setItem(i, 2, m)
        s = QTableWidgetItem(f"${saldo:,.2f}")
        s.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tabla.setItem(i, 3, s)
        tabla.setItem(i, 4, QTableWidgetItem(vence.astimezone().strftime("%d/%m/%Y") if vence and monto > 0 else ""))
    if not filas:
        ly.addWidget(QLabel("Sin movimientos todavía."))
    ly.addWidget(tabla)
    nota = QLabel("El saldo de la columna es el del libro; lo vencido deja de estar disponible en su fecha.")
    nota.setWordWrap(True)
    nota.setStyleSheet("color: #8a7a68; font-size: 12px;")
    ly.addWidget(nota)
    cerrar = QPushButton("Cerrar")
    cerrar.clicked.connect(dlg.accept)
    ly.addWidget(cerrar, alignment=Qt.AlignmentFlag.AlignRight)
    dlg.exec()


# La ficha del cliente en la caja (2026-11-12).
_FICHA_CLIENTE = """
QFrame#clienteBar { background: transparent; border: none; }
QLabel { background: transparent; }
QLabel#fcInicial {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b45a34, stop:1 #8a3a1f);
    color: white; border-radius: 23px; font-size: 19px; font-weight: 800;
}
QLabel#fcNombre { font-size: 18px; font-weight: 800; color: #2c2118; }
QLabel#fcCodigo { font-size: 12px; color: #9a8a7c; letter-spacing: 0.5px; }
QPushButton#fcQuitar {
    background: transparent; color: #9a8a7c; border: none; border-radius: 10px;
    font-size: 13px; font-weight: 700; padding: 4px 8px;
}
QPushButton#fcQuitar:hover { color: #b23a2b; background: #fbeeea; }
QFrame#fcDato { background: #faf6f0; border: 1px solid #f0e6d9; border-radius: 14px; }
QLabel#fcDatoTitulo { font-size: 10px; font-weight: 800; color: #a08c76; letter-spacing: 1.2px; }
QLabel#fcDatoValor { font-size: 22px; font-weight: 900; color: #2c2118; }
QLabel#fcDatoNota { font-size: 12px; color: #9a8a7c; }
QPushButton#fcPrincipal, QPushButton#fcSecundario {
    min-height: 42px; border-radius: 12px; font-size: 14px; font-weight: 800; padding: 0 14px;
}
QPushButton#fcPrincipal { background: white; color: #8a3a1f; border: 1.5px solid #e2cdb6; }
QPushButton#fcPrincipal:checked { background: #8a3a1f; color: white; border-color: #8a3a1f; }
QPushButton#fcSecundario { background: white; color: #5c4d40; border: 1.5px solid #ece2d6; }
QPushButton#fcPrincipal:disabled, QPushButton#fcSecundario:disabled {
    background: #f6f1ea; color: #c2b4a4; border-color: #efe6db;
}
"""
