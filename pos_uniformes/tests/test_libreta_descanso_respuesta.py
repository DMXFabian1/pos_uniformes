"""La Libreta le dice a ELLA qué pasó con su descanso, y deja de esconder el botón.

Antes: una solicitud sin contestar cuyo día ya pasó escondía el botón de
pedir para siempre, y cuando Daniel contestaba el botón solo reaparecía sin
decir si fue un sí o un no (auditoría 2026-10-12).
"""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Empleada, EmpleadaHorario, SolicitudDescanso
from pos_uniformes.services import descansos_service as ds


class LibretaDescansoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from PyQt6.QtWidgets import QLabel, QPushButton

        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add(Empleada(codigo="VEND-5", nombre_completo="Cristal Torres", activo=True))
        self.s.add(EmpleadaHorario(employee_code="VEND-5", descanso_weekday=6))
        self.s.commit()
        self.hoy = date.today()
        self.w = SimpleNamespace(
            _libreta_code="VEND-5",
            libreta_descanso_button=QPushButton(),
            libreta_descanso_aviso=QLabel(),
            libreta_descanso_respuesta=QLabel(),
            libreta_descanso_visto_button=QPushButton(),
        )
        self.w._libreta_descanso_refrescar = (
            lambda: QuoteSatelliteWindow._libreta_descanso_refrescar(self.w)
        )
        self.refrescar = self.w._libreta_descanso_refrescar
        self.visto = lambda: QuoteSatelliteWindow._libreta_descanso_visto(self.w)

        @contextmanager
        def _sesion():
            yield self.s

        self._parche = mock.patch(
            "pos_uniformes.ui.quote_satellite_window.get_session", _sesion
        )
        self._parche.start()

    def tearDown(self) -> None:
        self._parche.stop()
        for widget in vars(self.w).values():
            if hasattr(widget, "deleteLater"):
                widget.deleteLater()
        self.s.close()

    def _solicitud(self, fecha, estado=ds.PEDIDO):
        s = SolicitudDescanso(employee_code="VEND-5", employee_name="Cristal", fecha=fecha,
                              motivo="Escuela", estado=estado, tipo="cambio")
        self.s.add(s)
        self.s.commit()
        return s

    def test_una_vieja_sin_contestar_ya_no_esconde_el_boton(self) -> None:
        self._solicitud(self.hoy - timedelta(days=2))
        self.refrescar()
        self.assertFalse(self.w.libreta_descanso_button.isHidden())

    def test_la_que_espera_esconde_el_boton_y_lo_dice(self) -> None:
        self._solicitud(self.hoy + timedelta(days=9))
        self.refrescar()
        self.assertTrue(self.w.libreta_descanso_button.isHidden())
        self.assertIn("todavía no responde", self.w.libreta_descanso_aviso.text())

    def test_la_respuesta_se_le_dice_hasta_que_la_lee(self) -> None:
        s = self._solicitud(self.hoy + timedelta(days=9))
        ds.rechazar(self.s, s.id, quien="VEND-1", respuesta="Hay conteo")
        self.s.commit()
        self.refrescar()
        self.assertFalse(self.w.libreta_descanso_respuesta.isHidden())
        self.assertIn("no aprobó", self.w.libreta_descanso_respuesta.text())
        self.assertIn("Hay conteo", self.w.libreta_descanso_respuesta.text())
        self.visto()
        self.assertTrue(self.w.libreta_descanso_respuesta.isHidden())
        self.s.expire_all()
        self.assertIsNotNone(self.s.get(SolicitudDescanso, s.id).avisada_at)


if __name__ == "__main__":
    unittest.main()
