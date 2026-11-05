"""El calendario de empleadas dice sobre QUÉ día actúan sus botones.

El 5 de noviembre de 2026, con el domingo 8 elegido (un día que todavía no
llegaba), «Le pagué este día» registró el pago de la semana en curso de Stayce:
se llevó sus 35 comisiones y adelantó una semana su siguiente pago. El botón no
decía el día, y nada impedía pagar en el futuro.
"""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Empleada, EmpleadaEvento, EmpleadaHorario
from pos_uniformes.ui.dialogs import calendario_empleadas_dialog as cal

HOY = date.today()


def _qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


class DiaElegidoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        fabrica = sessionmaker(bind=engine)
        with fabrica() as s:
            s.add(Empleada(codigo="VEND-4", nombre_completo="Stayce Chavarria", activo=True))
            s.add(EmpleadaHorario(employee_code="VEND-4", descanso_weekday=(HOY.weekday() + 2) % 7,
                                  fecha_ultimo_pago=HOY - timedelta(days=4)))
            s.add(EmpleadaEvento(employee_code="VEND-4", fecha=HOY - timedelta(days=4), tipo="pago"))
            s.commit()

        @contextmanager
        def sesion():
            s = fabrica()
            try:
                yield s
            finally:
                s.close()

        self._parches = [
            patch("pos_uniformes.database.connection.get_session", sesion),
            patch("pos_uniformes.services.satellite_startup_service.probe_database_host", return_value=True),
        ]
        for p in self._parches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._parches])
        self.d = cal.CalendarioEmpleadasDialog(None, employee_code="VEND-1", employee_name="Daniel", is_owner=True)
        i = self.d._combo.findData("VEND-4")
        if i >= 0:
            self.d._combo.setCurrentIndex(i)
        self.addCleanup(self.d.deleteLater)

    def test_hoy_el_boton_dice_el_dia_y_se_puede_pagar(self) -> None:
        self.d.cal.setSelectedDate(_qdate(HOY))
        self.assertIn(cal._fecha_corta(HOY), self.d.btn_pago.text())
        self.assertTrue(self.d.btn_pago.isEnabled())
        self.assertEqual(self.d.dia_cuando.text(), "HOY")
        self.assertEqual(self.d.dia_titulo.text(), cal._fecha_en_palabras(HOY).capitalize())

    def test_en_un_dia_que_no_ha_llegado_no_se_ofrece_pagar(self) -> None:
        futuro = HOY + timedelta(days=3)
        self.d.cal.setSelectedDate(_qdate(futuro))
        self.assertFalse(self.d.btn_pago.isEnabled())
        self.assertIn("todavía no llega", self.d.pago_nota.text())
        self.assertIn(cal._fecha_corta(futuro), self.d.btn_pago.text())     # y aun así dice de qué día habla
        self.assertEqual(self.d.dia_cuando.text(), "EN 3 DÍAS")
        # Los demás botones sí: marcar un descanso a futuro es lo normal.
        self.assertTrue(self.d.btn_descanso.isEnabled())

    def test_en_un_dia_que_ya_tiene_pago_tampoco(self) -> None:
        self.d.cal.setSelectedDate(_qdate(HOY - timedelta(days=4)))
        self.assertFalse(self.d.btn_pago.isEnabled())
        self.assertIn("ya tiene un pago", self.d.pago_nota.text())
        self.assertEqual(self.d.dia_cuando.text(), "HACE 4 DÍAS")

    def test_un_dia_pasado_sin_pago_sirve_para_apuntar_uno_olvidado(self) -> None:
        self.d.cal.setSelectedDate(_qdate(HOY - timedelta(days=1)))
        self.assertTrue(self.d.btn_pago.isEnabled())
        self.assertIn("no se registró", self.d.pago_nota.text())

    def test_las_fichas_de_arriba(self) -> None:
        self.assertIn("⭐", self.d.banner.text())
        self.assertIn("Comisiones desde el último pago", self.d.banner.toolTip())
        self.assertEqual(self.d._pie_pago.text(), "en 3 días")                # cobra cada 7: pagada hace 4
        self.assertIn("días", self.d._pie_descanso.text())


class PalabrasDeFechaTests(unittest.TestCase):
    def test_cuanto_falta(self) -> None:
        hoy = date(2026, 11, 5)
        self.assertEqual([cal._cuanto_falta(hoy + timedelta(days=n), hoy) for n in (0, 1, 3, -1, -4)],
                         ["hoy", "mañana", "en 3 días", "ayer", "hace 4 días"])
        self.assertEqual(cal._fecha_corta(date(2026, 11, 8)), "domingo 8 de nov")


if __name__ == "__main__":
    unittest.main()
