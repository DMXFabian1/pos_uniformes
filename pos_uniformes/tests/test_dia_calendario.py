"""Detalle del día en el calendario del kiosko + consulta de pago con gafete."""

from __future__ import annotations

import os
import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pos_uniformes.database.models import Empleada, EmpleadaEvento, EmpleadaHorario
from pos_uniformes.services import dia_calendario_service as svc
from pos_uniformes.services.calendario_empleadas_service import (
    DESCANSO,
    MODO_POR_DIA,
    PAGO,
    chips_calendario_mes,
    guardar_horario,
)
from pos_uniformes.services.nomina_service import DetallePago

HOY = date(2026, 9, 9)  # miércoles


def _factory():
    engine = create_engine("sqlite://")
    Empleada.__table__.create(engine)
    EmpleadaHorario.__table__.create(engine)
    EmpleadaEvento.__table__.create(engine)
    return sessionmaker(bind=engine)


def _seed(s):
    s.add_all([
        Empleada(codigo="VEND-1", nombre_completo="Daniel Fabian", activo=True),
        Empleada(codigo="ENC-1", nombre_completo="Encargado Prueba", activo=True),
        Empleada(codigo="VEND-2", nombre_completo="Fanny López", activo=True),
        Empleada(codigo="VEND-6", nombre_completo="Nayeli Ruiz", activo=True),
        Empleada(codigo="VEND-9", nombre_completo="Lupita Baja", activo=False),
    ])
    s.commit()
    guardar_horario(s, "VEND-2", descanso_weekday=1, ciclo_dias_pago=7, fecha_ultimo_pago=date(2026, 9, 4), actualizar_ultimo_pago=True)
    guardar_horario(s, "VEND-6", descanso_weekday=None, ciclo_dias_pago=7, modo_pago=MODO_POR_DIA, dias_trabajo=[5, 6], fecha_ultimo_pago=date(2026, 9, 6), actualizar_ultimo_pago=True)


def _detalle(code, total_base="1300.00", com=10, faltas=0, por_dia=False):
    return DetallePago(
        employee_code=code, desde=date(2026, 9, 5), hasta=HOY, comisiones=com,
        sueldo_base=Decimal(total_base), tarifa_comision=Decimal("2.00"), faltas=faltas,
        descuento_falta=Decimal("216.67"),
        dias_trabajados=2 if por_dia else None, tarifa_dia=Decimal("216.67") if por_dia else None,
    )


class ChipsPorDiaTests(unittest.TestCase):
    def test_naye_no_aparece_descansando_entre_semana(self) -> None:
        with _factory()() as s:
            _seed(s)
            chips = chips_calendario_mes(s, 2026, 9, HOY)
        # Fanny descansa los martes; Naye (por días) no ensucia ningún día con "descanso".
        self.assertIn((DESCANSO, "Fanny"), chips[date(2026, 9, 8)])
        for fecha, lista in chips.items():
            self.assertNotIn((DESCANSO, "Nayeli"), lista, fecha)
        # Pero su pago sí se proyecta (último día de su patrón: domingo 13).
        self.assertIn((PAGO, "Nayeli"), chips[date(2026, 9, 13)])


    def test_las_faltas_tambien_salen_en_el_calendario(self) -> None:
        """Daniel las quiso visibles (2026-09-09): el encargado apunta y todos ven."""
        from pos_uniformes.services.calendario_empleadas_service import FALTA, marcar_dia

        with _factory()() as s:
            _seed(s)
            marcar_dia(s, "VEND-2", date(2026, 9, 10), FALTA, nota="apuntada por ENC-1")
            s.commit()
            chips = chips_calendario_mes(s, 2026, 9, HOY)
        self.assertIn((FALTA, "Fanny"), chips[date(2026, 9, 10)])

    def test_una_falta_no_se_confunde_con_descanso(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import FALTA, marcar_dia

        with _factory()() as s:
            _seed(s)
            marcar_dia(s, "VEND-2", date(2026, 9, 10), FALTA)
            s.commit()
            chips = chips_calendario_mes(s, 2026, 9, HOY)
        del_dia = chips[date(2026, 9, 10)]
        self.assertNotIn((DESCANSO, "Fanny"), del_dia)


class ResumenDiaTests(unittest.TestCase):
    def test_el_detalle_del_dia_lista_las_faltas(self) -> None:
        from pos_uniformes.services.calendario_empleadas_service import FALTA, marcar_dia

        with _factory()() as s:
            _seed(s)
            marcar_dia(s, "VEND-2", date(2026, 9, 10), FALTA)
            s.commit()
            r = svc.resumen_dia(s, date(2026, 9, 10), HOY)
        self.assertEqual(r.faltas, ["Fanny"])
        self.assertEqual(r.descansan, [])
        self.assertFalse(r.vacio)  # un día con solo faltas ya no está vacío

    def test_resumen_del_dia(self) -> None:
        conteo = SimpleNamespace(escuela_nombre="Primaria Juárez", vencida=True)
        with _factory()() as s, patch(
            "pos_uniformes.services.conteo_calendario_service.obtener_calendario_conteo", return_value=[conteo]
        ), patch(
            "pos_uniformes.services.conteo_calendario_service.agrupar_calendario_por_dia", return_value={8: [conteo]}
        ):
            _seed(s)
            r = svc.resumen_dia(s, date(2026, 9, 8), HOY)
        self.assertEqual(r.descansan, ["Fanny"])
        self.assertEqual([c.escuela_nombre for c in r.conteos], ["Primaria Juárez"])
        self.assertFalse(r.vacio)
        self.assertEqual(svc.fecha_en_palabras(date(2026, 9, 8)), "Martes 8 de septiembre de 2026")


class VistaDePagosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = _factory()
        self._p = patch.object(
            svc, "_pago_vista",
            side_effect=lambda s, e, hoy: svc.PagoVista(str(e.codigo), e.nombre_completo, _detalle(e.codigo), date(2026, 9, 11), True),
        )
        self._p.start()

    def tearDown(self) -> None:
        self._p.stop()

    def test_empleada_ve_solo_el_suyo(self) -> None:
        with self.factory() as s:
            _seed(s)
            v = svc.vista_de_pagos(s, "EMPÑVEND-2", HOY)  # teclado español: Ñ = :
        self.assertFalse(v.todas)
        self.assertEqual(v.quien, "Fanny")
        self.assertEqual([p.employee_code for p in v.pagos], ["VEND-2"])

    def test_dueno_y_encargado_ven_todas_sin_ellos(self) -> None:
        with self.factory() as s:
            _seed(s)
            for gafete in ("EMP:VEND-1", "ENC-1"):
                v = svc.vista_de_pagos(s, gafete, HOY)
                self.assertTrue(v.todas)
                self.assertEqual(sorted(p.employee_code for p in v.pagos), ["VEND-2", "VEND-6"])

    def test_codigos_invalidos(self) -> None:
        with self.factory() as s:
            _seed(s)
            self.assertIsNone(svc.vista_de_pagos(s, "SKU004838", HOY))
            self.assertIsNone(svc.vista_de_pagos(s, "EMP:VEND-9", HOY))  # de baja
            self.assertIsNone(svc.vista_de_pagos(s, "   ", HOY))


class LineasPagoTests(unittest.TestCase):
    def test_semana_con_falta(self) -> None:
        p = svc.PagoVista("VEND-2", "Fanny López", _detalle("VEND-2", com=45, faltas=1), date(2026, 9, 11), True)
        lineas = svc.lineas_pago(p, HOY)
        self.assertEqual(lineas[0], "Sueldo: $1,300.00")
        self.assertEqual(lineas[1], "45 comisiones × $2.00 = $90.00")
        self.assertEqual(lineas[2], "1 falta(s): −$216.67")
        self.assertEqual(lineas[3], "TOTAL HOY: $1,173.33")
        self.assertEqual(lineas[4], "Te toca cobrar el viernes 11 de septiembre.")

    def test_por_dia_y_atrasado(self) -> None:
        p = svc.PagoVista("VEND-6", "Nayeli", _detalle("VEND-6", "433.34", com=3, por_dia=True), date(2026, 9, 6), False)
        lineas = svc.lineas_pago(p, HOY)
        self.assertIn("Sin horario configurado", lineas[0])
        self.assertEqual(lineas[1], "2 día(s) × $216.67 = $433.34")
        self.assertIn("(atrasado)", lineas[-1])


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _dlg(self):
        from pos_uniformes.ui.dialogs.dia_calendario_dialog import DiaCalendarioDialog

        resumen = svc.ResumenDia(date(2026, 9, 8), descansan=["Fanny"], pagos=[], conteos=[SimpleNamespace(escuela_nombre="Juárez", vencida=False)])
        with patch.object(DiaCalendarioDialog, "_cargar_resumen", return_value=resumen):
            return DiaCalendarioDialog(None, date(2026, 9, 8), hoy=HOY)

    def test_tarjetas_y_pago_propio(self) -> None:
        from PyQt6.QtWidgets import QLabel

        dlg = self._dlg()
        textos = [w.text() for w in dlg.findChildren(QLabel)]
        self.assertIn("Fanny", textos)
        self.assertIn("Juárez", textos)
        self.assertFalse(dlg.pago_box.isVisible())
        vista = svc.VistaPagos(False, "Fanny", [svc.PagoVista("VEND-2", "Fanny López", _detalle("VEND-2", com=45), date(2026, 9, 11), True)])
        with patch.object(dlg, "_consultar_pagos", return_value=vista):
            dlg.scan_input.setText("EMP:VEND-2")
            dlg.scan_input.returnPressed.emit()
        self.assertTrue(dlg.pago_box.isVisibleTo(dlg))
        textos = [w.text() for w in dlg.pago_box.findChildren(QLabel)]
        self.assertIn("TOTAL HOY: $1,390.00", textos)
        self.assertEqual(dlg.scan_input.text(), "")
        self.assertTrue(dlg._timer_ocultar.isActive())
        dlg.ocultar_pago()
        self.assertFalse(dlg.pago_box.isVisibleTo(dlg))

    def test_todas_en_tabla_y_codigo_invalido(self) -> None:
        from PyQt6.QtWidgets import QTableWidget

        dlg = self._dlg()
        vista = svc.VistaPagos(True, "Daniel", [
            svc.PagoVista("VEND-2", "Fanny López", _detalle("VEND-2"), date(2026, 9, 11), True),
            svc.PagoVista("VEND-6", "Nayeli Ruiz", _detalle("VEND-6", "433.34", por_dia=True), HOY, True),
        ])
        with patch.object(dlg, "_consultar_pagos", return_value=vista):
            dlg.scan_input.setText("EMP:VEND-1")
            dlg.scan_input.returnPressed.emit()
        tabla = dlg.pago_box.findChildren(QTableWidget)[0]
        self.assertEqual(tabla.rowCount(), 2)
        self.assertEqual(tabla.item(0, 0).text(), "Fanny")
        self.assertEqual(tabla.item(1, 1).text(), "2 d × $216.67")
        self.assertEqual(tabla.item(1, 5).text(), "hoy")
        with patch.object(dlg, "_consultar_pagos", return_value=None):
            dlg.scan_input.setText("SKU1")
            dlg.scan_input.returnPressed.emit()
        self.assertTrue(dlg.error_label.isVisibleTo(dlg))
        self.assertIn("no es un gafete", dlg.error_label.text())


class PanelClickTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_clic_en_dia_abre_detalle(self) -> None:
        from pos_uniformes.ui.dialogs.conteo_calendario_mes_panel import ConteoCalendarioMesPanel

        panel = ConteoCalendarioMesPanel(None, session_factory=lambda: None, hoy=HOY, refresh_on_init=False)
        panel._render()
        abiertos = []
        with patch("pos_uniformes.ui.dialogs.dia_calendario_dialog.DiaCalendarioDialog") as Dlg:
            Dlg.return_value.exec.side_effect = lambda: abiertos.append(Dlg.call_args.args[1])
            panel._agregar_recordatorio_en(date(2026, 9, 8))
        self.assertEqual(abiertos, [date(2026, 9, 8)])


if __name__ == "__main__":
    unittest.main()
