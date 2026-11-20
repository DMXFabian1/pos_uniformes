"""El corte recuerda el pago del dueño (Daniel, 2026-11-19).

Sale en TODOS los cortes (dueño, encargado, automático/celular y su ticket),
NO cambia el esperado ni ninguna cifra, y sin cuenta activa no sale nada.
"""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import EmpleadaPago, LibretaCorte
from pos_uniformes.services import pago_dueno_service as pd
from pos_uniformes.ui.dialogs import corte_caja_dialog as ccd
from pos_uniformes.ui.helpers.ticket_print_layout_helper import TICKET_CHAR_WIDTH
from tests.test_corte_pagos_de_hoy import HOY, _CorteBase

app = QApplication.instance() or QApplication([])

LINEAS = [
    "PAGO DE DANIEL (no sale del cajón)",
    "  3 de 4 · sáb 21-nov · $2,500",
    "  Toca en 2 días · Último pago: 19-nov",
    "  Atrasado: 2 de 4 (14-nov) · $2,500",
    "  Días a favor: 0",
]


def _corte(**kw):
    datos = dict(
        monto_final=Decimal("7480.00"), reactivo_final=Decimal("1000.00"), reactivo_inicial=Decimal("1000.00"),
        periodo_label="19/11", nota=None, created_at=None, retiros_pagos=Decimal("0"), otros_retiros=Decimal("0"),
        creado_por="VEND-1", monto_esperado=Decimal("7480.00"), hasta=None, desde=None,
    )
    datos.update(kw)
    return SimpleNamespace(**datos)


class TicketTests(unittest.TestCase):
    def test_el_ticket_del_corte_lleva_el_recordatorio(self) -> None:
        texto = ccd.texto_ticket_corte_encargado(_corte(), Decimal("6480"), [], pago_dueno=LINEAS)
        self.assertIn("PAGO DE DANIEL (no sale del cajón)", texto)
        self.assertIn("3 de 4 · sáb 21-nov · $2,500", texto)
        self.assertIn("Último pago: 19-nov", texto)
        self.assertIn("Atrasado: 2 de 4 (14-nov) · $2,500", texto)
        self.assertIn("Días a favor: 0", texto)
        # Va al final, después de la cuenta.
        self.assertGreater(texto.index("PAGO DE DANIEL"), texto.index("SACAR"))

    def test_cabe_en_el_papel_y_en_cp850(self) -> None:
        for texto in (
            ccd.texto_ticket_corte_encargado(_corte(), Decimal("6480"), [], pago_dueno=LINEAS),
            ccd.texto_ticket_corte(_corte(), venta_efectivo=Decimal("6480"), pago_dueno=LINEAS),
        ):
            for renglon in texto.splitlines():
                self.assertLessEqual(len(renglon), TICKET_CHAR_WIDTH, renglon)
            texto.encode("cp850")          # la térmica imprime en CP850: nada se vuelve «?»
        # «Toca en 2 días · Último pago: 19-nov» no cabe en 34: se parte por el «·».
        texto = ccd.texto_ticket_corte_encargado(_corte(), Decimal("6480"), [], pago_dueno=LINEAS)
        self.assertIn("│ Toca en 2 días", texto)
        self.assertIn("│ Último pago: 19-nov", texto)

    def test_sin_cuenta_el_ticket_queda_igual(self) -> None:
        # La hora de impresión, fija: así los tres tickets se pueden comparar.
        fijo = datetime(2026, 11, 19, 20, 0)
        with patch("datetime.datetime", wraps=datetime) as dt:
            dt.now.return_value = fijo
            antes = ccd.texto_ticket_corte_encargado(_corte(), Decimal("6480"), [])
            vacio = ccd.texto_ticket_corte_encargado(_corte(), Decimal("6480"), [], pago_dueno=[])
            con = ccd.texto_ticket_corte_encargado(_corte(), Decimal("6480"), [], pago_dueno=LINEAS)
            dueno_antes = ccd.texto_ticket_corte(_corte(), venta_efectivo=Decimal("6480"))
            dueno_vacio = ccd.texto_ticket_corte(_corte(), venta_efectivo=Decimal("6480"), pago_dueno=[])
        self.assertEqual(antes, vacio)
        self.assertEqual(dueno_antes, dueno_vacio)
        self.assertNotIn("PAGO DE", antes)
        # Con el recordatorio, todo lo de antes sigue igual y en su lugar: solo se agrega al final.
        self.assertTrue(con.startswith(antes))

    def test_ticket_completo_del_dueno(self) -> None:
        texto = ccd.texto_ticket_corte(_corte(), venta_efectivo=Decimal("6480"), pago_dueno=LINEAS)
        self.assertIn("PAGO DE DANIEL", texto)
        self.assertTrue(texto.rstrip().endswith("Corte generado por la Libreta.".center(TICKET_CHAR_WIDTH).rstrip()))

    def test_previa_del_encargado(self) -> None:
        estado = SimpleNamespace(
            resumen=SimpleNamespace(efectivo=Decimal("5000.00")), entradas=Decimal("0"),
            pagos=Decimal("0"), total_retiros=Decimal("0"), reactivo=Decimal("1000.00"),
        )
        sin = ccd.texto_previa_corte_encargado(estado, [])
        con = ccd.texto_previa_corte_encargado(estado, [], LINEAS)
        self.assertNotIn("PAGO DE", sin)
        self.assertTrue(con.startswith(sin))
        self.assertIn("SE RETIRA: $5,000.00", con)            # la cifra no cambia
        self.assertIn("PAGO DE DANIEL (no sale del cajón)\n3 de 4", con)


class LineasPagoDuenoTests(unittest.TestCase):
    def test_base_sin_tablas_o_rota_da_nada(self) -> None:
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with Session(engine) as s:
            self.assertEqual(ccd.lineas_pago_dueno(s, datetime(2026, 11, 19, 20, 0)), [])
        self.assertEqual(ccd.lineas_pago_dueno(MagicMock()), [])
        with patch("pos_uniformes.services.pago_dueno_service.lineas_recordatorio_corte", side_effect=RuntimeError):
            self.assertEqual(ccd.lineas_pago_dueno(MagicMock()), [])

    def test_la_fecha_del_corte_es_la_local(self) -> None:
        with patch("pos_uniformes.services.pago_dueno_service.lineas_recordatorio_corte", return_value=["x"]) as f:
            ccd.lineas_pago_dueno("s", datetime(2026, 11, 19, 20, 0))
        self.assertEqual(f.call_args.args, ("s", date(2026, 11, 19)))


class CorteConLaCuentaTests(_CorteBase):
    """El corte real (SQLite): con la cuenta activa sale el recordatorio en la
    ventana y en el ticket, y el esperado es el mismo que sin ella."""

    def _corte(self, *, configurar: bool):
        if configurar:
            pd.guardar_config(self.s, fecha_inicio=HOY)
        tickets: list[str] = []
        vista = {}

        def _mira(dlg):
            vista["pago_dueno"] = dlg.pago_dueno.text() if dlg.pago_dueno is not None else None
            return QDialog.DialogCode.Accepted

        with patch("pos_uniformes.ui.dialogs.corte_caja_dialog.QDialog.exec", _mira), \
                patch("pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets",
                      lambda _p, _t, textos, **k: tickets.extend(textos)):
            corte = ccd.hacer_corte_caja(None, creado_por="VEND-1")
        self.assertIsNotNone(corte)
        return self.s.scalars(select(LibretaCorte)).one(), tickets, vista

    def _esperado(self) -> Decimal:
        pagos = sum((p.total for p in self.s.scalars(select(EmpleadaPago)).all()), Decimal("0.00"))
        return Decimal("11160.00") + Decimal("5000.00") - pagos

    def test_sin_cuenta_no_sale_nada(self) -> None:
        corte, tickets, vista = self._corte(configurar=False)
        self.assertIsNone(vista["pago_dueno"])
        self.assertNotIn("PAGO DE", tickets[0])
        self.assertEqual(corte.monto_esperado, self._esperado())

    def test_con_cuenta_sale_y_el_esperado_no_cambia(self) -> None:
        corte, tickets, vista = self._corte(configurar=True)
        self.assertIn("Último pago: ninguno", vista["pago_dueno"])
        self.assertIn("Días a favor: 0", vista["pago_dueno"])
        self.assertIn("PAGO DE DANIEL (no sale del cajón)", tickets[0])
        self.assertEqual(corte.monto_esperado, self._esperado())
        self.assertEqual(corte.monto_final, corte.monto_esperado)
        # Nada de la cuenta del dueño entró como pago de empleada.
        self.assertNotIn("VEND-1", [p.employee_code for p in self.s.scalars(select(EmpleadaPago)).all()])

    def test_el_corte_del_encargado_tambien(self) -> None:
        pd.guardar_config(self.s, fecha_inicio=HOY)
        with patch("pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets", lambda *a, **k: None):
            resultado = ccd.hacer_corte_automatico(None, creado_por="ENC-1")
        self.assertIsNotNone(resultado)
        auto, texto = resultado
        self.assertIn("PAGO DE DANIEL (no sale del cajón)", texto)
        self.assertEqual(auto.corte.monto_esperado, self._esperado())

    def test_el_corte_del_encargado_sin_cuenta(self) -> None:
        with patch("pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets", lambda *a, **k: None):
            _auto, texto = ccd.hacer_corte_automatico(None, creado_por="ENC-1")
        self.assertNotIn("PAGO DE", texto)


class CorteRemotoTests(unittest.TestCase):
    """El corte del celular / automático: ticket y mensaje de Telegram."""

    def _correr(self, lineas):
        from pos_uniformes.services import corte_remoto_service as crs
        from pos_uniformes.services.corte_caja_service import EstadoCaja, ResumenPeriodo

        hasta = datetime(2026, 11, 19, 23, 30, tzinfo=timezone.utc)
        estado = EstadoCaja(
            desde=datetime(2026, 11, 19, 1, tzinfo=timezone.utc), hasta=hasta, reactivo=Decimal("1000.00"),
            resumen=ResumenPeriodo(11, 23, Decimal("7480"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("7480")),
            pagos=Decimal("0"), retiros=Decimal("0"),
        )
        corte = _corte(monto_final=Decimal("8480.00"), created_at=hasta)
        auto = SimpleNamespace(corte=corte, estado=estado, pagos=[])
        datos = SimpleNamespace(por_empleada=[], tarjeta=Decimal("0.00"), tarjeta_ops=0, retiros=[])
        with patch("pos_uniformes.services.corte_caja_service.estado_caja", return_value=estado), \
                patch("pos_uniformes.services.corte_caja_service.pagos_que_tocan_hoy", return_value=[]), \
                patch("pos_uniformes.services.corte_caja_service.ultimo_corte", return_value=None), \
                patch("pos_uniformes.services.corte_caja_service.cerrar_corte_automatico", return_value=auto), \
                patch("pos_uniformes.services.corte_caja_service.operaciones_del_periodo", return_value=[]), \
                patch("pos_uniformes.services.corte_caja_service.datos_ticket_encargado", return_value=datos), \
                patch("pos_uniformes.services.retiros_service.retiros_del_periodo", return_value=[]), \
                patch("pos_uniformes.services.entradas_service.entradas_del_periodo", return_value=[]), \
                patch("pos_uniformes.ui.dialogs.corte_caja_dialog.pagos_previos_del_periodo", return_value=[]), \
                patch("pos_uniformes.ui.dialogs.corte_caja_dialog.lineas_pago_dueno", return_value=lineas), \
                patch("pos_uniformes.services.trabajos_service.enviar_corte") as enviar:
            resultado = crs.hacer_corte_y_avisar(MagicMock(), creado_por="VEND-1", ahora=hasta, sin_tarjeta=False)
        return resultado, enviar.call_args.args[1]

    def test_con_cuenta_sale_en_el_papel_y_en_telegram(self) -> None:
        resultado, papel = self._correr(LINEAS)
        self.assertIn("PAGO DE DANIEL (no sale del cajón)", papel)
        self.assertIn("💼 PAGO DE DANIEL (no sale del cajón)", resultado.mensaje)
        self.assertIn("Último pago: 19-nov", resultado.mensaje)
        # Las cifras del mensaje no cambian.
        self.assertIn("Sacar de la venta: $7,480.00", resultado.mensaje)

    def test_sin_cuenta_no_sale_nada(self) -> None:
        resultado, papel = self._correr([])
        self.assertNotIn("PAGO DE", papel)
        self.assertNotIn("PAGO DE", resultado.mensaje)
        self.assertIn("Sacar de la venta: $7,480.00", resultado.mensaje)


if __name__ == "__main__":
    unittest.main()
