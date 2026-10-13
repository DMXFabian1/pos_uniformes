"""El panel «Vacaciones del equipo» de Daniel, y quién ve qué en la Libreta."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QDate
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    CajaParametros, Empleada, EmpleadaEvento, EmpleadaHorario, ExpedienteVacacional, SolicitudVacaciones,
)
from pos_uniformes.services import vacaciones_service as vs


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.F = sessionmaker(bind=engine)
        with self.F() as s:
            s.add(Empleada(codigo="VEND-1", nombre_completo="Daniel", activo=True))
            s.add(Empleada(codigo="VEND-5", nombre_completo="Cristal Torres", activo=True))
            s.add(EmpleadaHorario(employee_code="VEND-5", descanso_weekday=6))
            s.add(CajaParametros(sueldo_base=Decimal("1300")))
            s.commit()
        self.widgets = []

    def tearDown(self) -> None:
        for w in self.widgets:
            w.deleteLater()


class PanelTests(_Base):
    def _panel(self):
        from pos_uniformes.ui.dialogs.vacaciones_equipo_dialog import VacacionesEquipoDialog

        d = VacacionesEquipoDialog(None, session_factory=self.F)
        self.widgets.append(d)
        d.tabla_equipo.selectRow(0)
        return d

    def test_captura_ingreso_registra_y_abre_el_autoservicio(self) -> None:
        d = self._panel()
        self.assertEqual(d.tabla_equipo.rowCount(), 1)          # sin el dueño
        self.assertFalse(d.btn_registrar.isEnabled())             # sin expediente
        hace_dos = date.today() - timedelta(days=800)
        d.ingreso.setDate(QDate(hace_dos.year, hace_dos.month, hace_dos.day))
        d._guardar_expediente()
        self.assertTrue(d.btn_registrar.isEnabled())
        ini = date.today() + timedelta(days=20)
        fin = ini + timedelta(days=6)
        d.desde.setDate(QDate(ini.year, ini.month, ini.day))
        d.hasta.setDate(QDate(fin.year, fin.month, fin.day))
        d._registrar()
        with self.F() as s:
            sol = s.query(SolicitudVacaciones).one()
            self.assertEqual((sol.estado, sol.resuelto_por), (vs.APROBADO, "VEND-1"))
            self.assertEqual(s.query(EmpleadaEvento).filter(EmpleadaEvento.tipo == "vacaciones").count(), 6)
        self.assertEqual(d.solicitudes.rowCount(), 1)
        d._cambiar_autoservicio(True)
        with self.F() as s:
            self.assertTrue(s.get(ExpedienteVacacional, "VEND-5").autoservicio)


class LibretaVisibleTests(_Base):
    """Cómo se verá cuando se estrene (EN_CONSTRUCCION=False). Hoy está
    oculto para todos: ver `NadieLoVeMientrasEsteEnObraTests`."""

    def setUp(self) -> None:
        super().setUp()
        p = mock.patch.object(vs, "EN_CONSTRUCCION", False)
        p.start()
        self.addCleanup(p.stop)

    def _ventana(self, code):
        from PyQt6.QtWidgets import QLabel, QPushButton

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        w = SimpleNamespace(
            _libreta_code=code, libreta_descanso_button=QPushButton(), libreta_descanso_aviso=QLabel(),
            libreta_vacaciones_button=QPushButton(),
        )
        self.widgets += [w.libreta_descanso_button, w.libreta_descanso_aviso, w.libreta_vacaciones_button]
        w._libreta_vacaciones_refrescar = lambda b, c: QuoteSatelliteWindow._libreta_vacaciones_refrescar(w, b, c)
        F = self.F

        @contextmanager
        def _sesion():
            with F() as s:
                yield s

        with mock.patch("pos_uniformes.ui.quote_satellite_window.get_session", _sesion):
            QuoteSatelliteWindow._libreta_descanso_refrescar(w)
        return w

    def test_daniel_ve_el_panel_del_equipo(self) -> None:
        w = self._ventana("VEND-1")
        self.assertFalse(w.libreta_vacaciones_button.isHidden())
        self.assertIn("equipo", w.libreta_vacaciones_button.text())

    def test_ella_no_ve_nada_hasta_que_daniel_se_lo_abre(self) -> None:
        self.assertTrue(self._ventana("VEND-5").libreta_vacaciones_button.isHidden())
        with self.F() as s:
            vs.capturar_expediente(s, "VEND-5", fecha_ingreso=date(2024, 3, 1), quien="VEND-1")
            s.commit()
        self.assertTrue(self._ventana("VEND-5").libreta_vacaciones_button.isHidden())
        with self.F() as s:
            vs.habilitar_autoservicio(s, "VEND-5", True, quien="VEND-1")
            s.commit()
        self.assertFalse(self._ventana("VEND-5").libreta_vacaciones_button.isHidden())


class NadieLoVeMientrasEsteEnObraTests(LibretaVisibleTests):
    """Daniel, 2026-10-13: «lo de vacaciones lo dejaremos oculto o en
    construcción». Ni él ve el panel, ni ella su botón aunque se lo hubieran abierto."""

    def setUp(self) -> None:
        super().setUp()
        p = mock.patch.object(vs, "EN_CONSTRUCCION", True)
        p.start()
        self.addCleanup(p.stop)

    def test_daniel_ve_el_panel_del_equipo(self) -> None:
        self.assertTrue(self._ventana("VEND-1").libreta_vacaciones_button.isHidden())

    def test_ella_no_ve_nada_hasta_que_daniel_se_lo_abre(self) -> None:
        with self.F() as s:
            vs.capturar_expediente(s, "VEND-5", fecha_ingreso=date(2024, 3, 1), quien="VEND-1")
            vs.habilitar_autoservicio(s, "VEND-5", True, quien="VEND-1")
            s.commit()
        self.assertTrue(self._ventana("VEND-5").libreta_vacaciones_button.isHidden())


if __name__ == "__main__":
    unittest.main()
