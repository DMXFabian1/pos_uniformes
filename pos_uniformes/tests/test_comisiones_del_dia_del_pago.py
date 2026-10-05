"""Las comisiones de la tarde en que se cobró no se pierden.

A Cristal se le pagó el 3-oct a las 09:13 y siguió vendiendo todo el día: esas
11 comisiones no entraron en su pago (no existían todavía) y tampoco en el
siguiente, que empezaba el 4-oct. Nadie las borró — cayeron en el hueco entre
"el pago cubre este día completo" y "el ciclo nuevo empieza mañana"
(Daniel, 2026-10-05).
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EmpleadaPago, LibretaVenta
from pos_uniformes.services.calendario_empleadas_service import (
    HorarioEmpleada,
    comisiones_desde_ultimo_pago,
)

CODE = "VEND-5"
DIA = date(2026, 10, 3)


class ComisionesDelDiaDelPagoTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)

    def _pago(self, *, fecha=DIA, hora=9, minuto=13):
        pago = EmpleadaPago(
            employee_code=CODE, employee_name="Cristal Torres", fecha=fecha,
            desde=fecha, hasta=fecha, comisiones=59, sueldo_base=Decimal("1300.00"), tarifa_comision=Decimal("2.00"),
            monto_comisiones=Decimal("118.00"), faltas=0, descuento_faltas=Decimal("0.00"),
            total=Decimal("1358.00"), creado_por="VEND-1",
            created_at=datetime(DIA.year, DIA.month, DIA.day, hora, minuto, tzinfo=timezone.utc),
        )
        self.s.add(pago)
        self.s.flush()
        return pago

    def _venta(self, *, hora, comisiones, dia=DIA):
        self.s.add(LibretaVenta(
            employee_code=CODE, employee_name="Cristal Torres", comisiones=comisiones,
            piezas=comisiones, monto_total=Decimal("0.00"),
            created_at=datetime(dia.year, dia.month, dia.day, hora, 0, tzinfo=timezone.utc),
        ))
        self.s.flush()

    def _horario(self):
        return HorarioEmpleada(CODE, fecha_ultimo_pago=DIA)

    def test_lo_que_vendio_despues_de_cobrar_cuenta_para_el_siguiente(self) -> None:
        self._pago()
        self._venta(hora=10, comisiones=1)
        self._venta(hora=12, comisiones=2)
        self._venta(hora=13, comisiones=2)
        self._venta(hora=15, comisiones=6)
        self.assertEqual(comisiones_desde_ultimo_pago(self.s, CODE, self._horario()), 11)

    def test_lo_que_vendio_antes_de_cobrar_no_se_paga_dos_veces(self) -> None:
        """Eso ya iba en el pago que acaba de recibir."""
        self._pago()
        self._venta(hora=8, comisiones=4)
        self.assertEqual(comisiones_desde_ultimo_pago(self.s, CODE, self._horario()), 0)

    def test_el_dia_siguiente_cuenta_igual_que_siempre(self) -> None:
        self._pago()
        self._venta(hora=11, comisiones=3, dia=DIA + timedelta(days=1))
        self.assertEqual(comisiones_desde_ultimo_pago(self.s, CODE, self._horario()), 3)

    def test_un_pago_de_otra_fecha_no_usa_su_hora(self) -> None:
        """Un pago adelantado o atrasado se captura un día y cubre otro: ahí la
        hora de captura no dice nada, y manda el día siguiente a la fecha."""
        self._pago(fecha=DIA - timedelta(days=5))
        self._venta(hora=10, comisiones=7)
        horario = HorarioEmpleada(CODE, fecha_ultimo_pago=DIA - timedelta(days=5))
        self.assertEqual(comisiones_desde_ultimo_pago(self.s, CODE, horario), 7)

    def test_sin_ningun_pago_se_cuenta_todo(self) -> None:
        self._venta(hora=10, comisiones=5)
        self.assertEqual(
            comisiones_desde_ultimo_pago(self.s, CODE, HorarioEmpleada(CODE)), 5
        )

    def test_un_pago_capturado_de_noche_no_arrastra_el_dia_siguiente(self) -> None:
        """Si se pagó a las 23:50, el corte sigue siendo el cambio de día: no
        se cuentan las comisiones de la mañana siguiente como si fueran de hoy."""
        self._pago(hora=23, minuto=50)
        self._venta(hora=9, comisiones=4, dia=DIA + timedelta(days=1))
        self.assertEqual(comisiones_desde_ultimo_pago(self.s, CODE, self._horario()), 4)


if __name__ == "__main__":
    unittest.main()
