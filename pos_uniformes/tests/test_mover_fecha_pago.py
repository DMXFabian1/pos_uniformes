"""Corregir el día de un pago que se registró tarde (Stayce, 2026-10-20)."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import EmpleadaEvento, EmpleadaHorario, EmpleadaPago, LibretaVenta
from pos_uniformes.services import nomina_service as nom
from pos_uniformes.services.calendario_empleadas_service import PAGO

LUNES, DOMINGO = date(2026, 10, 19), date(2026, 10, 18)


class MoverFechaPagoTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add(EmpleadaHorario(employee_code="VEND-4", descanso_weekday=5, fecha_ultimo_pago=LUNES))
        self.pago = EmpleadaPago(
            employee_code="VEND-4", employee_name="Stayce", fecha=LUNES, desde=date(2026, 10, 12), hasta=LUNES,
            total=Decimal("1476.00"), comisiones=103, tarifa_comision=Decimal("2.00"),
            monto_comisiones=Decimal("206.00"), creado_por="VEND-1",
            created_at=datetime(2026, 10, 19, 17, 14, tzinfo=timezone(timedelta(hours=-6))),
        )
        self.s.add(self.pago)
        self.s.add(EmpleadaEvento(employee_code="VEND-4", fecha=LUNES, tipo=PAGO))
        # Lo que vendió: 83 piezas en la semana y 20 el lunes antes de capturar el pago.
        self._vende(datetime(2026, 10, 14, 12, 0), 83)
        self._vende(datetime(2026, 10, 19, 11, 0), 20)
        self.s.flush()

    def _vende(self, cuando: datetime, piezas: int) -> None:
        self.s.add(LibretaVenta(employee_code="VEND-4", employee_name="Stayce", piezas=piezas, comisiones=piezas,
                                created_at=cuando.astimezone()))

    def _marcas(self) -> list[date]:
        return sorted(e.fecha for e in self.s.query(EmpleadaEvento).filter_by(employee_code="VEND-4", tipo=PAGO).all())

    def test_el_caso_de_stayce(self) -> None:
        r = nom.mover_fecha_pago(self.s, self.pago.id, DOMINGO, creado_por="VEND-1")
        self.assertEqual((r["de"], r["a"], r["ciclo_movido"]), (LUNES, DOMINGO, True))
        self.assertEqual(self.pago.fecha, DOMINGO)
        self.assertEqual(self._marcas(), [DOMINGO])                              # la marca verde se movió
        self.assertEqual(self.s.get(EmpleadaHorario, "VEND-4").fecha_ultimo_pago, DOMINGO)
        self.assertEqual(self.pago.created_at.hour, 17)                          # cuándo se capturó, intacto
        self.assertEqual(self.pago.hasta, DOMINGO)
        # Las 20 del lunes se le quitan al pago: el domingo no existían.
        self.assertEqual((r["comisiones_de"], r["comisiones_a"]), (103, 83))
        self.assertEqual((self.pago.comisiones, self.pago.monto_comisiones, self.pago.total),
                         (83, Decimal("166.00"), Decimal("1436.00")))

    def test_las_comisiones_ya_pagadas_no_se_vuelven_a_contar(self) -> None:
        # El siguiente ciclo arranca el lunes a las 00:00: las 20 del lunes se
        # cuentan ahí (y ya no en el pago), ni perdidas ni dobles.
        from pos_uniformes.services.calendario_empleadas_service import (
            _corte_de_comisiones, cargar_horario, comisiones_desde_ultimo_pago,
        )

        nom.mover_fecha_pago(self.s, self.pago.id, DOMINGO, creado_por="VEND-1")
        horario = cargar_horario(self.s, "VEND-4")
        corte = _corte_de_comisiones(self.s, "VEND-4", horario)
        self.assertEqual((corte.date(), corte.hour), (LUNES, 0))
        self.assertEqual(comisiones_desde_ultimo_pago(self.s, "VEND-4", horario), 20)
        self.assertEqual(self.pago.comisiones, 83)

    def test_si_no_era_el_ultimo_pago_el_ciclo_no_se_toca(self) -> None:
        self.s.get(EmpleadaHorario, "VEND-4").fecha_ultimo_pago = date(2026, 10, 25)
        r = nom.mover_fecha_pago(self.s, self.pago.id, DOMINGO, creado_por="VEND-1")
        self.assertFalse(r["ciclo_movido"])
        self.assertEqual(self.s.get(EmpleadaHorario, "VEND-4").fecha_ultimo_pago, date(2026, 10, 25))

    def test_no_a_un_dia_con_otro_pago_ni_al_futuro_ni_antes_del_periodo(self) -> None:
        self.s.add(EmpleadaPago(employee_code="VEND-4", employee_name="Stayce", fecha=DOMINGO, hasta=DOMINGO,
                                total=Decimal("1.00"), creado_por="VEND-1"))
        self.s.flush()
        with self.assertRaisesRegex(ValueError, "otro pago"):
            nom.mover_fecha_pago(self.s, self.pago.id, DOMINGO, creado_por="VEND-1")
        with self.assertRaisesRegex(ValueError, "todavía no llega"):
            nom.mover_fecha_pago(self.s, self.pago.id, date.today() + timedelta(days=1), creado_por="VEND-1")
        with self.assertRaisesRegex(ValueError, "cubre desde"):
            nom.mover_fecha_pago(self.s, self.pago.id, date(2026, 10, 10), creado_por="VEND-1")
        with self.assertRaisesRegex(ValueError, "ya está"):
            nom.mover_fecha_pago(self.s, self.pago.id, LUNES, creado_por="VEND-1")

    def test_solo_daniel(self) -> None:
        with self.assertRaises(PermissionError):
            nom.mover_fecha_pago(self.s, self.pago.id, DOMINGO, creado_por="ENC-1")

    def test_si_en_el_dia_viejo_queda_otro_pago_su_marca_se_queda(self) -> None:
        self.s.add(EmpleadaPago(employee_code="VEND-4", employee_name="Stayce", fecha=LUNES, hasta=LUNES,
                                total=Decimal("1.00"), creado_por="VEND-1"))
        self.s.flush()
        nom.mover_fecha_pago(self.s, self.pago.id, DOMINGO, creado_por="VEND-1")
        self.assertEqual(self._marcas(), [DOMINGO, LUNES])


if __name__ == "__main__":
    unittest.main()
