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
    """Se mezcla en QuickSaleWidget. Usa de él: _en_linea, build_reprint_ticket,
    _lookup_sku, _aplicar_rebaja, _buscar/_registrar_cliente_identidad,
    _load_business_info, _build_items_block y _OWNER_CODE."""

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

        VentaFolioDialog(
            venta, self,
            al_reimprimir=lambda: self._reimprimir_venta(venta),
            al_cambiar=lambda: self._hacer_cambio(venta),
        ).exec()

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

    # ─── Cambio de prenda (Daniel, 2026-11-12) ───────────────────────────

    def _producto_para_cambio(self, sku: str) -> dict:
        """La prenda escaneada como renglón del carrito (con su rebaja, si va)."""
        snap = self._lookup_sku(sku)
        item = {
            "sku": snap.sku,
            "nombre": getattr(snap, "sale_name", None) or snap.product_name,
            "talla": snap.size_label,
            "color": getattr(snap, "color_label", None),
            "precio": snap.price,
            "cantidad": 1,
        }
        self._aplicar_rebaja(item)
        item.pop("cantidad", None)
        return item

    def _elegir_cliente_para_cambio(self, padre):
        from PyQt6.QtWidgets import QDialog

        from pos_uniformes.ui.dialogs.cliente_rapido_dialog import ClienteRapidoDialog

        dialogo = ClienteRapidoDialog(padre, buscar=self._buscar_clientes_identidad, registrar=self._registrar_cliente_identidad)
        if dialogo.exec() != int(QDialog.DialogCode.Accepted) or dialogo.elegido is None:
            return None
        return int(dialogo.elegido.id), str(dialogo.elegido.nombre)

    def _hacer_cambio(self, venta) -> None:
        from PyQt6.QtWidgets import QMessageBox

        from pos_uniformes.database.connection import get_session
        from pos_uniformes.database.models import LibretaVenta
        from pos_uniformes.services import cambio_service as cs
        from pos_uniformes.ui.dialogs.cambio_dialog import CambioDialog
        from pos_uniformes.ui.dialogs.venta_folio_dialog import datos_de_venta

        if not self._en_linea():
            QMessageBox.information(self, "Cambio", "Sin conexión: el cambio se puede hacer cuando vuelva la red.")
            return
        try:
            with get_session() as session:
                v = session.get(LibretaVenta, int(venta.id))
                renglones = cs.renglones_vendidos(session, v)
                abono, ya = cs.contexto_cashback(session, v)
                dias = cs.dias_desde(v)
                cliente = (int(v.cliente_id), str(v.cliente or "")) if v.cliente_id else None
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Cambio: no se pudo leer la venta %s", getattr(venta, "id", None))
            QMessageBox.warning(self, "Cambio", f"No se pudo leer la venta.\n\n{exc}")
            return
        if not any(r.disponibles for r in renglones):
            QMessageBox.information(self, "Cambio", "De esta venta ya no queda nada por cambiar.")
            return

        hecho: dict = {}

        def registrar(datos: dict) -> str | None:
            try:
                with get_session() as session:
                    r = cs.registrar_cambio(
                        session, venta_id=int(venta.id), regresa=datos["regresa"], lleva=datos["lleva"],
                        employee_code=str(self._employee_code or ""), employee_name=str(self._employee_name or ""),
                        cliente_id=datos["cliente_id"], pago_tarjeta=datos["pago_tarjeta"],
                        autorizo_dueno=datos["autorizo_dueno"], origen=self._origen_satelite(),
                    )
                    session.commit()
                    saldo = None
                    if r.cambio.cliente_id and r.cuenta.a_favor > 0:
                        from pos_uniformes.services import monedero_service as mon

                        saldo = mon.resumen_cliente(session, int(r.cambio.cliente_id)).disponible
                    hecho["texto"] = self._build_cambio_text(r, saldo)
            except cs.CambioError as exc:
                return str(exc)
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Cambio: no se pudo registrar")
                return f"No se pudo registrar el cambio.\n\n{exc}"
            return None

        dialogo = CambioDialog(
            self,
            datos_venta=datos_de_venta(venta),
            renglones=renglones,
            abono=abono,
            ya_quitado=ya,
            dias=dias,
            cliente=cliente,
            buscar_producto=self._producto_para_cambio,
            elegir_cliente=lambda: self._elegir_cliente_para_cambio(dialogo),
            es_dueno=lambda codigo: str(codigo or "").strip().upper() == self._OWNER_CODE,
            registrar=registrar,
        )
        dialogo.exec()
        if hecho.get("texto"):
            from pos_uniformes.ui.helpers.ticket_routing_helper import route_tickets

            route_tickets(self, "Ticket de cambio", [hecho["texto"]])

    def _build_cambio_text(self, r, saldo=None) -> str:
        """El ticket del cambio: qué regresó, qué se llevó y cómo quedó."""
        from datetime import datetime
        from decimal import Decimal

        from pos_uniformes.services.sale_ticket_text_service import encabezado_de_ticket
        from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
            TICKET_CHAR_WIDTH as _TW,
        )
        from pos_uniformes.ui.helpers.ticket_print_layout_helper import (
            tk_bot,
            tk_center,
            tk_field,
            tk_fmt,
            tk_mid,
            tk_row,
            tk_top,
        )

        def renglones(lista):
            return [
                {**it, "nombre": it["nombre"].split(": ", 1)[-1], "precio": Decimal(str(it["precio"])),
                 "cantidad": int(it["cantidad"])}
                for it in lista
            ]

        biz_name, biz_phone, biz_addr = self._load_business_info()
        c = r.cuenta
        lines: list[str] = list(encabezado_de_ticket(biz_name, biz_addr, biz_phone))
        lines.append("Ticket de cambio".center(_TW))
        lines.append(tk_top())
        tk_field("Fecha:", datetime.now().strftime("%d/%m/%Y %H:%M"), lines)
        tk_field("Atendió:", str(self._employee_name or self._employee_code or ""), lines)
        tk_field("Venta:", f"Folio {r.folio_venta}", lines)
        if r.cambio.cliente:
            tk_field("Cliente:", str(r.cambio.cliente), lines)
        lines.append(tk_mid())
        lines.append(tk_center("REGRESA"))
        lines.append(tk_mid())
        self._build_items_block(lines, renglones(r.regresa))
        if r.lleva:
            lines.append(tk_mid())
            lines.append(tk_center("SE LLEVA"))
            lines.append(tk_mid())
            self._build_items_block(lines, renglones(r.lleva))
        lines.append(tk_mid())
        lines.append(tk_row("Regresa:", f"${tk_fmt(c.valor_regresa)}"))
        if c.cashback_quitado > 0:
            lines.append(tk_row("Monedero ganado:", f"-${tk_fmt(c.cashback_quitado)}"))
        lines.append(tk_row("Se lleva:", f"${tk_fmt(c.valor_lleva)}"))
        lines.append(tk_mid())
        if c.a_pagar > 0:
            forma = "tarjeta" if r.cambio.pago_tarjeta else "efectivo"
            lines.append(tk_row(f"PAGA ({forma}):", f"${tk_fmt(c.a_pagar)}"))
        elif c.a_favor > 0:
            lines.append(tk_row("A FAVOR EN MONEDERO:", f"${tk_fmt(c.a_favor)}"))
            if saldo is not None:
                lines.append(tk_row("Saldo del Monedero:", f"${tk_fmt(saldo)}"))
            # Lo a favor entra al Monedero y vence como cualquier abono: se
            # avisa con la misma leyenda de la venta (Daniel, 2026-11-12:
            # «solucionemos estos»).
            from pos_uniformes.ui.helpers.quick_sale_monedero_helper import lineas_vigencia_monedero

            lines.extend(lineas_vigencia_monedero())
        else:
            lines.append(tk_center("Queda parejo"))
        lines.append(tk_bot())
        lines.append("")
        lines.append("Gracias por su preferencia".center(_TW))
        return "\n".join(lines)
