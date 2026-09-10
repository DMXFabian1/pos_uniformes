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

from pos_uniformes.database.models import CajaParametros, LibretaCorte
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
    SinPermiso,
    borrar_corte,
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
        c = _corte(creado_por="ENC-1")
        self.assertEqual(diferencia_corte(c), Decimal("-20.00"))
        self.assertEqual(retirado(c), Decimal("1820.00"))
        self.assertIsNone(diferencia_corte(_corte(hasta=None)))  # corte viejo sin esperado
        legacy = _corte(desde=None, reactivo_inicial=Decimal("0"), reactivo_final=Decimal("0"), monto_esperado=Decimal("0"), periodo_label="HOY")
        self.assertIsNone(diferencia_corte(legacy))
        self.assertEqual(retirado(legacy), Decimal("0.00"))  # era total del día, no retiro
        self.assertEqual(diferencia_corte(_corte(creado_por="VEND-1")), Decimal("-20.00"))  # oficial vs real, solo para el dueño

    def test_formato_original(self) -> None:
        self.assertEqual(formato_original(_corte(creado_por="ENC-1")), FORMATO_ENCARGADO)
        self.assertEqual(formato_original(_corte(creado_por="auto")), FORMATO_ENCARGADO)
        self.assertEqual(formato_original(_corte(creado_por="VEND-1")), FORMATO_DUENO)

    def test_totales(self) -> None:
        t = totales_cortes([_corte(), _corte(id=2, monto_final=Decimal("11500.00"), retiros_pagos=Decimal("0"), otros_retiros=Decimal("200"))])
        self.assertEqual(t.cortes, 2)
        # venta oficial: (12980−11160+1390) + (11500−11160+0+200) = 3210 + 540
        self.assertEqual(t.venta, Decimal("3750.00"))
        self.assertEqual(t.retirado, Decimal("2160.00"))
        self.assertEqual(t.pagos, Decimal("1390.00"))
        self.assertEqual(t.otros_retiros, Decimal("200.00"))


class VentaTests(unittest.TestCase):
    """La tabla habla como el ticket: reactivo · venta · pagos · gastos · se retiró."""

    def test_venta_oficial_y_real(self) -> None:
        from pos_uniformes.services.historial_cortes_service import venta_oficial, venta_real

        c = _corte()  # final 12,980 · real 13,000 · reactivo 11,160 · pagos 1,390
        self.assertEqual(venta_oficial(c), Decimal("3210.00"))
        self.assertEqual(venta_real(c), Decimal("3230.00"))
        self.assertEqual(venta_oficial(c) - venta_real(c), diferencia_corte(c))

    def test_con_gastos(self) -> None:
        from pos_uniformes.services.historial_cortes_service import venta_oficial

        self.assertEqual(venta_oficial(_corte(otros_retiros=Decimal("500"))), Decimal("3710.00"))

    def test_corte_viejo_su_cifra_era_la_venta(self) -> None:
        from pos_uniformes.services.historial_cortes_service import venta_oficial, venta_real

        legacy = _corte(desde=None, reactivo_inicial=Decimal("0"), monto_esperado=Decimal("0"))
        self.assertEqual(venta_oficial(legacy), Decimal("12980.00"))
        self.assertIsNone(venta_real(legacy))


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

    def test_periodo_de_corte_viejo_es_su_dia(self) -> None:
        # Los cortes de antes ("HOY") eran el total del día: de 00:00 a la hora del corte.
        # (Antes se iba 90 días atrás y reimprimía $64,822 de "hoy" — bug del 2026-09-09.)
        viejo = self._guardar(date(2026, 9, 5), datetime(2026, 9, 5, 16, 35).astimezone(), hasta=datetime(2026, 9, 5, 16, 35).astimezone())
        nuevo = self._guardar(date(2026, 9, 8), _T0 + timedelta(days=1), desde=_T0, hasta=_T0 + timedelta(days=1))
        d, h = periodo_del_corte(self.session, viejo)
        self.assertEqual(h.replace(tzinfo=None), datetime(2026, 9, 5, 16, 35))
        self.assertEqual((d.hour, d.minute, d.date()), (0, 0, date(2026, 9, 5)))
        d, h = periodo_del_corte(self.session, nuevo)
        self.assertEqual((d.replace(tzinfo=None), h.replace(tzinfo=None)), (_T0.replace(tzinfo=None), (_T0 + timedelta(days=1)).replace(tzinfo=None)))


class BorrarCorteTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        LibretaCorte.__table__.create(engine)
        CajaParametros.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()
        from pos_uniformes.services.corte_caja_service import guardar_parametros

        guardar_parametros(self.session, reactivo_actual=Decimal("11500.00"))
        # a: 07/09 → 08/09 18:00 ; b: 08/09 18:00 → 09/09 12:00 (reactivo subió a 11500) ; c: 09/09 12:00 → 09/09 12:05 (doble)
        self.a = self._c(date(2026, 9, 8), _T0, _T0 + timedelta(hours=21, minutes=30), Decimal("11160"), Decimal("11160"))
        self.b = self._c(date(2026, 9, 9), self.a.hasta, self.a.hasta + timedelta(hours=18), Decimal("11160"), Decimal("11500"))
        self.c = self._c(date(2026, 9, 9), self.b.hasta, self.b.hasta + timedelta(minutes=5), Decimal("11500"), Decimal("11500"))

    def _c(self, fecha, desde, hasta, r_ini, r_fin):
        fila = LibretaCorte(fecha=fecha, periodo_label="x", monto_final=Decimal("12000"), creado_por="VEND-1", created_at=hasta,
                            desde=desde, hasta=hasta, reactivo_inicial=r_ini, reactivo_final=r_fin, monto_esperado=Decimal("12000"))
        self.session.add(fila)
        self.session.commit()
        return fila

    def test_solo_daniel(self) -> None:
        with self.assertRaises(SinPermiso):
            borrar_corte(self.session, self.c.id, creado_por="ENC-1")

    def test_borrar_el_ultimo_restaura_reactivo(self) -> None:
        from pos_uniformes.services.corte_caja_service import cargar_parametros, ultimo_corte

        r = borrar_corte(self.session, self.c.id, creado_por="VEND-1")
        self.assertTrue(r["era_ultimo"])
        self.assertEqual(r["reactivo_restaurado"], Decimal("11500.00"))
        self.assertEqual(cargar_parametros(self.session).reactivo_actual, Decimal("11500.00"))
        self.assertEqual(ultimo_corte(self.session).id, self.b.id)

    def test_borrar_uno_de_en_medio_extiende_el_siguiente(self) -> None:
        r = borrar_corte(self.session, self.b.id, creado_por="VEND-1")
        self.assertFalse(r["era_ultimo"])
        self.session.refresh(self.c)
        self.assertEqual(self.c.desde.replace(tzinfo=None), self.a.hasta.replace(tzinfo=None))
        self.assertIsNone(self.session.get(LibretaCorte, self.b.id))


class QuitarAjusteTests(unittest.TestCase):
    """Dejar la cifra oficial igual a la real (pruebas o ajustes que ya no aplican)."""

    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        LibretaCorte.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()
        self.corte = LibretaCorte(
            fecha=date(2026, 9, 9), periodo_label="x", monto_final=Decimal("23202"), monto_esperado=Decimal("26202"),
            creado_por="VEND-1", created_at=_T0, desde=_T0 - timedelta(days=1), hasta=_T0,
            reactivo_inicial=Decimal("11160"), reactivo_final=Decimal("11160"), retiros_pagos=Decimal("1598"),
        )
        self.session.add(self.corte)
        self.session.commit()

    def test_quita_el_ajuste(self) -> None:
        from pos_uniformes.services.historial_cortes_service import quitar_ajuste

        r = quitar_ajuste(self.session, self.corte.id, creado_por="VEND-1")
        self.assertTrue(r["cambio"])
        self.assertEqual(r["ajuste"], Decimal("-3000.00"))
        self.session.refresh(self.corte)
        self.assertEqual(self.corte.monto_final, Decimal("26202.00"))
        self.assertEqual(diferencia_corte(self.corte), Decimal("0.00"))  # ya no hay diferencia
        # El reactivo no se toca: solo cambia lo que se retiró.
        self.assertEqual(self.corte.reactivo_final, Decimal("11160.00"))
        self.assertEqual(retirado(self.corte), Decimal("15042.00"))

    def test_sin_ajuste_no_hace_nada(self) -> None:
        from pos_uniformes.services.historial_cortes_service import quitar_ajuste

        quitar_ajuste(self.session, self.corte.id, creado_por="VEND-1")
        r = quitar_ajuste(self.session, self.corte.id, creado_por="VEND-1")
        self.assertFalse(r["cambio"])

    def test_ajustar_la_venta_recalcula_la_cifra(self) -> None:
        from pos_uniformes.services.historial_cortes_service import ajustar_corte, venta_oficial, venta_real

        # Caso real del 09/09: venta real 16,640 y se entregan 12,042 (3,000 fuera).
        self.corte.monto_final = Decimal("26202")
        self.corte.monto_esperado = Decimal("26202")
        self.corte.retiros_pagos = Decimal("1598")
        self.session.commit()
        self.assertEqual(venta_real(self.corte), Decimal("16640.00"))
        r = ajustar_corte(self.session, self.corte.id, venta=Decimal("13640"), creado_por="VEND-1")
        self.assertEqual(r["sin_reportar"], Decimal("3000.00"))
        self.assertEqual(r["retirado"], Decimal("12042.00"))
        self.session.refresh(self.corte)
        self.assertEqual(venta_oficial(self.corte), Decimal("13640.00"))
        self.assertEqual(venta_real(self.corte), Decimal("16640.00"))
        self.assertEqual(diferencia_corte(self.corte), Decimal("-3000.00"))

    def test_ajustar_no_puede_dejar_sin_reactivo(self) -> None:
        from pos_uniformes.services.historial_cortes_service import ajustar_corte

        with self.assertRaises(ValueError):
            ajustar_corte(self.session, self.corte.id, venta=Decimal("0"), creado_por="VEND-1")

    def test_ajustar_solo_el_dueno(self) -> None:
        from pos_uniformes.services.historial_cortes_service import SinPermiso, ajustar_corte

        with self.assertRaises(SinPermiso):
            ajustar_corte(self.session, self.corte.id, venta=Decimal("100"), creado_por="ENC-1")

    def test_solo_el_dueno(self) -> None:
        from pos_uniformes.services.historial_cortes_service import SinPermiso, quitar_ajuste

        with self.assertRaises(SinPermiso):
            quitar_ajuste(self.session, self.corte.id, creado_por="ENC-1")

    def test_corte_viejo_no_tiene_ajuste_que_quitar(self) -> None:
        from pos_uniformes.services.historial_cortes_service import quitar_ajuste

        viejo = LibretaCorte(fecha=date(2026, 9, 5), periodo_label="HOY", monto_final=Decimal("22300"),
                             monto_esperado=Decimal("0"), creado_por="VEND-1", created_at=_T0 - timedelta(days=4))
        self.session.add(viejo)
        self.session.commit()
        with self.assertRaises(ValueError):
            quitar_ajuste(self.session, viejo.id, creado_por="VEND-1")


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

        t = texto_ticket_reimpresion(_corte(monto_final=Decimal("13000.00")), self._datos(), FORMATO_DUENO)  # sin ajuste
        self.assertIn("CORTE DE CAJA", t)
        self.assertIn("* REIMPRESION *", t)
        self.assertIn("Corte:", t)
        self.assertIn("$3,210.00", t)
        # Con ajuste (12,980 vs esperado 13,000): la venta impresa cuadra con su cifra y nada dice "esperado".
        ajustado = texto_ticket_reimpresion(_corte(), self._datos(), FORMATO_DUENO)
        self.assertIn("$1,820.00", ajustado)  # SACAR = 12980 − 11160
        self.assertNotIn("esperado", ajustado.lower())
        self.assertIn("Ana", t)
        self.assertNotIn("esperado", t.lower())  # nunca la palabra ni la diferencia en papel
        t2 = texto_ticket_reimpresion(_corte(creado_por="ENC-1"), self._datos(), FORMATO_ENCARGADO)
        self.assertIn("Venta en efectivo:", t2)
        self.assertIn("* REIMPRESION *", t2)
        self.assertIn("PAGAR A ANA:", t2)


class VentaCongruenteTests(unittest.TestCase):
    def test_reimpresion_encargado_con_ajuste_usa_la_venta_que_cuadra(self) -> None:
        from pos_uniformes.ui.dialogs.historial_cortes_dialog import texto_ticket_reimpresion, venta_congruente

        datos = TicketReimpresionTests()._datos()  # venta real 3,210
        ajustado = _corte(creado_por="VEND-1", monto_final=Decimal("12980.00"), monto_esperado=Decimal("13000.00"))
        # 12980 − 11160 + 1390 = 3,210 coincide; forzamos un ajuste de $500 para verlo
        ajustado2 = _corte(creado_por="VEND-1", monto_final=Decimal("12500.00"), monto_esperado=Decimal("13000.00"))
        self.assertEqual(venta_congruente(ajustado2, datos), Decimal("2730.00"))
        t = texto_ticket_reimpresion(ajustado2, datos, FORMATO_ENCARGADO)
        self.assertIn("$2,730.00", t)
        self.assertNotIn("$3,210.00", t)
        sin = _corte(creado_por="VEND-1", monto_final=Decimal("13000.00"))
        self.assertEqual(venta_congruente(sin, datos), Decimal("3210.00"))


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_filas_totales_y_previa(self) -> None:
        from pos_uniformes.ui.dialogs.historial_cortes_dialog import COLUMNAS, HistorialCortesDialog, filas_tabla, texto_diferencia

        cortes = [_corte(creado_por="ENC-1"), _corte(id=2, creado_por="ENC-1", monto_final=Decimal("13000.00"), nota="ok")]
        self.assertEqual(texto_diferencia(cortes[1]), "cuadró ✅")
        self.assertEqual(texto_diferencia(cortes[0]), "faltó $20.00")
        self.assertEqual(texto_diferencia(_corte(creado_por="VEND-1")), "ajuste −$20.00")
        self.assertEqual(texto_diferencia(_corte(creado_por="VEND-1", monto_final=Decimal("13000.00"))), "sin ajuste")
        legacy = _corte(desde=None, reactivo_inicial=Decimal("0"), reactivo_final=Decimal("0"), monto_esperado=Decimal("0"), periodo_label="HOY")
        fila = filas_tabla([legacy])[0]
        self.assertEqual(fila[4], "—")                 # sin reactivo
        self.assertEqual(fila[5], "$12,980.00")        # su cifra ERA el total del día
        self.assertEqual(fila[6], "—")                 # sin venta real guardada
        self.assertEqual(texto_diferencia(legacy), "—")
        # Mismo orden que el ticket: reactivo · venta · venta real · pagos · gastos · se retiró
        filas = filas_tabla(cortes)
        self.assertEqual(filas[0][0], "08/09/2026")
        self.assertEqual(filas[0][4], "$11,160.00")   # reactivo con que abrió
        self.assertEqual(filas[0][5], "$3,210.00")    # venta oficial: 12980 − 11160 + 1390
        self.assertEqual(filas[0][6], "$3,230.00")    # venta real: 13000 − 11160 + 1390
        self.assertEqual(filas[0][7], "$1,390.00")    # pagos
        self.assertEqual(filas[0][8], "$0.00")        # gastos
        self.assertEqual(filas[1][10], "ok")
        self.assertNotIn("Se retiró", COLUMNAS)       # quitada a pedido de Daniel (2026-09-10)

        with patch.object(HistorialCortesDialog, "recargar"):
            dlg = HistorialCortesDialog(None, hoy=date(2026, 9, 9))
        self.assertEqual(dlg.mes_combo.itemText(0), "Septiembre 2026")
        # Real y Ajuste ocultas por default; Ctrl+Shift+R las asoma (y las vuelve a esconder).
        self.assertTrue(dlg.tabla.isColumnHidden(6) and dlg.tabla.isColumnHidden(9))
        dlg.alternar_modo_real()
        self.assertFalse(dlg.tabla.isColumnHidden(6) or dlg.tabla.isColumnHidden(9))
        self.assertIn("con lo real", dlg.windowTitle())
        dlg.alternar_modo_real()
        self.assertTrue(dlg.tabla.isColumnHidden(6))
        dlg.pintar(cortes)
        self.assertEqual(dlg.tabla.rowCount(), 2)
        self.assertIn("2 corte(s)", dlg.totales_label.text())
        self.assertFalse(dlg.reprint_button.isEnabled())

        datos = TicketReimpresionTests()._datos()
        with patch.object(HistorialCortesDialog, "_datos", return_value=datos):
            # El ticket SIMPLE es el default para todos (Daniel 2026-09-10).
            dlg.tabla.selectRow(1)
            self.assertFalse(dlg.formato_check.isChecked())
            self.assertIn("Venta en efectivo:", dlg.previa.toPlainText())
            self.assertTrue(dlg.reprint_button.isEnabled())
            dlg.formato_check.setChecked(True)          # la casilla saca el completo
            self.assertIn("CORTE DE CAJA", dlg.previa.toPlainText())
            dlg.tabla.selectRow(0)                       # al cambiar de corte vuelve al simple
            self.assertFalse(dlg.formato_check.isChecked())
            self.assertIs(dlg.corte_seleccionado(), cortes[0])

        # Borrar solo con gafete VEND-1 (este diálogo se abrió sin gafete): botón oculto
        self.assertFalse(dlg.delete_button.isVisibleTo(dlg))
        with patch("pos_uniformes.ui.helpers.ticket_routing_helper.route_tickets") as rt:
            dlg.reimprimir()
        self.assertEqual(rt.call_args.args[1], "Corte de caja (reimpresión)")
        self.assertIn("* REIMPRESION *", rt.call_args.args[2][0])

    def test_borrar_con_gafete_del_dueno(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        from pos_uniformes.ui.dialogs.historial_cortes_dialog import HistorialCortesDialog

        with patch.object(HistorialCortesDialog, "recargar"):
            dlg = HistorialCortesDialog(None, hoy=date(2026, 9, 9), creado_por="VEND-1")
        self.assertTrue(dlg.delete_button.isVisibleTo(dlg))
        dlg.pintar([_corte(creado_por="VEND-1")])
        with patch.object(HistorialCortesDialog, "_datos", return_value=TicketReimpresionTests()._datos()):
            dlg.tabla.selectRow(0)
        self.assertTrue(dlg.delete_button.isEnabled())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), patch(
            "pos_uniformes.services.historial_cortes_service.borrar_corte", return_value={"reactivo_restaurado": Decimal("11160.00")}
        ) as borrar, patch("pos_uniformes.database.connection.get_session") as gs, patch.object(dlg, "recargar") as rec:
            gs.return_value.__enter__.return_value = object()
            dlg.borrar()
        self.assertEqual(borrar.call_args.args[1], 1)
        self.assertEqual(borrar.call_args.kwargs["creado_por"], "VEND-1")
        self.assertIn("Reactivo de vuelta en $11,160.00", dlg.totales_label.text())
        rec.assert_called_once()

    def test_sin_cortes(self) -> None:
        from pos_uniformes.ui.dialogs.historial_cortes_dialog import HistorialCortesDialog

        with patch.object(HistorialCortesDialog, "recargar"):
            dlg = HistorialCortesDialog(None, hoy=date(2026, 9, 9))
        dlg.pintar([])
        self.assertEqual(dlg.tabla.rowCount(), 0)
        self.assertIn("No hay cortes", dlg.totales_label.text())


if __name__ == "__main__":
    unittest.main()
