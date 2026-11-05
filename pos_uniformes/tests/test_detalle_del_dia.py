"""El calendario cuenta lo que pasó un día pasado y lo que viene en uno futuro.

Daniel, 2026-11-05: «no puedo ver los detalles de pasado, ni los del futuro».
Cualquier día que no fuera hoy solo decía «día normal de trabajo».
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EmpleadaHorario, EmpleadaPago, LibretaVenta
from pos_uniformes.services import nomina_service as nomina

HOY = date(2026, 11, 5)           # jueves
PAGO = date(2026, 11, 1)          # domingo: el último pago


def _venta(dia: date, comisiones: int) -> LibretaVenta:
    return LibretaVenta(
        employee_code="VEND-4", employee_name="Stayce", piezas=comisiones, comisiones=comisiones,
        created_at=datetime.combine(dia, time(12, 0)).astimezone(),
    )


class DetalleDelDiaTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = sessionmaker(bind=engine)()
        self.s.add(EmpleadaHorario(employee_code="VEND-4", descanso_weekday=5, fecha_ultimo_pago=PAGO))
        self.s.add(EmpleadaPago(
            employee_code="VEND-4", employee_name="Stayce", fecha=PAGO,
            desde=PAGO - timedelta(days=6), hasta=PAGO, comisiones=83,
            sueldo_base=Decimal("1300.00"), tarifa_comision=Decimal("2.00"), monto_comisiones=Decimal("166.00"),
            faltas=0, descuento_faltas=Decimal("0.00"), descuento_prestamos=Decimal("30.00"),
            total=Decimal("1436.00"), creado_por="VEND-1",
        ))
        self.s.add_all([_venta(date(2026, 10, 28), 7), _venta(date(2026, 10, 28), 5), _venta(date(2026, 11, 3), 1)])
        self.s.commit()

    def tearDown(self) -> None:
        self.s.close()

    def _detalle(self, dia: date) -> str:
        return "\n".join(nomina.detalle_del_dia(self.s, "vend-4", dia, HOY))

    def test_un_dia_pasado_dice_sus_comisiones_y_en_que_pago_entro(self) -> None:
        texto = self._detalle(date(2026, 10, 28))
        self.assertIn("12 comisiones en 2 ventas", texto)
        self.assertIn("Entró en el pago del domingo 1 de nov ($1,436.00)", texto)

    def test_el_dia_del_pago_trae_el_desglose(self) -> None:
        texto = self._detalle(PAGO)
        self.assertIn("Se le pagaron $1,436.00", texto)
        self.assertIn("sueldo $1,300.00 + 83 comisiones $166.00 − préstamo $30.00", texto)
        self.assertIn("cubre del lunes 26 de oct al domingo 1 de nov", texto)
        self.assertIn("Sin ventas apuntadas", texto)

    def test_un_dia_pasado_que_aun_no_se_paga_dice_cuando(self) -> None:
        texto = self._detalle(date(2026, 11, 3))
        self.assertIn("1 comisión en 1 venta", texto)
        self.assertIn("Todavía no se paga: va en el pago del domingo 8 de nov", texto)

    def test_el_proximo_dia_de_pago_dice_cuanto_lleva(self) -> None:
        texto = self._detalle(date(2026, 11, 8))
        self.assertIn("Ese día le toca cobrar", texto)
        self.assertIn("hasta hoy lleva 1 comisión: serían $", texto)

    def test_un_dia_futuro_cualquiera_dice_en_que_pago_cae(self) -> None:
        self.assertIn("se paga el domingo 15 de nov", self._detalle(date(2026, 11, 11)))
        # Y el pago de más adelante se anuncia, pero sin inventar un monto.
        lejos = self._detalle(date(2026, 11, 15))
        self.assertIn("Ese día le toca cobrar", lejos)
        self.assertNotIn("serían", lejos)


if __name__ == "__main__":
    unittest.main()
