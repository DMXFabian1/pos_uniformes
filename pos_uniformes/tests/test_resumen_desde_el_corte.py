"""/hoy y el resumen cuentan el dinero desde el último corte, como la Libreta.

Lo vendido después del corte de ayer es dinero de hoy (Daniel, 2026-10-15)."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaCorte, LibretaVenta
from pos_uniformes.services import resumen_diario_service as rd


class DesdeElCorteTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        ahora = datetime.now().astimezone()
        self.corte_ayer = ahora - timedelta(days=1)
        self.s.add(LibretaCorte(
            fecha=self.corte_ayer.date(), monto_final=Decimal("16852.00"), creado_por="VEND-1",
            created_at=self.corte_ayer, hasta=self.corte_ayer,
        ))
        self._venta(self.corte_ayer - timedelta(minutes=10), "299.00")   # ya se entregó
        self._venta(self.corte_ayer + timedelta(minutes=20), "190.00")   # después del corte
        self._venta(self.corte_ayer + timedelta(minutes=64), "942.00")
        self._venta(ahora - timedelta(minutes=5), "149.00")              # hoy
        self.s.commit()

    def _venta(self, cuando, monto) -> None:
        self.s.add(LibretaVenta(
            employee_code="VEND-4", employee_name="Stayce", tipo="venta", piezas=1,
            comisiones=1, monto_total=Decimal(monto), monto_neto=Decimal(monto),
            detalle=[], created_at=cuando,
        ))

    def test_hoy_trae_lo_de_despues_del_corte_de_ayer(self) -> None:
        d = rd.recolectar(self.s, date.today())
        self.assertEqual(d.operaciones, 3)
        self.assertEqual(d.efectivo, Decimal("1281.00"))          # 190 + 942 + 149

    def test_el_mensaje_dice_desde_cuando(self) -> None:
        d = rd.recolectar(self.s, date.today())
        self.assertIn("desde el corte de ayer", rd.texto_hoy(d))
        self.assertIn("VENTAS (desde el corte de ayer", rd.formatear(d))

    def test_un_dia_pasado_se_lee_por_calendario(self) -> None:
        ayer = date.today() - timedelta(days=1)
        d = rd.recolectar(self.s, ayer)
        self.assertIsNone(d.inicio_corte)
        self.assertEqual(d.periodo, "hoy")

    def test_despues_del_corte_de_hoy_arranca_en_ceros_y_lo_dice(self) -> None:
        ahora = datetime.now().astimezone()
        self.s.add(LibretaCorte(fecha=date.today(), monto_final=Decimal("1281.00"),
                                creado_por="VEND-1", created_at=ahora, hasta=ahora))
        self.s.commit()
        d = rd.recolectar(self.s, date.today())
        self.assertEqual(d.operaciones, 0)
        self.assertIn("Ninguna venta desde el corte de hoy", rd.texto_hoy(d))

    def test_sin_ningun_corte_es_el_dia(self) -> None:
        self.s.query(LibretaCorte).delete()
        self.s.commit()
        d = rd.recolectar(self.s, date.today())
        self.assertIsNone(d.inicio_corte)
        self.assertEqual(d.operaciones, 1)                         # solo la de hoy


if __name__ == "__main__":
    unittest.main()
