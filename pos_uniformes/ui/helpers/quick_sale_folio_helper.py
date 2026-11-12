"""Escanear el QR de un ticket abre esa venta (Daniel, 2026-11-12).

«El QR era para identificar ventas, así si necesito hacer un cambio o
rastrear una venta.» En la caja de escaneo de Venta rápida, el QR del ticket
(o el folio corto tecleado, `3F9A-12BC`) muestra la venta: cuándo, quién la
hizo, el cliente, lo que se llevó y cómo pagó, con un botón para reimprimir
el ticket. No cambia nada de la venta.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

_logger = logging.getLogger(__name__)

#: Lo que se copia de la venta para mostrarla fuera de la sesión de la base.
_CAMPOS = (
    "id", "tipo", "detalle", "cliente", "employee_name", "employee_code", "descuento_empleada",
    "created_at", "monto_total", "monto_monedero", "pago_tarjeta", "descuento_programa",
    "calculo", "operacion_uuid", "piezas",
)


class FolioVentaMixin:
    """Se mezcla en QuickSaleWidget. Usa de él: _en_linea, build_reprint_ticket."""

    def _es_folio_venta(self, raw: str) -> bool:
        from pos_uniformes.services.folio_venta_service import es_folio

        return es_folio(raw)

    def _buscar_venta_por_folio(self, raw: str):
        """La venta como datos sueltos (fuera de la sesión), o None."""
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.folio_venta_service import buscar_venta

        with get_session() as session:
            v = buscar_venta(session, raw)
            if v is None:
                return None
            return SimpleNamespace(**{c: getattr(v, c, None) for c in _CAMPOS})

    def _abrir_venta_por_folio(self, raw: str) -> None:
        from PyQt6.QtWidgets import QMessageBox

        if not self._en_linea():
            QMessageBox.information(self, "Folio de venta", "Sin conexión: la venta se puede buscar cuando vuelva la red.")
            return
        try:
            venta = self._buscar_venta_por_folio(raw)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Folio: no se pudo buscar la venta")
            QMessageBox.warning(self, "Folio de venta", f"No se pudo buscar la venta.\n\n{exc}")
            return
        if venta is None:
            QMessageBox.information(
                self, "Folio de venta",
                "No encontré esa venta. Si se hizo hace un momento sin conexión, "
                "todavía no sube: inténtalo en un rato.",
            )
            return
        from pos_uniformes.ui.dialogs.venta_folio_dialog import VentaFolioDialog

        VentaFolioDialog(venta, self, al_reimprimir=lambda: self._reimprimir_venta(venta)).exec()

    def _reimprimir_venta(self, v) -> None:
        from PyQt6.QtWidgets import QMessageBox

        texto = self.build_reprint_ticket(
            tipo=str(v.tipo),
            detalle=list(v.detalle or []),
            cliente=v.cliente,
            employee_name=str(v.employee_name or v.employee_code or ""),
            descuento_empleada=bool(v.descuento_empleada),
            created_at=v.created_at,
            monto_total=v.monto_total,
            monto_monedero=v.monto_monedero,
            pago_tarjeta=bool(v.pago_tarjeta),
            descuento_programa=v.descuento_programa,
            calculo=v.calculo,
            operacion_uuid=v.operacion_uuid,
        )
        if not texto:
            QMessageBox.information(self, "Sin ticket", "Los abonos no generan ticket para reimprimir.")
            return
        from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets

        route_tickets(self, "Reimpresión de ticket", [texto])
