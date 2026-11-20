"""💼 Mi pago (kiosko, solo VEND-1) y la pregunta del calendario del dueño
«¿Te lo pagamos o te lo guardamos?» (Daniel, 2026-11-19)."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Empleada, EmpleadaEvento, EmpleadaHorario
from pos_uniformes.services import pago_dueno_service as pd
from pos_uniformes.services.calendario_empleadas_service import DESCANSO, FALTA, TRABAJO
from pos_uniformes.ui.dialogs import mi_pago_dialog as mp

D = date
HOY = date.today()
# El martes más reciente (descanso del dueño), con la cuenta arrancando una semana antes.
MARTES = HOY - timedelta(days=(HOY.weekday() - 1) % 7)
INICIO = MARTES - timedelta(days=7)


def _base():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine)
    with fabrica() as s:
        s.add(Empleada(codigo="VEND-1", nombre_completo="Daniel Fabian", activo=True))
        s.add(EmpleadaHorario(employee_code="VEND-1", descanso_weekday=1))
        s.commit()

    @contextmanager
    def sesion():
        s = fabrica()
        try:
            yield s
        finally:
            s.close()

    return engine, fabrica, sesion


def _desglose(**kw) -> pd.DesglosePago:
    datos = dict(
        fecha_programada=D(2026, 11, 21), numero=3, de=4, desde=D(2026, 11, 15), hasta=D(2026, 11, 21),
        base=Decimal("2500.00"), valor_dia=Decimal("385.00"),
    )
    datos.update(kw)
    return pd.DesglosePago(**datos)


class TextosTests(unittest.TestCase):
    def test_titulo_y_estados(self) -> None:
        p = _desglose()
        self.assertEqual(mp.titulo_pago(p), "3 de 4 · sáb 21-nov")
        self.assertEqual(mp.texto_estado(p, D(2026, 11, 19)), "Pendiente")
        self.assertEqual(mp.texto_estado(p, D(2026, 11, 21)), "Toca hoy")
        self.assertEqual(mp.texto_estado(p, D(2026, 11, 22)), "Atrasado")
        p.registro = pd.RegistroPago(D(2026, 11, 21), D(2026, 11, 20), Decimal("2500.00"))
        self.assertEqual(mp.texto_estado(p, D(2026, 11, 22)), "Pagado el 20-nov · $2,500")

    def test_desglose_con_dias_de_mas_y_faltas(self) -> None:
        p = _desglose(
            dias_extra_pagados=[D(2026, 11, 17)],
            dias_extra_acumulados=[D(2026, 11, 18)], dias_extra_sin_decidir=[D(2026, 11, 18)],
            faltas_descontadas=[D(2026, 11, 20)], faltas_cubiertas=[D(2026, 11, 19)],
        )
        texto = "\n".join(mp.lineas_desglose(p))
        self.assertIn("Cubre del 15-nov al 21-nov", texto)
        self.assertIn("Base: $2,500", texto)
        self.assertIn("+ 1 día de más: $385 (17-nov)", texto)
        self.assertIn("− 1 falta(s): $385 (20-nov)", texto)
        self.assertIn("cubierta(s) con días a favor: 19-nov", texto)
        self.assertIn("sin decidir (se guardan): 18-nov", texto)
        self.assertTrue(texto.endswith("Total: $2,500"))

    def test_desglose_simple(self) -> None:
        self.assertEqual(mp.lineas_desglose(_desglose()),
                         ["Cubre del 15-nov al 21-nov", "Base: $2,500", "Total: $2,500"])

    def test_resumen_sin_cuenta(self) -> None:
        self.assertIn("no está configurada", mp.texto_resumen(None))

    def test_dias_de_pago(self) -> None:
        self.assertEqual(mp.leer_dias_de_pago("7, 14, 21, 28"), (7, 14, 21, 28))
        self.assertEqual(mp.leer_dias_de_pago("28 14"), (14, 28))
        for malo in ("7, 31", "siete", ""):
            with self.assertRaises(ValueError):
                mp.leer_dias_de_pago(malo)


class MiPagoDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.engine, self.fabrica, self.sesion = _base()
        self.addCleanup(self.engine.dispose)

    def _dialogo(self, hoy=D(2026, 11, 19)) -> mp.MiPagoDialog:
        d = mp.MiPagoDialog(None, quien="VEND-1", session_factory=self.sesion, hoy=hoy)
        self.addCleanup(d.deleteLater)
        return d

    def test_sin_configuracion_lo_dice_y_se_puede_configurar(self) -> None:
        d = self._dialogo()
        self.assertIn("no está configurada", d.resumen.text())
        self.assertEqual(d.pagos, [])
        d.cfg_inicio.setDate(QDate(2026, 11, 19))
        d._guardar_config()
        self.assertIn("3 de 4", d.resumen.text())
        self.assertEqual([p.fecha_programada for p in d.pagos], [D(2026, 11, 21), D(2026, 11, 28)])

    def test_fechas_de_pago_invalidas_no_se_guardan(self) -> None:
        d = self._dialogo()
        d.cfg_dias.setText("7, 30")
        with patch.object(QMessageBox, "warning") as aviso:
            d._guardar_config()
        aviso.assert_called_once()
        with self.sesion() as s:
            self.assertIsNone(pd.cargar_config(s))

    def test_el_caso_real_pago_2_de_4_y_deshacer(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
        d = self._dialogo()
        self.assertTrue(d.registrar(D(2026, 11, 14), D(2026, 11, 19), None))
        self.assertIn("Último pago: 19-nov", d.resumen.text())
        self.assertIn("Pago 2 de 4 guardado: $2,500", d.status.text())
        # Un monto editado
        self.assertTrue(d.registrar(D(2026, 11, 21), D(2026, 11, 19), Decimal("2400")))
        self.assertTrue(d.pagos[0].pagado)
        self.assertEqual(d.pagos[0].registro.monto, Decimal("2400.00"))
        self.assertTrue(d.deshacer(D(2026, 11, 21)))
        self.assertFalse(d.pagos[0].pagado)

    def test_un_pago_futuro_avisa_y_no_se_guarda(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
        d = self._dialogo()
        with patch.object(QMessageBox, "warning") as aviso:
            self.assertFalse(d.registrar(D(2026, 11, 21), D(2026, 11, 22), None))
        aviso.assert_called_once()

    def test_las_tarjetas_ofrecen_el_boton_correcto(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
            pd.registrar_pago(s, D(2026, 11, 21), D(2026, 11, 19), None, "VEND-1", hoy=D(2026, 11, 19))
        d = self._dialogo()
        tarjetas = [d._pagos_box.itemAt(i).widget() for i in range(d._pagos_box.count())]
        self.assertEqual([t.boton.text() for t in tarjetas], ["Deshacer pago", "💵 Ya me pagaron"])

    def test_cambiar_el_destino_de_un_dia_de_mas(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
            s.add(EmpleadaEvento(employee_code="VEND-1", fecha=D(2026, 11, 24), tipo=TRABAJO))
            s.commit()
        d = self._dialogo(hoy=D(2026, 11, 25))
        self.assertEqual(len(d.extras), 1)
        self.assertTrue(d.extras[0].sin_decidir)
        d._decidir(D(2026, 11, 24), pd.PAGAR)
        self.assertEqual(d.extras[0].destino, pd.PAGAR)
        self.assertEqual(d.pagos[-1].monto, Decimal("2885.00"))

    def test_solo_el_dueno(self) -> None:
        with patch.object(QMessageBox, "information") as aviso, patch.object(mp.MiPagoDialog, "exec") as exe:
            self.assertFalse(mp.abrir_mi_pago(None, "VEND-4"))
            aviso.assert_called_once()
            exe.assert_not_called()
        with patch("pos_uniformes.database.connection.get_session", self.sesion), \
                patch.object(mp.MiPagoDialog, "exec") as exe:
            self.assertTrue(mp.abrir_mi_pago(None, "vend-1"))
            exe.assert_called_once()


class PreguntaDelCalendarioTests(unittest.TestCase):
    """`despues_de_marcar_dueno`: lo que el calendario llama tras marcar un día del dueño."""

    def setUp(self) -> None:
        self.engine, self.fabrica, self.sesion = _base()
        self.addCleanup(self.engine.dispose)
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19))
        self.preguntas = []

    def _marcar(self, fecha, tipo) -> None:
        from pos_uniformes.services.calendario_empleadas_service import marcar_dia

        with self.sesion() as s:
            marcar_dia(s, "VEND-1", fecha, tipo, actor="VEND-1")

    def _despues(self, fecha, tipo, respuesta):
        def preguntar(parent, f, valor_dia, actual):
            self.preguntas.append((f, valor_dia, actual))
            return respuesta

        return mp.despues_de_marcar_dueno(None, fecha, tipo, session_factory=self.sesion, preguntar=preguntar)

    def _decision(self, fecha):
        with self.sesion() as s:
            return pd.decision_dia_extra(s, fecha)

    def test_trabajo_en_su_descanso_pregunta_y_guarda(self) -> None:
        self._marcar(D(2026, 11, 24), TRABAJO)
        self.assertEqual(self._despues(D(2026, 11, 24), TRABAJO, pd.PAGAR), pd.PAGAR)
        self.assertEqual(self.preguntas, [(D(2026, 11, 24), Decimal("385.00"), None)])
        self.assertEqual(self._decision(D(2026, 11, 24)), pd.PAGAR)

    def test_luego_lo_deja_sin_decidir(self) -> None:
        self._marcar(D(2026, 11, 24), TRABAJO)
        self.assertIsNone(self._despues(D(2026, 11, 24), TRABAJO, None))
        self.assertIsNone(self._decision(D(2026, 11, 24)))

    def test_trabajo_en_dia_normal_no_pregunta(self) -> None:
        self._marcar(D(2026, 11, 25), TRABAJO)        # miércoles
        self.assertIsNone(self._despues(D(2026, 11, 25), TRABAJO, pd.PAGAR))
        self.assertEqual(self.preguntas, [])

    def test_quitar_la_marca_borra_la_decision(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import quitar_marca

        self._marcar(D(2026, 11, 24), TRABAJO)
        self._despues(D(2026, 11, 24), TRABAJO, pd.PAGAR)
        with self.sesion() as s:
            quitar_marca(s, "VEND-1", D(2026, 11, 24), actor="VEND-1")
        self.assertIsNone(self._despues(D(2026, 11, 24), "", pd.PAGAR))
        self.assertIsNone(self._decision(D(2026, 11, 24)))

    def test_cambiarlo_a_falta_borra_la_decision(self) -> None:
        self._marcar(D(2026, 11, 24), TRABAJO)
        self._despues(D(2026, 11, 24), TRABAJO, pd.ACUMULAR)
        self._marcar(D(2026, 11, 24), FALTA)
        self._despues(D(2026, 11, 24), FALTA, pd.PAGAR)
        self.assertIsNone(self._decision(D(2026, 11, 24)))

    def test_sin_cuenta_no_pregunta(self) -> None:
        with self.sesion() as s:
            pd.guardar_config(s, fecha_inicio=D(2026, 11, 19), activo=False)
        self._marcar(D(2026, 11, 24), TRABAJO)
        self.assertIsNone(self._despues(D(2026, 11, 24), TRABAJO, pd.PAGAR))
        self.assertEqual(self.preguntas, [])


class CalendarioDelDuenoTests(unittest.TestCase):
    """En el calendario, eligiendo a VEND-1: «Sí trabajó» en su martes pregunta."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from pos_uniformes.ui.dialogs import calendario_empleadas_dialog as cal

        self.engine, self.fabrica, self.sesion = _base()
        self.addCleanup(self.engine.dispose)
        with self.fabrica() as s:
            s.add(Empleada(codigo="VEND-4", nombre_completo="Stayce Chavarria", activo=True))
            s.add(EmpleadaHorario(employee_code="VEND-4", descanso_weekday=1))
            s.commit()
            pd.guardar_config(s, fecha_inicio=INICIO)
        parches = [
            patch("pos_uniformes.database.connection.get_session", self.sesion),
            patch("pos_uniformes.services.satellite_startup_service.probe_database_host", return_value=True),
        ]
        for p in parches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in parches])
        self.d = cal.CalendarioEmpleadasDialog(None, employee_code="VEND-1", employee_name="Daniel", is_owner=True)
        self.addCleanup(self.d.deleteLater)

    def _elegir(self, code: str, dia: date) -> None:
        self.d._combo.setCurrentIndex(self.d._combo.findData(code))
        self.d.cal.setSelectedDate(QDate(dia.year, dia.month, dia.day))

    def test_si_trabajo_en_su_martes_pregunta_y_guarda(self) -> None:
        self._elegir("VEND-1", MARTES)
        with patch.object(mp, "preguntar_destino", return_value=pd.ACUMULAR) as preguntar:
            self.d._marcar(TRABAJO)
        preguntar.assert_called_once()
        with self.sesion() as s:
            self.assertEqual(pd.decision_dia_extra(s, MARTES), pd.ACUMULAR)
        with patch.object(mp, "preguntar_destino") as preguntar:
            self.d._quitar()
        preguntar.assert_not_called()
        with self.sesion() as s:
            self.assertIsNone(pd.decision_dia_extra(s, MARTES))

    def test_otra_empleada_no_pregunta(self) -> None:
        self._elegir("VEND-4", MARTES)
        with patch.object(mp, "preguntar_destino") as preguntar:
            self.d._marcar(TRABAJO)
        preguntar.assert_not_called()

    def test_descanso_del_dueno_no_pregunta(self) -> None:
        self._elegir("VEND-1", MARTES + timedelta(days=1) if MARTES + timedelta(days=1) <= HOY else MARTES)
        with patch.object(mp, "preguntar_destino") as preguntar:
            self.d._marcar(DESCANSO)
        preguntar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
