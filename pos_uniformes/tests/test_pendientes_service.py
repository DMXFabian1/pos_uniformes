"""Pendientes del día: pagos, posibles faltas, descansos y horarios sin configurar."""

from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pos_uniformes.services import pendientes_service as svc
from pos_uniformes.services.calendario_empleadas_service import FALTA, HorarioEmpleada
from pos_uniformes.services.nomina_service import AvisoPago
from pos_uniformes.services.pendientes_service import (
    DESCANSO_HOY,
    PAGO_ATRASADO,
    PAGO_HOY,
    POSIBLE_FALTA,
    SIN_HORARIO,
    Pendiente,
    texto_pendientes,
)

HOY = date(2026, 9, 9)  # miércoles


def _emp(code, nombre):
    return SimpleNamespace(codigo=code, nombre_completo=nombre, activo=True)


class PendientesDelDiaTests(unittest.TestCase):
    def _session(self, empleadas, con_movimientos):
        session = MagicMock()
        q_emp = MagicMock()
        q_emp.filter.return_value.order_by.return_value.all.return_value = empleadas
        q_mov = MagicMock()
        q_mov.filter.return_value.distinct.return_value.all.return_value = [(c,) for c in con_movimientos]
        session.query.side_effect = lambda *a: q_emp if a and getattr(a[0], "__name__", "") == "Empleada" else q_mov
        return session

    def test_detecta_todo(self) -> None:
        empleadas = [_emp("VEND-2", "Ana López"), _emp("VEND-3", "Bety Ruiz"), _emp("VEND-4", "Caro Díaz"), _emp("VEND-5", "Dani Nueva"), _emp("ENC-1", "Encargado Prueba")]
        horarios = {
            "VEND-2": HorarioEmpleada("VEND-2", descanso_weekday=2, fecha_ultimo_pago=date(2026, 9, 2)),  # descansa miércoles
            "VEND-3": HorarioEmpleada("VEND-3", descanso_weekday=6, fecha_ultimo_pago=date(2026, 9, 2)),  # trabaja, sin movimientos
            "VEND-4": HorarioEmpleada("VEND-4", descanso_weekday=6, fecha_ultimo_pago=date(2026, 8, 30)),  # pago atrasado, con ventas
            "VEND-5": HorarioEmpleada("VEND-5"),  # sin configurar
        }
        avisos = [
            AvisoPago("VEND-3", "Bety Ruiz", HOY, 0, 12, Decimal("1324.00")),
            AvisoPago("VEND-4", "Caro Díaz", date(2026, 9, 6), -3, 30, Decimal("1360.00")),
        ]
        session = self._session(empleadas, ["VEND-4"])
        with patch.object(svc, "date") if False else patch(
            "pos_uniformes.services.calendario_empleadas_service.cargar_horario",
            side_effect=lambda _s, code: horarios[code.upper()],
        ), patch("pos_uniformes.services.nomina_service.avisos_de_pago", return_value=avisos), patch(
            "pos_uniformes.services.libreta_service.ventana_hoy", return_value=(datetime(2026, 9, 9), datetime(2026, 9, 9, 23, 59))
        ):
            pend = svc.pendientes_del_dia(session, HOY, ahora=datetime(2026, 9, 9, 15, 0))
        tipos = [(p.tipo, p.employee_code) for p in pend]
        self.assertEqual(tipos, [
            (PAGO_ATRASADO, "VEND-4"),
            (PAGO_HOY, "VEND-3"),
            (POSIBLE_FALTA, "VEND-3"),
            (SIN_HORARIO, "VEND-5"),
            (DESCANSO_HOY, "VEND-2"),
        ])
        self.assertIn("atrasado 3 día(s): $1,360.00", pend[0].texto)
        self.assertIn("Hoy toca pagar a Bety: $1,324.00", pend[1].texto)
        self.assertIn("¿Faltó?", pend[2].texto)
        self.assertIn("descanso fijo ni fecha del último pago", pend[3].texto)

    def test_antes_de_la_una_no_sugiere_faltas_y_falta_apuntada_no_se_repite(self) -> None:
        empleadas = [_emp("VEND-3", "Bety Ruiz"), _emp("VEND-6", "Eli")]
        h6 = HorarioEmpleada("VEND-6", descanso_weekday=6, fecha_ultimo_pago=date(2026, 9, 2))
        h6.eventos[HOY] = FALTA
        horarios = {"VEND-3": HorarioEmpleada("VEND-3", descanso_weekday=6, fecha_ultimo_pago=date(2026, 9, 2)), "VEND-6": h6}
        session = self._session(empleadas, [])
        with patch(
            "pos_uniformes.services.calendario_empleadas_service.cargar_horario",
            side_effect=lambda _s, code: horarios[code.upper()],
        ), patch("pos_uniformes.services.nomina_service.avisos_de_pago", return_value=[]), patch(
            "pos_uniformes.services.libreta_service.ventana_hoy", return_value=(datetime(2026, 9, 9), datetime(2026, 9, 9, 23, 59))
        ):
            temprano = svc.pendientes_del_dia(session, HOY, ahora=datetime(2026, 9, 9, 10, 0))
            tarde = svc.pendientes_del_dia(session, HOY, ahora=datetime(2026, 9, 9, 16, 0))
        self.assertEqual(temprano, [])
        self.assertEqual([(p.tipo, p.employee_code) for p in tarde], [(POSIBLE_FALTA, "VEND-3")])


class TextoPendientesTests(unittest.TestCase):
    def test_texto(self) -> None:
        t = texto_pendientes([
            Pendiente(PAGO_ATRASADO, "VEND-4", "Caro Díaz", "Pago de Caro atrasado 3 día(s): $1,360.00"),
            Pendiente(POSIBLE_FALTA, "VEND-3", "Bety Ruiz", "Bety no tiene movimientos hoy. ¿Faltó?"),
            Pendiente(DESCANSO_HOY, "VEND-2", "Ana López", "Ana descansa hoy"),
        ])
        self.assertTrue(t.startswith("📌 PENDIENTES"))
        self.assertIn("❗ Pago de Caro atrasado", t)
        self.assertIn("❓ Bety no tiene movimientos", t)
        self.assertIn("🛌 Descansa hoy: Ana", t)

    def test_vacio(self) -> None:
        self.assertEqual(texto_pendientes([]), "")


if __name__ == "__main__":
    unittest.main()
