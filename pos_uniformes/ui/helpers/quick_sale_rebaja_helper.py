"""E7: en el kiosko, las prendas en Oferta o Liquidación (Daniel, 2026-11-11).

Al agregar una prenda se busca si está rebajada: el renglón toma el precio
rebajado y la marca. Las reglas viven en `rebaja_service`; aquí se guarda la
lista de rebajas (se vuelve a leer cada pocos minutos) y se marcan renglones.

Sin conexión se usa la última lista leída; si nunca se leyó, precio normal.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal

from pos_uniformes.services import rebaja_service as reb

_logger = logging.getLogger(__name__)

#: Segundos que dura la lista de rebajas antes de volver a leerla.
VIGENCIA_LISTA = 120


class RebajaVentaMixin:
    """Se mezcla en QuickSaleView."""

    _rebajas: dict | None = None
    _rebajas_leidas_en: float = 0.0

    def _cargar_rebajas(self) -> dict:
        ahora = time.monotonic()
        if self._rebajas is not None and ahora - self._rebajas_leidas_en < VIGENCIA_LISTA:
            return self._rebajas
        try:
            from pos_uniformes.database.connection import get_session

            with get_session() as session:
                self._rebajas = reb.vigentes_por_sku(session)
        except Exception:  # noqa: BLE001
            _logger.warning("Sin conexión para las rebajas: se usa la última lista", exc_info=True)
            if self._rebajas is None:
                self._rebajas = {}
        self._rebajas_leidas_en = ahora
        return self._rebajas

    def _aplicar_rebaja(self, item: dict) -> None:
        """Si la prenda está en Oferta o Liquidación, el renglón lo dice."""
        rebaja = self._cargar_rebajas().get(str(item.get("sku") or "").upper())
        if rebaja is not None:
            reb.aplicar(item, rebaja)

    def _hay_rebajados(self, items: list[dict]) -> bool:
        return any(reb.es_rebajado(it) for it in items)

    def _marca_rebaja_para_libreta(self, it: dict) -> dict:
        return reb.marca_para_libreta(it)

    def _importe_rebajado_carrito(self) -> Decimal:
        return reb.importe_rebajado(getattr(self, "_items", []) or [])
