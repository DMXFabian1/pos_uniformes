"""Historial de cortes del dueño: periodo reconstruido, filas, totales y reimpresión."""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pos_uniformes.database.models import LibretaCorte
from pos_uniformes.services.historial_cortes_service import (
    FORMATO_DUENO,
    FORMATO_ENCARGADO,
    DatosReimpresion,
    diferencia_corte,
    formato_original,
    listar_cortes_mes,
    periodo_del_corte,
    retirado,
    totales_cortes,
)

_T0 = datetime(2026, 9, 7, 20, 30, tzinfo=timezone.utc)


def _corte(**extra):
    base = dict(
        id=1, fecha=date(2026, 9, 8), periodo_label="07/09 20:30 → 08/09 21:00", creado_por="VEND-1",
        operaciones=12, piezas=20, nota=None, created_at=_T0 + timedelta(days=1),
        desde=_T0, hasta=_T0 + timedelta(days=1),
        reactivo_inicial=Decimal("11160.00"), monto_esperado=Decimal("13000.00"),
        retiros_pagos=Decimal("1390.00"), otros_retiros=Decimal("0.00"),
        monto_final=Decimal("12980.00"), reactivo_final=Decimal("11160.00"),
    )
    base.update(extra)
    return SimpleNamespace(**base)


class PurasTests(unittest.TestCase):
    def test_diferencia_y_retirado(self) -> None:
        c = _corte()
        self.assertEqual(diferencia_corte(c), Decimal("-20.00"))
        self.assertEqual(retirado(c), Decimal("1820.00"))
        self.assertIsNone(diferencia_corte(_corte(hasta=None)))  # corte viejo sin esperado

    def test_formato_original(self) -> None:
        self.assertEqual(formato_original(_corte(creado_por="ENC-1")), FORMATO_ENCARGADO)
        self.assertEqual(formato_original(_corte(creado_por="auto")), FORMATO_ENCARGADO)
        self.assertEqual(formato_original(_corte(creado_por="VEND-1")), FORMATO_DUENO)

    def test_totales(self) -> None:
        t = totales_cortes([_corte(), _corte(id=2, monto_final=Decimal("11500.00"), retiros_pagos=Decimal("0"), otros_retiros=Decimal("200"))])
        self.assertEqual(t.cortes, 2)
        self.assertEqual(t.retirado, Decimal("2160.00"))
        self.assertEqual(t.pagos, Decimal("1390.00"))
        self.assertEqual(t.otros_retiros, Decimal("200.00"))


class ConBaseTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        LibretaCorte.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()

    def _guardar(self, fecha, created_at, **extra):
        fila = LibretaCorte(fecha=fecha, periodo_label="x", monto_final=Decimal("100"), creado_por="VEND-1", created_at=created_at, **extra)
        self.session.add(fila)
        self.session.commit()
        return fila

    def test_listar_por_mes_mas_reciente_primero(self) -> None:
        self._guardar(date(2026, 8, 31), _T0 - timedelta(days=8))
        a = self._guardar(date(2026, 9, 1), _T0 - timedelta(days=6))
        b = self._guardar(date(2026, 9, 8), _T0 + timedelta(days=1))
        cortes = listar_cortes_mes(self.session, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual([c.id for c in cortes], [b.id, a.id])

    def test_periodo_de_corte_viejo_usa_el_anterior(self) -> None:
        viejo1 = self._guardar(date(2026, 9, 1), _T0 - timedelta(days=6))
        viejo2 = self._guardar(date(2026, 9, 3), _T0 - timedelta(days=4))
        nuevo = self._guardar(date(2026, 9, 8), _T0 + timedelta(days=1), desde=_T0, hasta=_T0 + timedelta(days=1))
        d, h = periodo_del_corte(self.session, viejo2)
        self.assertEqual(h.replace(tzinfo=None), viejo2.created_at.replace(tzinfo=None))
        self.assertEqual(d.replace(tzinfo=None), viejo1.created_at.replace(tzinfo=None))
        d, h = periodo_del_corte(self.session, viejo1)
        self.assertIsNone(d)
        d, h = periodo_del_corte(self.session, nuevo)
        self.assertEqual((d.replace(tzinfo=None), h.replace(tzinfo=None)), (_T0.replace(tzinfo=None), (_T0 + timedelta(days=1)).replace(tzinfo=None)))


class TicketReimpresionTests(unittest.TestCase):
    def _datos(self):
        pago = SimpleNamespace(
            employee_name="Ana López", employee_code="VEND-2", total=Decimal("1390.00"), sueldo_base=Decimal("1300.00"),
            comisiones=45, tarifa_comision=Decimal("2.00"), monto_comisiones=Decimal("90.00"), faltas=0,
            descuento_faltas=Decimal("0.00"), dias_trabajados=None,
        )
        return DatosReimpresion(
            por_empleada=[SimpleNamespace(employee_name="Ana López", employee_code="VEND-2", operaciones=7, comisiones=45)],
            pagos=[pago], retiros=[], venta_efectivo=Decimal("3210.00"),
        )

    def test_dueno_y_encargado_marcados_como_reimpresion(self) -> None:
        from pos_uniformes.ui.dialogs.historial_cortes_dialog import texto_ticket_reimpresion

        t = texto_ticket_reimpresion(_corte(), self._datos(), FORMATO_DUENO)
        self.assertIn("CORTE DE CAJA", t)
        self.assertIn("* REIMPRESION *", t)
        self.assertIn("Corte:", t)
        self.assertIn("$3,210.00", t)
        self.assertIn("Ana", t)
        self.assertNotIn("13,000.00", t)  # nunca el esperado en papel
        t2 = texto_ticket_reimpresion(_corte(creado_por="ENC-1"), self._datos(), FORMATO_ENCARGADO)
        self.assertIn("SE VENDIO:", t2)
        self.assertIn("* REIMPRESION *", t2)
        self.assertIn("PAGAR A ANA:", t2)


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_filas_totales_y_previa(self) -> None:
        from pos_uniformes.ui.dialogs.historial_cortes_dialog import HistorialCortesDialog, filas_tabla, texto_diferencia

        cortes = [_corte(), _corte(id=2, creado_por="ENC-1", monto_final=Decimal("13000.00"), nota="ok")]
        self.assertEqual(texto_diferencia(cortes[1]), "cuadró ✅")
        self.assertEqual(texto_diferencia(cortes[0]), "faltó $20.00")
        filas = filas_tabla(cortes)
        self.assertEqual(filas[0][0], "08/09/2026")
        self.assertEqual(filas[0][4], "$12,980.00")
        self.assertEqual(filas[0][6], "$1,820.00")
        self.assertEqual(filas[1][9], "ok")

        with patch.object(HistorialCortesDialog, "recargar"):
            dlg = HistorialCortesDialog(None, hoy=date(2026, 9, 9))
        self.assertEqual(dlg.mes_combo.itemText(0), "Septiembre 2026")
        dlg.pintar(cortes)
        self.assertEqual(dlg.tabla.rowCount(), 2)
        self.assertIn("2 corte(s)", dlg.totales_label.text())
        self.assertFalse(dlg.reprint_button.isEnabled())

        datos = TicketReimpresionTests()._datos()
        with patch.object(HistorialCortesDialog, "_datos", return_value=datos):
            dlg.tabla.selectRow(1)  # el del encargado → formato simple por default
            self.assertTrue(dlg.formato_check.isChecked())
            self.assertIn("SE VENDIO:", dlg.previa.toPlainText())
            self.assertTrue(dlg.reprint_button.isEnabled())
            dlg.formato_check.setChecked(False)
            self.assertIn("CORTE DE CAJA", dlg.previa.toPlainText())
            dlg.tabla.selectRow(0)
            self.assertFalse(dlg.formato_check.isChecked())
            self.assertIs(dlg.corte_seleccionado(), cortes[0])

        with patch("pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets") as rt:
            dlg.reimprimir()
        self.assertEqual(rt.call_args.args[1], "Corte de caja (reimpresión)")
        self.assertIn("* REIMPRESION *", rt.call_args.args[2][0])

    def test_sin_cortes(self) -> None:
        from pos_uniformes.ui.dialogs.historial_cortes_dialog import HistorialCortesDialog

        with patch.object(HistorialCortesDialog, "recargar"):
            dlg = HistorialCortesDialog(None, hoy=date(2026, 9, 9))
        dlg.pintar([])
        self.assertEqual(dlg.tabla.rowCount(), 0)
        self.assertIn("No hay cortes", dlg.totales_label.text())


if __name__ == "__main__":
    unittest.main()
