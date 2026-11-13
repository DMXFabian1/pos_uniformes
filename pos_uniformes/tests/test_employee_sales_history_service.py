"""Operaciones del día de una empleada y su detalle, desde la Libreta.

2026-11-12, Daniel: «la caja antigua ya no es de utilidad, todo lo demás
corre en libreta y kioskos» → «Pantallas con datos viejos». Antes leía la
tabla `venta` de la Caja antigua.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.services.employee_sales_history_service import (
    build_employee_day_sale_rows,
    build_employee_sale_detail_snapshot,
    folio_de_operacion,
    list_employee_day_sale_rows,
    load_employee_sale_detail_snapshot,
)

_UUID = "3f9a12bc-0000-4000-8000-000000000001"


def _op(id_, hora, monto, *, piezas=1, tipo="venta", cliente=None, uuid=None, empleada=False, detalle=()):
    return SimpleNamespace(
        id=id_, tipo=tipo, cliente=cliente, operacion_uuid=uuid, piezas=piezas,
        monto_total=Decimal(monto), descuento_empleada=empleada, detalle=list(detalle),
        created_at=datetime(2026, 11, 12, *hora),
    )


class EmployeeSalesHistoryServiceTests(unittest.TestCase):
    def test_las_operaciones_del_dia_con_hora_folio_cliente_piezas_y_total(self) -> None:
        rows = build_employee_day_sale_rows([
            _op(11, (10, 30), "399", piezas=3, cliente="Maria Fernanda", uuid=_UUID),
            _op(12, (12, 5), "900", piezas=2, tipo="apartado"),
        ])

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].sale_id, 11)
        self.assertEqual(rows[0].values, ("10:30", "3F9A-12BC", "Maria Fernanda", 3, Decimal("399.00")))
        self.assertEqual(rows[1].values, ("12:05", "#12 (apartado)", "Mostrador", 2, Decimal("900.00")))

    def test_ni_abonos_ni_su_propia_compra(self) -> None:
        rows = build_employee_day_sale_rows([
            _op(1, (10, 0), "100", piezas=0, tipo="abono"),
            _op(2, (11, 0), "250", empleada=True),
        ])
        self.assertEqual(rows, ())

    def test_folio_de_una_operacion_vieja_sin_uuid(self) -> None:
        self.assertEqual(folio_de_operacion(_op(7, (9, 0), "1")), "#7")

    def test_el_detalle_sale_de_las_lineas_de_la_libreta(self) -> None:
        operacion = _op(
            11, (10, 30), "399", piezas=3, cliente="Maria Fernanda", uuid=_UUID,
            detalle=[
                {"sku": "SKU-001", "nombre": "Playera Polo", "talla": "8", "precio": "100", "cantidad": 2, "subtotal": "200"},
                {"sku": "SKU-002", "nombre": "Sueter Escolar", "talla": "", "precio": "199", "cantidad": 1},
            ],
        )

        snapshot = build_employee_sale_detail_snapshot(operacion)

        self.assertEqual(snapshot.sale_id, 11)
        self.assertEqual(snapshot.folio, "3F9A-12BC")
        self.assertEqual(snapshot.time_label, "10:30")
        self.assertEqual(snapshot.client_name, "Maria Fernanda")
        self.assertEqual(snapshot.pieces, 3)
        self.assertEqual(snapshot.total, Decimal("399.00"))
        self.assertEqual(
            snapshot.rows[0].values,
            ("SKU-001", "Playera Polo · talla 8", 2, Decimal("100.00"), Decimal("200.00")),
        )
        self.assertEqual(
            snapshot.rows[1].values,
            ("SKU-002", "Sueter Escolar", 1, Decimal("199.00"), Decimal("199.00")),
        )


class DesdeLaBaseTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)

    def _anotar(self, code, tipo, monto, hora) -> LibretaVenta:
        row = LibretaVenta(
            employee_code=code, employee_name="X", tipo=tipo, piezas=1 if tipo != "abono" else 0,
            monto_total=Decimal(monto), monto_neto=Decimal(monto),
            detalle=[{"sku": "S1", "nombre": "Pants", "talla": "10", "precio": monto, "cantidad": 1, "subtotal": monto}],
            created_at=datetime.combine(date.today(), datetime.min.time()).replace(hour=hora).astimezone(),
        )
        self.s.add(row)
        self.s.commit()
        return row

    def test_lista_lo_que_vendio_ese_dia_y_abre_su_detalle(self) -> None:
        venta = self._anotar("VEND-1", "venta", "300", 10)
        self._anotar("VEND-1", "abono", "100", 11)
        self._anotar("VEND-2", "venta", "500", 12)

        rows = list_employee_day_sale_rows(self.s, employee_code="vend-1", target_day=date.today())
        self.assertEqual([r.sale_id for r in rows], [venta.id])

        snapshot = load_employee_sale_detail_snapshot(self.s, sale_id=venta.id)
        self.assertEqual(snapshot.total, Decimal("300.00"))
        self.assertEqual(snapshot.rows[0].values[0], "S1")

    def test_una_operacion_borrada_ya_no_se_abre(self) -> None:
        with self.assertRaises(ValueError):
            load_employee_sale_detail_snapshot(self.s, sale_id=999)


if __name__ == "__main__":
    unittest.main()
