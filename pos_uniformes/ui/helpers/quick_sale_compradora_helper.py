"""E6: en el kiosko, quién compra con el descuento de empleada (Daniel, 2026-11-10).

Después de que el dueño autoriza el descuento se elige a la empleada que
compra. Con eso cada renglón lleva su % (su nivel del mes, o el 5 % base si ya
pasó su tope o es promo 3pz). Las reglas viven en `incentivo_empleada_service`;
aquí solo se pregunta, se guarda el estado y se marcan los renglones.

Sin conexión, o si el dueño elige «Otra persona», queda el 5 % de siempre.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout

from pos_uniformes.services import incentivo_empleada_service as inc

_logger = logging.getLogger(__name__)

_OTRA = "__otra__"


class CompradoraEmpleadaMixin:
    """Se mezcla en QuickSaleView. Estado: `self._compradora` (EstadoCompradora o None)."""

    _compradora = None

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
        """Pregunta quién compra. Cualquier salida sin elegir deja el 5 % base."""
        self._compradora = None
        empleadas = self._cargar_empleadas_compradoras()
        if not empleadas:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("¿Quién compra?")
        dlg.setMinimumWidth(360)
        ly = QVBoxLayout(dlg)
        ly.addWidget(QLabel("¿Qué empleada compra? Su descuento depende de lo que vendió el mes pasado."))
        lista = QListWidget()
        for codigo, nombre in empleadas:
            item = QListWidgetItem(nombre)
            item.setData(Qt.ItemDataRole.UserRole, codigo)
            lista.addItem(item)
        otra = QListWidgetItem(f"Otra persona ({inc.fmt_pct(inc.PCT_BASE)})")
        otra.setData(Qt.ItemDataRole.UserRole, _OTRA)
        lista.addItem(otra)
        lista.itemDoubleClicked.connect(lambda _i: dlg.accept())
        ly.addWidget(lista)
        boton = QPushButton("Elegir")
        boton.clicked.connect(dlg.accept)
        ly.addWidget(boton)
        lista.setCurrentRow(0)
        self._dialogo_compradora = dlg  # para las pruebas
        if dlg.exec() != QDialog.DialogCode.Accepted or lista.currentItem() is None:
            return
        codigo = lista.currentItem().data(Qt.ItemDataRole.UserRole)
        if codigo == _OTRA:
            return
        self._compradora = self._estado_de_compradora(str(codigo), lista.currentItem().text())

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
