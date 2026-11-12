"""E6: en el kiosko, quién compra con el descuento de empleada (Daniel, 2026-11-10).

Después de que el dueño autoriza el descuento, la empleada que compra
escanea SU gafete (desde 2026-11-12; antes se elegía de una lista y se podía
elegir a otra con más descuento). Con eso cada renglón lleva su % (su nivel del mes, o el 5 % base si ya
pasó su tope o es promo 3pz). Las reglas viven en `incentivo_empleada_service`;
aquí solo se pregunta, se guarda el estado y se marcan los renglones.

Sin conexión, o si el dueño elige «Otra persona», queda el 5 % de siempre.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from pos_uniformes.services import incentivo_empleada_service as inc

_logger = logging.getLogger(__name__)



def compradora_por_gafete(codigo: str, empleadas, *, dueno: str = "VEND-1"):
    """(código, nombre) de la empleada de ese gafete, o el texto de por qué no."""
    codigo = str(codigo or "").strip().upper()
    if not codigo:
        return "Escanea el gafete de la empleada que compra."
    if codigo == str(dueno).upper():
        return "Ese es el gafete del dueño: que escanee el suyo la empleada que compra."
    for c, nombre in empleadas:
        if str(c).upper() == codigo:
            return str(c), str(nombre)
    return f"El gafete {codigo} no es de una empleada activa."


class CompradoraEmpleadaMixin:
    """Se mezcla en QuickSaleView. Estado: `self._compradora` (EstadoCompradora o None)."""

    _compradora = None

    # ─── Discreto en la caja (2026-11-12) ─────────────────────────────
    #
    # Daniel: «no me gustaría que las personas ajenas vean que las empleadas
    # tienen su descuento propio». Se activa desde el menú «⋯» de la caja y,
    # mientras está puesto, solo se ve una ficha «🔒 Precio especial» en el
    # total, sin nombre ni porcentaje. Quien cobra la toca para ver quién
    # compra y con cuánto, y desde ahí lo quita.

    def _build_compradora_card(self) -> None:
        self._chip_precio_especial = QPushButton("🔒  Precio especial")
        self._chip_precio_especial.setObjectName("chipPrecioEspecial")
        self._chip_precio_especial.setToolTip("Ver o quitar el precio especial")
        self._chip_precio_especial.setAutoDefault(False)
        self._chip_precio_especial.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chip_precio_especial.clicked.connect(self._ver_precio_especial)
        self._chip_precio_especial.setVisible(False)
        # El detalle (quién y con cuánto) se arma siempre, pero solo se muestra
        # dentro del diálogo de quien cobra: el contenedor nunca sale a pantalla.
        self._compradora_guardado = QWidget()
        self._compradora_texto = QLabel("", self._compradora_guardado)
        self._compradora_texto.setTextFormat(Qt.TextFormat.RichText)
        self._compradora_texto.setWordWrap(True)
        self._compradora_texto.setVisible(False)
        self._pintar_compradora_card()

    def _pintar_compradora_card(self) -> None:
        texto = getattr(self, "_compradora_texto", None)
        if texto is None:
            return
        activo = bool(getattr(self, "_discount_active", False))
        self._chip_precio_especial.setVisible(activo)
        accion = getattr(self, "_accion_precio_especial", None)
        if accion is not None:
            accion.setText("🔓  Quitar precio especial" if activo else "🔒  Precio especial")
        if not activo:
            texto.setVisible(False)
            return
        c = self._compradora
        if c is None:
            texto.setText(
                f"Con <b>{inc.fmt_pct(inc.PCT_BASE)}</b> · sin compradora"
                "<br><span style='color:#9a8a7c'>Otra persona, o sin conexión para saber quién.</span>"
            )
        else:
            detalle = inc.fmt_nivel(c.porcentaje) if c.tiene_nivel else inc.fmt_pct(inc.PCT_BASE)
            renglones = [
                f"Compra <b style='font-size:20px; color:#6b1f3a'>{c.nombre}</b>",
                f"Con <b>{detalle}</b>",
            ]
            if c.tiene_nivel and c.restante is not None:
                renglones.append(
                    f"<span style='color:#9a8a7c'>Le quedan ${c.restante:,.2f} este mes con su nivel; "
                    f"lo demás va con {inc.fmt_pct(inc.PCT_BASE)}.</span>"
                )
            texto.setText("<br>".join(renglones))
        texto.setVisible(True)

    def _ver_precio_especial(self) -> None:
        """Lo que solo ve quien cobra: quién compra, con cuánto y quitarlo."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Precio especial")
        dlg.setFixedWidth(400)
        dlg.setStyleSheet(
            "QDialog { background: #fbf7f1; }"
            "QLabel { background: transparent; color: #3d2e22; font-size: 15px; }"
            "QPushButton { min-height: 44px; border-radius: 12px; font-size: 15px; font-weight: 800; padding: 0 16px; }"
            "QPushButton#quitar { background: white; color: #b23a2b; border: 1.5px solid #e6c9c3; }"
            "QPushButton#listo { background: #6b1f3a; color: white; border: none; }"
        )
        ly = QVBoxLayout(dlg)
        ly.setContentsMargins(24, 20, 24, 20)
        ly.setSpacing(14)
        titulo = QLabel("🔒  PRECIO ESPECIAL")
        titulo.setStyleSheet("color: #8a7a68; font-size: 12px; font-weight: 800; letter-spacing: 1.5px;")
        ly.addWidget(titulo)
        detalle = QLabel(self._compradora_texto.text())
        detalle.setTextFormat(Qt.TextFormat.RichText)
        detalle.setWordWrap(True)
        ly.addWidget(detalle)
        botones = QHBoxLayout()
        quitar = QPushButton("Quitar precio especial")
        quitar.setObjectName("quitar")
        quitar.setAutoDefault(False)
        listo = QPushButton("Listo")
        listo.setObjectName("listo")
        botones.addWidget(quitar, 1)
        botones.addWidget(listo, 1)
        ly.addLayout(botones)
        quitar.clicked.connect(lambda: dlg.done(2))
        listo.clicked.connect(dlg.accept)
        self._dialogo_precio_especial = dlg
        if dlg.exec() == 2 and getattr(self, "_discount_active", False):
            self._discount_check.click()

    # ─── Elegir ─────────────────────────────────────────────────────────

    def _cargar_empleadas_compradoras(self) -> list[tuple[str, str]] | None:
        """None = sin conexión."""
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                return inc.empleadas_activas(session)
        except Exception:  # noqa: BLE001
            _logger.warning("Sin conexión para la lista de empleadas", exc_info=True)
            return None

    def _estado_de_compradora(self, codigo: str, nombre: str):
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                return inc.estado_compradora(session, codigo, nombre)
        except Exception:  # noqa: BLE001
            _logger.warning("No se pudo leer el nivel de %s", codigo, exc_info=True)
            return None

    def _elegir_compradora(self) -> None:
        """Ella escanea SU gafete (Daniel, 2026-11-12): con una lista se podía
        elegir a otra empleada con más descuento. Sin gafete, «Otra persona»
        o sin conexión: el 5 % de siempre, sin compradora."""
        self._compradora = None
        empleadas = self._cargar_empleadas_compradoras()
        if not empleadas:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("¿Quién compra?")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(
            "QDialog { background: #f4ede2; }"
            "QLabel { color: #2c2a27; font-size: 15px; background: transparent; }"
            "QLineEdit { font-size: 18px; padding: 12px 16px; border: 2px solid #ddd0c0;"
            " border-radius: 12px; background: white; color: #2c2a27; }"
            "QLineEdit:focus { border-color: #a84f2d; }"
            "QPushButton { background: #f8f2e9; color: #73341c; border: 1.5px solid #ddd0c0;"
            " border-radius: 12px; min-height: 44px; padding: 0 16px; font-size: 15px; font-weight: 800; }"
        )
        ly = QVBoxLayout(dlg)
        ly.setContentsMargins(24, 20, 24, 20)
        ly.setSpacing(10)
        titulo = QLabel("🏷  ¿Quién compra?")
        titulo.setStyleSheet("font-size: 22px; font-weight: 900; color: #73341c;")
        ly.addWidget(titulo)
        ayuda = QLabel("Que escanee <b>su</b> gafete quien compra.")
        ayuda.setWordWrap(True)
        ly.addWidget(ayuda)
        entrada = QLineEdit()
        entrada.setPlaceholderText("Escanea su gafete…")
        entrada.setEchoMode(QLineEdit.EchoMode.Password)
        ly.addWidget(entrada)
        error = QLabel("")
        error.setStyleSheet("color: #a12; font-size: 14px; font-weight: 700;")
        error.setWordWrap(True)
        error.setVisible(False)
        ly.addWidget(error)
        otra = QPushButton(f"Otra persona ({inc.fmt_pct(inc.PCT_BASE)})")
        otra.setAutoDefault(False)
        otra.clicked.connect(dlg.reject)
        ly.addWidget(otra)
        elegida: dict = {}

        def _escanear() -> None:
            quien = compradora_por_gafete(self._clean_scanned_code(entrada.text()), empleadas, dueno=self._OWNER_CODE)
            entrada.clear()
            if isinstance(quien, str):
                error.setText(quien)
                error.setVisible(True)
                return
            elegida["quien"] = quien
            dlg.accept()

        entrada.returnPressed.connect(_escanear)
        self._dialogo_compradora = dlg  # para las pruebas
        self._dialogo_compradora_entrada = entrada
        self._dialogo_compradora_error = error
        entrada.setFocus()
        if dlg.exec() != QDialog.DialogCode.Accepted or "quien" not in elegida:
            return
        codigo, nombre = elegida["quien"]
        self._compradora = self._estado_de_compradora(codigo, nombre)
    def _quitar_compradora(self) -> None:
        self._compradora = None
        for it in getattr(self, "_items", []) or []:
            it.pop(inc.LLAVE_PCT, None)

    # ─── Renglones ──────────────────────────────────────────────────────

    def _asignar_pct_empleada(self, items: list[dict]) -> None:
        """Marca el % de cada renglón según quién compra.

        Sin descuento se quitan las marcas. Sin compradora (5 % de siempre o
        reimpresión) se dejan como estén."""
        if not getattr(self, "_discount_active", False):
            for it in items:
                it.pop(inc.LLAVE_PCT, None)
            return
        c = self._compradora
        if c is None:
            return
        if not c.tiene_nivel:
            # Sin nivel: el 5 % de siempre, calculado igual que antes.
            for it in items:
                it.pop(inc.LLAVE_PCT, None)
            return
        self._poner_categorias(items)
        pcts = inc.repartir(items, pct_nivel=c.porcentaje, restante=c.restante)
        for it, pct in zip(items, pcts):
            it[inc.LLAVE_PCT] = pct

    def _poner_categorias(self, items: list[dict]) -> None:
        """La categoría de cada renglón (uniforme o no). Se pregunta a la base
        una vez por SKU; sin conexión el renglón cuenta como uniforme."""
        cache = self.__dict__.setdefault("_categorias_sku", {})
        faltan = {str(it.get("sku") or "") for it in items if inc.LLAVE_CATEGORIA not in it} - set(cache)
        faltan.discard("")
        if faltan:
            try:
                from pos_uniformes.database.connection import get_session

                with get_session() as session:
                    encontradas = inc.categorias_por_sku(session, faltan)
            except Exception:  # noqa: BLE001
                _logger.warning("Sin conexión para las categorías: cuentan como uniforme", exc_info=True)
                encontradas = {}
            for sku in faltan:  # lo que no se encontró queda como uniforme (no se vuelve a preguntar)
                cache[sku] = encontradas.get(sku, "")
        for it in items:
            if inc.LLAVE_CATEGORIA not in it and cache.get(str(it.get("sku") or "")):
                it[inc.LLAVE_CATEGORIA] = cache[str(it.get("sku") or "")]

    def _hay_pct_por_renglon(self, items: list[dict]) -> bool:
        return any(it.get(inc.LLAVE_PCT) not in (None, "") for it in items)

    def _marca_pct_empleada(self, it: dict) -> dict:
        valor = it.get(inc.LLAVE_PCT)
        if not getattr(self, "_discount_active", False) or valor in (None, ""):
            return {}
        return {inc.LLAVE_PCT: str(valor)}

    def _datos_compradora_para_cola(self) -> dict:
        c = self._compradora
        if c is None or not getattr(self, "_discount_active", False):
            return {}
        return {"compradora_code": c.codigo}

    def _texto_compradora(self) -> str:
        c = self._compradora
        return c.texto() if c is not None and getattr(self, "_discount_active", False) else ""
