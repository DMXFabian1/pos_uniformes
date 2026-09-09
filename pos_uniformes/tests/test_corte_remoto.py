"""Corte desde el celular con modificaciones: retirar menos y sin tarjeta."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pos_uniformes.services import corte_remoto_service as crs
from pos_uniformes.services.corte_caja_service import EstadoCaja, ResumenPeriodo

_HASTA = datetime(2026, 9, 9, 23, 30, tzinfo=timezone.utc)


def _estado(efectivo="7480", tarjeta="1200", pagos="0", retiros="0"):
    return EstadoCaja(
        desde=datetime(2026, 9, 9, 1, tzinfo=timezone.utc),
        hasta=_HASTA,
        reactivo=Decimal("1000.00"),
        resumen=ResumenPeriodo(
            11, 23, Decimal(efectivo), Decimal(tarjeta), Decimal("0"), Decimal("0"), Decimal(efectivo)
        ),
        pagos=Decimal(pagos),
        retiros=Decimal(retiros),
    )


class TicketConRetiroTests(unittest.TestCase):
    def _correr(self, *, retirar=None, sin_tarjeta=False, pagos_del_corte=(), retiros="0"):
        estado = _estado(retiros=retiros)
        corte = SimpleNamespace(
            monto_final=Decimal("1000.00") + (retirar or Decimal("6480")),
            reactivo_final=Decimal("1000.00"),
            reactivo_inicial=Decimal("1000.00"),
            periodo_label="09/09", nota=None, created_at=_HASTA,
            retiros_pagos=Decimal("0"), otros_retiros=Decimal(retiros),
            operaciones=11, piezas=23, creado_por="VEND-1",
        )
        auto = SimpleNamespace(corte=corte, estado=estado, pagos=list(pagos_del_corte))
        datos = SimpleNamespace(por_empleada=[], tarjeta=Decimal("0.00"), tarjeta_ops=0, retiros=[])
        with patch.object(crs, "ResultadoCorte", crs.ResultadoCorte), patch(
            "pos_uniformes.services.corte_caja_service.estado_caja", return_value=estado
        ), patch(
            "pos_uniformes.services.corte_caja_service.pagos_que_tocan_hoy", return_value=[]
        ), patch(
            "pos_uniformes.services.corte_caja_service.cerrar_corte_automatico", return_value=auto
        ) as cerrar, patch(
            "pos_uniformes.services.corte_caja_service.operaciones_del_periodo", return_value=[]
        ), patch(
            "pos_uniformes.services.corte_caja_service.datos_ticket_encargado", return_value=datos
        ), patch(
            "pos_uniformes.services.libreta_service.marcar_privadas_del_periodo", return_value=2
        ) as ocultar, patch(
            "pos_uniformes.ui.dialogs.corte_caja_dialog.pagos_previos_del_periodo", return_value=[]
        ), patch(
            "pos_uniformes.ui.dialogs.corte_caja_dialog.texto_ticket_corte_encargado", return_value="TICKET"
        ) as ticket, patch(
            "pos_uniformes.services.trabajos_service.enviar_ticket"
        ):
            resultado = crs.hacer_corte_y_avisar(
                MagicMock(), creado_por="VEND-1", ahora=_HASTA,
                retirar=retirar, sin_tarjeta=sin_tarjeta,
            )
        return resultado, ticket, cerrar, ocultar

    def test_sin_modificaciones_el_papel_lleva_la_venta_real(self) -> None:
        _r, ticket, cerrar, ocultar = self._correr()
        self.assertEqual(ticket.call_args.args[1], Decimal("7480"))
        self.assertIsNone(cerrar.call_args.kwargs["retirar"])
        ocultar.assert_not_called()

    def test_retirar_menos_cuadra_el_papel_con_esa_cifra(self) -> None:
        """venta declarada − pagos − lo que ya salió = lo que se retira."""
        pago = SimpleNamespace(total=Decimal("1304.00"), employee_name="Fanny", employee_code="VEND-4")
        _r, ticket, cerrar, _o = self._correr(
            retirar=Decimal("5000"), pagos_del_corte=[pago], retiros="300",
        )
        self.assertEqual(cerrar.call_args.kwargs["retirar"], Decimal("5000"))
        # 5000 + 1304 (pago) + 300 (ya salió) = 6604
        self.assertEqual(ticket.call_args.args[1], Decimal("6604.00"))

    def test_el_mensaje_le_dice_a_daniel_cuanto_se_queda(self) -> None:
        resultado, _t, _c, _o = self._correr(retirar=Decimal("5000"))
        self.assertIn("El ticket dice venta", resultado.mensaje)
        self.assertIn("te quedas", resultado.mensaje)
        # El mensaje es solo para él: la venta real sigue ahí.
        self.assertIn("7,480.00", resultado.mensaje)

    def test_sintarjeta_oculta_los_cobros_del_periodo(self) -> None:
        resultado, _t, _c, ocultar = self._correr(sin_tarjeta=True)
        ocultar.assert_called_once()
        self.assertEqual(ocultar.call_args.kwargs["creado_por"], "VEND-1")
        self.assertIn("ocultos para tu papá", resultado.mensaje)


if __name__ == "__main__":
    unittest.main()
