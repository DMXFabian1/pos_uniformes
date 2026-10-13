"""La ventana «Mis vacaciones»: lo que ella ve y lo que pasa al cerrar."""

from __future__ import annotations

import os
import unittest
from datetime import date, timedelta
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import CajaParametros, Empleada, EmpleadaHorario, SolicitudVacaciones
from pos_uniformes.services import vacaciones_service as vs


def _con_autoservicio(session, code, **kw):
    """Expediente + autoservicio abierto: estas pruebas son de ella pidiendo."""
    exp = vs.capturar_expediente(session, code, **kw)
    vs.habilitar_autoservicio(session, code, True, quien="VEND-1")
    return exp


class VacacionesDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.F = sessionmaker(bind=engine)
        hoy = date.today()
        with self.F() as s:
            s.add(Empleada(codigo="VEND-5", nombre_completo="Cristal Torres", activo=True))
            s.add(EmpleadaHorario(employee_code="VEND-5", descanso_weekday=6))
            s.add(CajaParametros(sueldo_base=Decimal("1300")))
            s.commit()
            _con_autoservicio(s, "VEND-5", fecha_ingreso=hoy - timedelta(days=800), quien="VEND-1")
            vs.generar_periodos(s, "VEND-5", hoy=hoy)
            b = vs.pedir(s, employee_code="VEND-5", nombre="C", desde=hoy + timedelta(days=40),
                         hasta=hoy + timedelta(days=41), hoy=hoy)
            vs.rechazar(s, b.id, quien="VEND-1", respuesta="Temporada alta")
            s.commit()
            self.sid = b.id
        self.dialogos = []

    def tearDown(self) -> None:
        for d in self.dialogos:
            d.deleteLater()

    def _abrir(self, code):
        from pos_uniformes.ui.dialogs.vacaciones_dialog import VacacionesDialog

        d = VacacionesDialog(None, employee_code=code, nombre="x", session_factory=self.F)
        self.dialogos.append(d)
        return d

    def test_sin_expediente_no_deja_pedir_y_dice_por_que(self) -> None:
        d = self._abrir("VEND-9")
        self.assertFalse(d.btn_pedir.isEnabled())
        self.assertIn("pendiente de completar", d.resumen.text())

    def test_muestra_saldo_y_la_respuesta_y_al_cerrar_queda_vista(self) -> None:
        d = self._abrir("VEND-5")
        self.assertIn("disponibles", d.resumen.text())
        self.assertIn("Temporada alta", d.respuestas.text())
        self.assertTrue(d.btn_pedir.isEnabled())
        d.accept()
        with self.F() as s:
            self.assertIsNotNone(s.get(SolicitudVacaciones, self.sid).avisada_at)


if __name__ == "__main__":
    unittest.main()
