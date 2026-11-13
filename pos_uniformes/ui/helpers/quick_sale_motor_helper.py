"""M2: el kiosko cobra con el motor de beneficios.

Un solo lugar arma la entrada del motor con el estado del kiosko (carrito,
cliente, Mayorista, quién compra, saldo, tarjeta) y pide el cálculo. Los
totales, el neto con comisión (T4), los renglones de la Libreta y la
fotografía (T2) salen de aquí; ninguna otra parte del kiosko calcula
descuentos por su cuenta.

La reimpresión de una venta de antes (sin fotografía) sigue con el cálculo
viejo: es un dato histórico, no se vuelve a decidir con las reglas de hoy.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

_logger = logging.getLogger(__name__)
_CERO = Decimal("0.00")


def texto_si_el_motor_no_responde(calcular) -> str | None:
    """None si `calcular()` funciona; si no, qué decirle a la empleada."""
    from pos_uniformes.services.beneficios.contrato import EntradaInvalida

    try:
        calcular()
    except EntradaInvalida as exc:
        _logger.warning("Motor de beneficios: carrito rechazado (%s); se cobra con el cálculo anterior", exc)
        motivo = f"\n\nMotivo: {exc}"
    except Exception:  # noqa: BLE001 — se avisa; el mostrador no se detiene
        _logger.exception("Motor de beneficios: no se pudo calcular; se cobra con el cálculo anterior")
        motivo = ""
    else:
        return None
    return (
        "Las reglas de descuento no pudieron calcular esta venta. Se cobra con el cálculo de antes: "
        "revisa que el total sea correcto y avísale a Daniel." + motivo
    )


class MotorVentaMixin:
    """Se mezcla en QuickSaleWidget. Usa de él: _items, _cliente,
    _usar_descuento_programa, _descuento_programa_fijo, _discount_active,
    _compradora, _usar_saldo, _puede_usar_saldo, _en_linea, _employee_code,
    _poner_categorias."""

    #: Mientras se reimprime una venta de antes: el cálculo viejo.
    _reimpresion_legada = False
    #: Mientras se reimprime una venta con fotografía: su cálculo guardado.
    _calculo_fijo = None

    def _entrada_motor(self, items: list[dict] | None = None, *, pago_tarjeta: bool = False, fecha=None):
        from pos_uniformes.services.beneficios_carrito import entrada_desde_carrito

        items = self._items if items is None else items
        compradora = getattr(self, "_compradora", None)
        descuento = bool(getattr(self, "_discount_active", False))
        if descuento and compradora is not None and compradora.tiene_nivel:
            # Uniforme o no (máximo de 10 % en uniforme): solo importa con nivel.
            self._poner_categorias(items)
        cliente = getattr(self, "_cliente", None)
        usar_saldo = bool(getattr(self, "_usar_saldo", False)) and self._puede_usar_saldo() and bool(items)
        return entrada_desde_carrito(
            items,
            fecha_venta=fecha or datetime.now(timezone.utc),
            en_linea=self._en_linea(),
            cliente=cliente,
            usar_descuento_programa=bool(getattr(self, "_usar_descuento_programa", False)),
            pct_mayoreo_fijo=getattr(self, "_descuento_programa_fijo", None),
            descuento_empleada=descuento,
            compradora=compradora,
            usar_saldo=usar_saldo,
            saldo_disponible=(cliente or {}).get("disponible") or _CERO,
            pago_tarjeta=pago_tarjeta,
            vendedora=getattr(self, "_employee_code", None),
        )

    def _calculo_motor(self, items: list[dict] | None = None, *, pago_tarjeta: bool = False, fecha=None):
        from pos_uniformes.services.beneficios.motor import calcular

        return calcular(self._entrada_motor(items, pago_tarjeta=pago_tarjeta, fecha=fecha))

    def _calculo_y_entrada(self, *, pago_tarjeta: bool = False, fecha=None):
        from pos_uniformes.services.beneficios.motor import calcular

        entrada = self._entrada_motor(pago_tarjeta=pago_tarjeta, fecha=fecha)
        return entrada, calcular(entrada)

    def _avisar_si_el_motor_no_responde(self) -> None:
        """Antes de cobrar: si el motor no puede calcular este carrito, la
        empleada lo sabe. Antes se cobraba con el cálculo de respaldo (otro
        tope de empleada, otro reparto) y solo quedaba en el log (revisión de
        deuda, 2026-11-12). No detiene la venta: el mostrador no se para."""
        if self._calculo_fijo is not None or self._reimpresion_legada:
            return
        texto = texto_si_el_motor_no_responde(self._calculo_motor)
        if texto:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Cálculo de respaldo", texto)

    def _fotografia_motor(self, entrada, calculo) -> dict:
        from pos_uniformes.services.beneficios.fotografia import fotografia

        return fotografia(entrada, calculo)

    # ─── T3: revisar con el servidor antes de cobrar ─────────────────────

    def _refrescar_contexto_motor(self) -> bool:
        """Vuelve a leer de la base al cliente y a quien compra, sin tocar lo
        que eligió la empleada (usar saldo, descuento de Mayorista). False si
        no se pudo (sin conexión)."""
        if not self._en_linea():
            return False
        c = getattr(self, "_cliente", None)
        compradora = getattr(self, "_compradora", None)
        if not (c and c.get("id")) and compradora is None:
            return True
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services import incentivo_empleada_service as inc
            from pos_uniformes.services import monedero_service as mon

            with get_session() as session:
                if c and c.get("id"):
                    r = mon.resumen_cliente(session, int(c["id"]))
                    c.update(
                        tiene_monedero=r.tiene_monedero, estado=r.estado, disponible=r.disponible,
                        tasa=r.tasa, descuento_disponible=r.descuento_disponible, programa=r.programa,
                    )
                if compradora is not None:
                    self._compradora = inc.estado_compradora(session, compradora.codigo, compradora.nombre)
        except Exception:  # noqa: BLE001 — sin conexión se cobra con lo que hay
            _logger.warning("Motor: no se pudo revisar con el servidor antes de cobrar", exc_info=True)
            return False
        return True

    def _revisar_con_servidor(self) -> bool:
        """T3: antes de cobrar, lo que el kiosko tenía leído se revisa con la
        base. Si el total cambia, la empleada lo ve y vuelve a cobrar: el
        total nunca cambia en silencio. True = se puede cobrar."""
        from PyQt6.QtWidgets import QMessageBox

        if not self._items:
            return True
        antes = self._compute_totals()
        if not self._refrescar_contexto_motor():
            return True
        despues = self._compute_totals()
        self._refresh_totals()
        if despues[2] == antes[2]:
            return True
        QMessageBox.information(
            self,
            "El total cambió",
            "Al revisarlo con el servidor cambió el total (el programa o el saldo del cliente, "
            f"o el tope de quien compra).\n\nAntes: ${antes[2]:,.2f}\nAhora: ${despues[2]:,.2f}\n\n"
            "Revisa el total en pantalla y vuelve a cobrar.",
        )
        return False
